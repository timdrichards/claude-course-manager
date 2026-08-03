#!/usr/bin/env python3
"""
Pull unanswered student questions out of a Piazza course.

Read-only by design. This script has no code path that creates, edits, answers,
pins, or deletes anything on Piazza. It logs in, reads the feed, reads threads,
and writes JSON to disk. That is the whole surface area, and keeping it that way
is what makes it safe to run unattended on a schedule.

Piazza has no official public API. This talks to Piazza's internal endpoints via
the unofficial `piazza-api` client, which means it can break when Piazza changes
something. Failures here should be loud, not silent, so a broken fetch never
looks like "no new questions".

Piazza state lives in <course>/.infra/piazza/. See course_infra.py for the layout.

Setup:
    pip install piazza-api
    python3 course_infra.py init ~/courses/326 --tool piazza \
        --course-url https://piazza.com/class/abc
    # then fill in the password in ~/courses/326/.infra/piazza/credentials

Usage:
    python3 piazza_fetch.py --course ~/courses/326
    python3 piazza_fetch.py --course ~/courses/326 --since 12h
    python3 piazza_fetch.py --course ~/courses/326 --all --scan-leaks
"""

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import course_infra  # noqa: E402

TOOL = "piazza"


# ---------------------------------------------------------------- credentials

def load_credentials(root):
    """Every client script in this plugin reads credentials the same way: the
    course's own file first, environment variables as the escape hatch for someone
    teaching several courses on one account. course_infra owns that rule."""
    values = course_infra.require_credentials(
        root, TOOL, ["PIAZZA_EMAIL", "PIAZZA_PASSWORD"])
    return values["PIAZZA_EMAIL"], values["PIAZZA_PASSWORD"]


# ------------------------------------------------------------------- parsing

def network_id(course_url=None, nid=None):
    """Course URLs look like https://piazza.com/class/mfxyzabc123."""
    if nid:
        return nid.strip()
    m = re.search(r"piazza\.com/class/([a-zA-Z0-9]+)", course_url or "")
    if not m:
        sys.exit(f"Could not find a class id in {course_url!r}. "
                 "Expected something like https://piazza.com/class/mfxyzabc123")
    return m.group(1)


