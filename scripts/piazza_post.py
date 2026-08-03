#!/usr/bin/env python3
"""
Write actions against a Piazza course: post an approved answer, or make a public
post private.

This is the only script in the skill that writes. It is separate from
piazza_fetch.py on purpose, so that the thing running unattended on a schedule
physically cannot post.

Three safety properties, all deliberate:

1.  Every write is logged to <course>/.infra/piazza/actions.log with enough detail to
    reverse it. There is no way to make a change here that leaves no trace.
2.  `privatize` defaults to dry-run and requires --live to act. Piazza's
    visibility field is undocumented, so an unverified write to it gets the
    cautious default rather than the convenient one.
3.  After any privatize, the post is re-fetched and its content compared against
    what was there before. If the content changed, the script restores it and
    exits non-zero. The failure mode being guarded against is an update call
    that silently overwrites a student's post body, which would be much worse
    than the leak it was trying to contain.

All state lives in <course>/.infra/piazza/. See course_infra.py for the layout.

Usage:
    piazza_post.py answer      --course ~/courses/326 --cid 141 --file draft.md
    piazza_post.py followup    --course ~/courses/326 --cid 141 --file note.md
    piazza_post.py privatize   --course ~/courses/326 --cid 146            # dry run
    piazza_post.py privatize   --course ~/courses/326 --cid 146 --live --explain
    piazza_post.py unprivatize --course ~/courses/326 --cid 146 --live
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import course_infra  # noqa: E402
from piazza_fetch import load_credentials, network_id  # noqa: E402

TOOL = "piazza"

DEFAULT_EXPLANATION = (
    "I've made this post private so it's visible to you and the course staff "
    "rather than the whole class. It showed enough assignment code that leaving "
    "it public would give other students a head start they haven't earned yet. "
    "This is not a penalty and nothing is going on your record. Your question is "
    "still here and staff will answer it in this thread."
)


def log_action(root, record):
    path = course_infra.tool_dir(root, TOOL) / course_infra.ACTIONS
    path.parent.mkdir(parents=True, exist_ok=True)
    record["at"] = datetime.now(timezone.utc).isoformat()
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def connect(root, nid):
    try:
        from piazza_api import Piazza
    except ImportError:
        sys.exit("piazza-api is not installed. Run: pip install piazza-api")
    email, password = load_credentials(root)
    p = Piazza()
    try:
        p.user_login(email=email, password=password)
    except Exception as e:
        sys.exit(f"Piazza login failed: {e}")
    return p, p.network(nid)


def read_body(args):
    if args.file:
        return Path(args.file).read_text().strip()
    if args.text:
        return args.text.strip()
    sys.exit("Provide the text with --file or --text.")


def post_snapshot(net, cid):
    """Everything needed to detect and undo damage."""
    post = net.get_post(cid)
    hist = (post.get("history") or [{}])[0]
    author = hist.get("uid") or post.get("uid")
    if not author:
        for entry in post.get("change_log") or []:
            if entry.get("uid"):
                author = entry["uid"]
                break
    return {
        "post": post,
        "id": post.get("id"),
        "cid": post.get("nr"),
        "type": post.get("type"),
        "subject": hist.get("subject") or "",
        "content": hist.get("content") or "",
        "folders": post.get("folders", []),
        "feed_groups": (post.get("config") or {}).get("feed_groups", ""),
        "author_uid": author,
        "anonymous": bool(hist.get("anon") and hist.get("anon") != "no"),
    }


# --------------------------------------------------------------------- writes

def do_answer(net, args):
    body = read_body(args)
    snap = post_snapshot(net, args.cid)

    if args.dry_run:
        print(f"[dry run] Would post an instructor answer to cid {args.cid} "
              f"({snap['subject']!r}), {len(body)} chars.")
        return 0

    net.create_instructor_answer({"id": snap["id"], "nr": snap["cid"]}, body, revision=0)
    log_action(args.root, {"action": "answer", "cid": args.cid, "nid": args.nid, "chars": len(body)})
    print(f"Posted instructor answer to cid {args.cid}.")
    return 0


def do_followup(net, args):
    body = read_body(args)
    snap = post_snapshot(net, args.cid)

    if args.dry_run:
        print(f"[dry run] Would post a followup on cid {args.cid}, {len(body)} chars.")
        return 0

    net.create_followup({"id": snap["id"], "nr": snap["cid"]}, body)
    log_action(args.root, {"action": "followup", "cid": args.cid, "nid": args.nid, "chars": len(body)})
    print(f"Posted followup on cid {args.cid}.")
    return 0


def set_feed_groups(net, snap, feed_groups):
    """Change visibility while round-tripping every other field.

    Piazza's content.update is undocumented and the unofficial client's helper
    only sends `subject`, which is how a post body gets wiped. Sending the
    existing values back explicitly is what keeps this from being destructive.
    """
    config = dict(snap["post"].get("config") or {})
    config["feed_groups"] = feed_groups
    params = {
        "cid": snap["id"],
        "subject": snap["subject"],
        "content": snap["content"],
        "folders": snap["folders"],
        "type": snap["type"],
        "config": config,
    }
    return net._rpc.content_update(params)


def verify_or_restore(root, net, snap, expect_private, action="privatize"):
    """Re-read the post and make sure we changed only what we meant to."""
    after = post_snapshot(net, snap["cid"])

    if after["content"] != snap["content"] or after["subject"] != snap["subject"]:
        print("DANGER: the post body changed. Restoring the original text.", file=sys.stderr)
        try:
            set_feed_groups(net, snap, snap["feed_groups"])
        except Exception as e:
            print(f"Restore failed: {e}. Fix cid {snap['cid']} by hand now.", file=sys.stderr)
        log_action(root, {"action": f"{action}_aborted", "cid": snap["cid"],
                          "reason": "content changed", "original_content": snap["content"]})
        return False

    is_private = "instr_" in (after["feed_groups"] or "")
    if is_private != expect_private:
        print(f"Visibility did not change as expected (feed_groups="
              f"{after['feed_groups']!r}). Nothing was damaged; check the thread "
              f"in the browser.", file=sys.stderr)
        return False
    return True


def do_privatize(net, args, nid):
    snap = post_snapshot(net, args.cid)

    if "instr_" in (snap["feed_groups"] or ""):
        print(f"cid {args.cid} is already private. Nothing to do.")
        return 0

    if not snap["author_uid"]:
        print(f"Cannot determine who wrote cid {args.cid}, most likely because it is "
              f"anonymous. Refusing to act: making it private without their user id "
              f"would lock the student out of their own thread. Handle this one in the "
              f"browser.", file=sys.stderr)
        return 2

    target = f"instr_{nid},{snap['author_uid']}"

    if args.dry_run:
        print(f"[dry run] Would privatize cid {args.cid}: {snap['subject']!r}")
        print(f"[dry run]   feed_groups {snap['feed_groups']!r} -> {target!r}")
        if args.explain:
            print(f"[dry run]   and post an explanation followup ({len(args.explanation)} chars)")
        return 0

    set_feed_groups(net, snap, target)
    log_action(args.root, {"action": "privatize", "cid": args.cid, "nid": nid,
                           "previous_feed_groups": snap["feed_groups"], "new_feed_groups": target,
                           "subject": snap["subject"]})

    if not verify_or_restore(args.root, net, snap, expect_private=True):
        return 1

    print(f"cid {args.cid} is now private to staff and the author.")

    if args.explain:
        try:
            net.create_followup({"id": snap["id"], "nr": snap["cid"]}, args.explanation)
            log_action(args.root, {"action": "privatize_explanation", "cid": args.cid, "nid": nid})
            print("Posted the explanation followup.")
        except Exception as e:
            print(f"Privatized, but the explanation followup failed: {e}", file=sys.stderr)
            return 1

    print(f"Undo with: piazza_post.py unprivatize --nid {nid} --cid {args.cid} --live")
    return 0


def do_unprivatize(net, args, nid):
    snap = post_snapshot(net, args.cid)

    previous = ""
    action_log = course_infra.tool_dir(args.root, TOOL) / course_infra.ACTIONS
    if action_log.exists():
        for line in action_log.read_text().splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("action") == "privatize" and rec.get("cid") == args.cid:
                previous = rec.get("previous_feed_groups", "")

    if args.dry_run:
        print(f"[dry run] Would make cid {args.cid} public again "
              f"(feed_groups {snap['feed_groups']!r} -> {previous!r})")
        return 0

    set_feed_groups(net, snap, previous)
    log_action(args.root, {"action": "unprivatize", "cid": args.cid, "nid": nid,
                           "restored_feed_groups": previous})

    if not verify_or_restore(args.root, net, snap, expect_private=False):
        return 1
    print(f"cid {args.cid} is public again.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Post to Piazza. Writes only when told to.")
    ap.add_argument("action", choices=["answer", "followup", "privatize", "unprivatize"])
    ap.add_argument("--course", help="Course folder, or anywhere inside it (or set COURSE_DIR)")
    ap.add_argument("--course-url", help="Override the course URL in config.json")
    ap.add_argument("--nid", help="Override with a raw Piazza network id")
    ap.add_argument("--cid", type=int, required=True, help="Thread number as shown on Piazza")
    ap.add_argument("--file", help="File containing the text to post")
    ap.add_argument("--text", help="Text to post, inline")
    ap.add_argument("--live", action="store_true",
                    help="Actually perform the write. Required for privatize/unprivatize.")
    ap.add_argument("--dry-run", action="store_true", help="Force a dry run")
    ap.add_argument("--explain", action="store_true",
                    help="After privatizing, post a followup telling the student why")
    ap.add_argument("--explanation", default=DEFAULT_EXPLANATION,
                    help="Override the explanation text")
    ap.add_argument("--override-mode", action="store_true",
                    help="Allow --live even though config.json still says dry-run")
    args = ap.parse_args()

    root = course_infra.resolve(args.course)
    piazza = course_infra.tool_dir(root, TOOL)
    if not piazza.is_dir():
        sys.exit(f"{piazza} does not exist. Set it up with:\n"
                 f"  python3 course_infra.py init {root} --tool piazza --course-url <piazza url>")
    args.root = root
    cfg = course_infra.load_config(root, TOOL)

    course_url = args.course_url or cfg.get("course_url")
    if not (args.nid or course_url):
        sys.exit(f"No course URL. Put one in {piazza / course_infra.CONFIG} "
                 f"or pass --course-url.")
    nid = network_id(course_url, args.nid)
    args.nid = nid

    # A folder holds one course. If the shared profile and this tool's config
    # disagree about which class that is, stop: this is exactly the state in which
    # an answer meant for one section gets posted to another.
    info = course_infra.describe(root, TOOL)
    fatal = [p for p in info["problems"] if p.startswith("MISMATCH")]
    if fatal:
        sys.exit("\n".join(fatal) + f"\n\nNothing was posted. Check {piazza}.")

    # answer/followup are explicit acts of approval, so they run unless told not to.
    # privatize touches an undocumented field, so it needs --live every time, and
    # the course folder has to have been switched out of dry-run as well.
    if args.action in ("privatize", "unprivatize"):
        mode = cfg.get("privatize_mode", "dry-run")
        if args.live and mode != "live" and not args.override_mode:
            print(f"{piazza}/config.json still says privatize_mode={mode!r}, so --live is "
                  f"refused. Set it to \"live\" once you trust the detection, or pass "
                  f"--override-mode for a one-off.", file=sys.stderr)
            args.live = False
        args.dry_run = args.dry_run or not args.live

    _, net = connect(root, nid)

    if args.action == "answer":
        return do_answer(net, args)
    if args.action == "followup":
        return do_followup(net, args)
    if args.action == "privatize":
        return do_privatize(net, args, nid)
    return do_unprivatize(net, args, nid)


if __name__ == "__main__":
    sys.exit(main())