def strip_html(raw):
    """Piazza stores post bodies as HTML. Flatten to readable text, keeping
    code blocks intact since a debugging question is mostly its code."""
    if not raw:
        return ""
    text = raw
    text = re.sub(r"<pre[^>]*>(.*?)</pre>", r"\n```\n\1\n```\n", text, flags=re.S | re.I)
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>|</div>|</li>", "\n", text, flags=re.I)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.I)
    text = re.sub(r"<img[^>]*src=['\"]([^'\"]+)['\"][^>]*>", r"[image: \1]", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_since(value):
    """Accept '12h', '3d', or an ISO date."""
    if not value:
        return None
    v = value.strip().lower()
    now = datetime.now(timezone.utc)
    if v.endswith("h") and v[:-1].isdigit():
        return now - timedelta(hours=int(v[:-1]))
    if v.endswith("d") and v[:-1].isdigit():
        return now - timedelta(days=int(v[:-1]))
    try:
        dt = datetime.fromisoformat(v.replace("z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        sys.exit(f"Could not read --since {value!r}. Use '12h', '3d', or an ISO date.")


def parse_ts(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------ leak detection

ASSIGNMENT_FOLDER_RE = re.compile(r"(hw\d*|homework|assignment|proj|project|lab\d*|pset|ps\d+)", re.I)

# Lines that look like output rather than authorship. A student pasting a stack
# trace is asking for help, not leaking a solution, and privatizing those would
# make the tool feel arbitrary and train students to stop posting detail.
ERROR_LINE_RE = re.compile(
    r"(traceback|^\s*at\s+\S+\s*\(|^\s*File\s+\"|"
    r"\w*Error\b|\w*Exception\b|npm ERR!|^\s*\^+\s*$|"
    r"node_modules|webpack|^\s*warning:|^\s*\d+\s*\|)", re.I)

CODE_LINE_RE = re.compile(
    r"(=>|\bfunction\b|\bdef\b|\breturn\b|\bconst\b|\blet\b|\bvar\b|"
    r"\bimport\b|\bclass\b|\bif\s*\(|\bfor\s*\(|\bwhile\s*\(|"
    r"</?\w+[\s/>]|[{};]\s*$|^\s*[\w.\[\]]+\s*=[^=])")


def code_blocks(raw_html):
    """Pull out fenced/preformatted regions, which is where real code lives."""
    blocks = re.findall(r"<pre[^>]*>(.*?)</pre>", raw_html or "", flags=re.S | re.I)
    blocks += re.findall(r"```(.*?)```", raw_html or "", flags=re.S)
    return [html.unescape(re.sub(r"<[^>]+>", "", b)) for b in blocks]


def measure_code(text):
    """Return (authored_code_lines, error_output_lines)."""
    authored = errors = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        if ERROR_LINE_RE.search(line):
            errors += 1
        elif CODE_LINE_RE.search(line):
            authored += 1
    return authored, errors


def assess_leak(thread, raw_html, min_code_lines, keywords):
    """Decide whether a public post shows substantial assignment code.

    Deliberately conservative. A false positive pulls a legitimate question out
    of the class feed, which costs the student and the class more than a few
    extra hours of a solution being visible costs the course.
    """
    reasons = []

    folders = " ".join(thread.get("folders") or [])
    haystack = f"{thread.get('subject','')} {thread.get('body','')}".lower()
    in_assignment_folder = bool(ASSIGNMENT_FOLDER_RE.search(folders))
    keyword_hit = next((k for k in keywords if k.lower() in haystack), None)

    if in_assignment_folder:
        reasons.append(f"posted in assignment folder ({folders})")
    if keyword_hit:
        reasons.append(f"mentions {keyword_hit!r}")
    if not (in_assignment_folder or keyword_hit):
        return None

    blocks = code_blocks(raw_html)
    if blocks:
        authored, errors = map(sum, zip(*(measure_code(b) for b in blocks)))
    else:
        authored, errors = measure_code(thread.get("body", ""))
        if authored:
            reasons.append("code is inline rather than in a code block")

    if authored < min_code_lines:
        return None

    if errors > authored:
        return None  # mostly a stack trace; that is a question, not a leak

    reasons.append(f"{authored} lines of authored code"
                   + (f" ({errors} lines look like error output)" if errors else ""))

    return {
        "cid": thread["cid"],
        "url": thread["url"],
        "subject": thread["subject"],
        "anonymous": thread["anonymous"],
        "code_lines": authored,
        "error_lines": errors,
        "folders": thread.get("folders", []),
        "reasons": reasons,
        "excerpt": (blocks[0][:400].strip() if blocks else thread.get("body", "")[:400]),
    }


# --------------------------------------------------------------------- state

def load_state(path):
    try:
        return set(json.loads(Path(path).read_text()).get("seen", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_state(path, seen):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"seen": sorted(seen)}, indent=2))


# ------------------------------------------------------------------ fetching

def summarize_thread(post, nid):
    """Flatten a Piazza thread into the fields a reply actually depends on."""
    history = post.get("history") or []
    latest = history[0] if history else {}

    student_answer = None
    instructor_answer = None
    followups = []
    for child in post.get("children", []):
        ctype = child.get("type")
        if ctype == "s_answer":
            h = (child.get("history") or [{}])[0]
            student_answer = strip_html(h.get("content"))
        elif ctype == "i_answer":
            h = (child.get("history") or [{}])[0]
            instructor_answer = strip_html(h.get("content"))
        elif ctype == "followup":
            followups.append({
                "text": strip_html(child.get("subject") or ""),
                "replies": [strip_html(g.get("subject") or "")
                            for g in child.get("children", [])],
                "resolved": child.get("no_answer", 0) == 0,
            })

    return {
        "cid": post.get("nr"),
        "id": post.get("id"),
        "url": f"https://piazza.com/class/{nid}?cid={post.get('nr')}",
        "type": post.get("type"),
        "subject": strip_html(latest.get("subject") or ""),
        "body": strip_html(latest.get("content") or ""),
        "folders": post.get("folders", []),
        "tags": post.get("tags", []),
        "created": post.get("created"),
        "updated": latest.get("created") or post.get("created"),
        "anonymous": bool(latest.get("anon") and latest.get("anon") != "no"),
        "student_answer": student_answer,
        "instructor_answer": instructor_answer,
        "has_instructor_answer": instructor_answer is not None,
        "followups": followups,
        "unresolved_followups": sum(1 for f in followups if not f["resolved"]),
        "views": post.get("unique_views"),
    }


def main():
    ap = argparse.ArgumentParser(description="Read unanswered Piazza questions (read-only).")
    ap.add_argument("--course", help="Course folder, or anywhere inside it (or set COURSE_DIR)")
    ap.add_argument("--course-url", help="Override the course URL in config.json")
    ap.add_argument("--nid", help="Override with a raw Piazza network id")
    ap.add_argument("--since", help="Only threads updated since: '12h', '3d', or ISO date")
    ap.add_argument("--limit", type=int, default=60, help="Feed items to scan (default 60)")
    ap.add_argument("--all", action="store_true",
                    help="Include threads that already have an instructor answer")
    ap.add_argument("--out",
                    help="Write JSON here (default: <course>/.infra/piazza/inbox/<timestamp>.json)")
    ap.add_argument("--stdout", action="store_true", help="Print JSON instead of writing a file")
    ap.add_argument("--no-state", action="store_true",
                    help="Ignore and do not update the seen-thread state")
    ap.add_argument("--scan-leaks", action="store_true",
                    help="Also flag public posts showing substantial assignment code")
    ap.add_argument("--min-code-lines", type=int,
                    help="Lines of authored code before a post counts as a leak (default 6)")
    ap.add_argument("--assignment-keywords",
                    help="Comma-separated assignment names, e.g. 'HW4,Recipe Browser'")
    args = ap.parse_args()

    try:
        from piazza_api import Piazza
    except ImportError:
        sys.exit("piazza-api is not installed. Run: pip install piazza-api")

    root = course_infra.resolve(args.course)
    piazza = course_infra.tool_dir(root, TOOL)
    if not piazza.is_dir():
        sys.exit(f"{piazza} does not exist. Set it up with:\n"
                 f"  python3 course_infra.py init {root} --tool piazza --course-url <piazza url>")
    cfg = course_infra.load_config(root, TOOL)

    course_url = args.course_url or cfg.get("course_url")
    if not (args.nid or course_url):
        sys.exit(f"No course URL. Put one in {piazza / course_infra.CONFIG} "
                 f"or pass --course-url.")
    nid = network_id(course_url, args.nid)

    min_code_lines = args.min_code_lines if args.min_code_lines is not None else cfg.get("min_code_lines", 6)
    if args.assignment_keywords is not None:
        keywords = [k.strip() for k in args.assignment_keywords.split(",") if k.strip()]
    else:
        keywords = cfg.get("assignment_keywords") or []

    state_file = piazza / course_infra.SEEN
    email, password = load_credentials(root)
    since = parse_since(args.since)
    seen = set() if args.no_state else load_state(state_file)

    p = Piazza()
    try:
        p.user_login(email=email, password=password)
    except Exception as e:
        sys.exit(f"Piazza login failed: {e}\n"
                 "If your school uses SSO for Piazza, password login will not work.")

    net = p.network(nid)
    feed = net.get_feed(limit=args.limit, offset=0).get("feed", [])

    post_cache = {}

    def fetch_post(cid):
        if cid not in post_cache:
            try:
                post_cache[cid] = net.get_post(cid)
            except Exception as e:
                print(f"warning: could not read thread {cid}: {e}", file=sys.stderr)
                post_cache[cid] = None
        return post_cache[cid]

    threads, skipped_seen = [], 0
    for item in feed:
        cid = item.get("nr")
        if cid is None:
            continue

        # Piazza marks a thread no_answer=1 when nobody has answered it.
        unanswered = bool(item.get("no_answer")) or bool(item.get("no_answer_followup"))
        if not args.all and not unanswered:
            continue

        updated = parse_ts(item.get("modified"))
        if since and updated and updated < since:
            continue

        key = f"{nid}:{cid}:{item.get('modified')}"
        if key in seen:
            skipped_seen += 1
            continue

        post = fetch_post(cid)
        if post is None:
            continue

        threads.append(summarize_thread(post, nid))
        seen.add(key)

    leak_candidates = []
    if args.scan_leaks:
        for item in feed:
            cid = item.get("nr")
            if cid is None:
                continue
            post = fetch_post(cid)
            if post is None:
                continue

            # Already private means already contained.
            if "instr_" in ((post.get("config") or {}).get("feed_groups") or ""):
                continue

            summary = summarize_thread(post, nid)
            raw = ((post.get("history") or [{}])[0]).get("content") or ""
            verdict = assess_leak(summary, raw, min_code_lines, keywords)
            if verdict:
                leak_candidates.append(verdict)

    result = {
        "course_root": str(root),
        "course_name": (course_infra.load_course(root).get("course_number") or root.name),
        "course_url": f"https://piazza.com/class/{nid}",
        "nid": nid,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "filter": {
            "unanswered_only": not args.all,
            "since": since.isoformat() if since else None,
            "feed_limit": args.limit,
            "scan_leaks": args.scan_leaks,
        },
        "counts": {
            "feed_scanned": len(feed),
            "returned": len(threads),
            "skipped_already_seen": skipped_seen,
            "leak_candidates": len(leak_candidates),
        },
        "threads": threads,
        "leak_candidates": leak_candidates,
    }

    payload = json.dumps(result, indent=2)
    if args.stdout:
        print(payload)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
        out = Path(args.out) if args.out else piazza / course_infra.INBOX / f"{stamp}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload)
        print(f"{len(threads)} thread(s)"
              + (f", {len(leak_candidates)} leak candidate(s)" if args.scan_leaks else "")
              + f" written to {out} ({skipped_seen} already seen, {len(feed)} scanned)",
              file=sys.stderr)

    # --stdout is for looking, not for consuming. Marking threads seen on a run
    # whose output went nowhere would silently hide them from the next real digest,
    # which is the failure mode this whole script exists to avoid.
    if not args.no_state and not args.stdout:
        save_state(state_file, seen)


if __name__ == "__main__":
    main()
