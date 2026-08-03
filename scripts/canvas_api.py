#!/usr/bin/env python3
"""
Canvas LMS client: roster, assignments, submissions, announcements, and grades.

Canvas is the only platform in this plugin with a real, documented, stable API, so
it is where anything that must actually land goes. Piazza and Gradescope are
scraped and can break quietly; Canvas will tell you when you are wrong.

Reads are free. Writes are gated twice, the same way Piazza's privatize is: the
course's canvas/config.json must say "write_mode": "live", and the command must
also carry --live. One switch is a decision the instructor made once, deliberately;
the other is this invocation. A grade pushed to 200 students is not something to
make easy to do by accident.

Every write appends a line to <course>/.infra/canvas/actions.log recording what
changed and what the value was before, so an undo is always reconstructible.

Setup:
    python3 course_infra.py init 326 --tool canvas \\
        --base-url https://umass.instructure.com --course-id 123456
    # then put CANVAS_TOKEN in <course>/.infra/canvas/credentials
    # (Canvas: Account -> Settings -> New Access Token)

Usage:
    python3 canvas_api.py --course 326 whoami
    python3 canvas_api.py --course 326 roster
    python3 canvas_api.py --course 326 assignments
    python3 canvas_api.py --course 326 submissions 98765
    python3 canvas_api.py --course 326 announcements
    python3 canvas_api.py --course 326 announce --title "Exam moved" --file body.md --live
    python3 canvas_api.py --course 326 set-grade 98765 --user 4242 --score 17 \\
        --comment-file feedback.md --live
    python3 canvas_api.py --course 326 set-grades 98765 --file grades.json --live
    python3 canvas_api.py --course 326 undo            # show how to reverse the last write
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import course_infra  # noqa: E402

TOOL = "canvas"
PAGE_SIZE = 100
TIMEOUT = 30


# ----------------------------------------------------------------- transport

class CanvasError(RuntimeError):
    pass


class Canvas:
    def __init__(self, base_url, token, course_id):
        self.base = base_url.rstrip("/")
        self.token = token
        self.course_id = str(course_id)

    def _request(self, method, path, params=None, data=None):
        url = path if path.startswith("http") else f"{self.base}/api/v1{path}"
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)

        body = None
        headers = {"Authorization": f"Bearer {self.token}",
                   "Accept": "application/json"}
        if data is not None:
            body = urllib.parse.urlencode(data, doseq=True).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                payload = resp.read().decode("utf-8", "replace")
                link = resp.headers.get("Link", "")
                parsed = json.loads(payload) if payload.strip() else None
                return parsed, link
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:800]
            # Canvas returns useful errors; surfacing them beats a bare status code.
            raise CanvasError(explain_http(e.code, method, url, detail)) from None
        except urllib.error.URLError as e:
            raise CanvasError(f"Could not reach {self.base}: {e.reason}") from None

    def get(self, path, params=None):
        data, _ = self._request("GET", path, params=params)
        return data

    def get_all(self, path, params=None):
        """Follow Canvas's Link header. A 300-person roster is four pages, and
        silently returning the first hundred students would be a quiet disaster."""
        params = dict(params or {})
        params["per_page"] = PAGE_SIZE
        out, url, first = [], path, True
        while url:
            data, link = self._request("GET", url, params=params if first else None)
            first = False
            if isinstance(data, list):
                out.extend(data)
            elif data is not None:
                return data
            url = next_link(link)
        return out

    def post(self, path, data):
        return self._request("POST", path, data=data)[0]

    def put(self, path, data):
        return self._request("PUT", path, data=data)[0]

    # ------------------------------------------------------------- endpoints

    def whoami(self):
        return self.get("/users/self/profile")

    def course(self):
        return self.get(f"/courses/{self.course_id}",
                        {"include[]": ["term", "total_students"]})

    def roster(self):
        return self.get_all(f"/courses/{self.course_id}/users",
                            {"enrollment_type[]": "student",
                             "enrollment_state[]": ["active", "invited"],
                             "include[]": ["email", "enrollments"]})

    def assignments(self):
        return self.get_all(f"/courses/{self.course_id}/assignments",
                            {"order_by": "due_at"})

    def assignment(self, aid):
        return self.get(f"/courses/{self.course_id}/assignments/{aid}")

    def submissions(self, aid):
        return self.get_all(f"/courses/{self.course_id}/assignments/{aid}/submissions",
                            {"include[]": ["user", "submission_comments"]})

    def submission(self, aid, user_id):
        return self.get(
            f"/courses/{self.course_id}/assignments/{aid}/submissions/{user_id}",
            {"include[]": ["user", "submission_comments"]})

    def announcements(self):
        return self.get_all(f"/courses/{self.course_id}/discussion_topics",
                            {"only_announcements": "true"})

    def create_announcement(self, title, message, delayed_post_at=None):
        data = {"title": title, "message": message, "is_announcement": "true",
                "published": "true"}
        if delayed_post_at:
            data["delayed_post_at"] = delayed_post_at
        return self.post(f"/courses/{self.course_id}/discussion_topics", data)

    def create_assignment(self, spec):
        data = {}
        for key, value in spec.items():
            if isinstance(value, list):
                data[f"assignment[{key}][]"] = value
            elif isinstance(value, bool):
                data[f"assignment[{key}]"] = "true" if value else "false"
            elif value is not None:
                data[f"assignment[{key}]"] = value
        return self.post(f"/courses/{self.course_id}/assignments", data)

    def set_grade(self, aid, user_id, score=None, comment=None):
        data = {}
        if score is not None:
            data["submission[posted_grade]"] = str(score)
        if comment:
            data["comment[text_comment]"] = comment
        if not data:
            raise CanvasError("set_grade needs a score, a comment, or both.")
        return self.put(
            f"/courses/{self.course_id}/assignments/{aid}/submissions/{user_id}", data)

    def set_grades_bulk(self, aid, entries):
        """entries: [{user_id, score, comment}]. Canvas queues this and hands back a
        Progress object, so the call returning does not mean the grades landed."""
        data = {}
        for e in entries:
            uid = e["user_id"]
            if e.get("score") is not None:
                data[f"grade_data[{uid}][posted_grade]"] = str(e["score"])
            if e.get("comment"):
                data[f"grade_data[{uid}][text_comment]"] = e["comment"]
        if not data:
            raise CanvasError("No gradeable entries in that file.")
        return self.post(
            f"/courses/{self.course_id}/assignments/{aid}/submissions/update_grades", data)

    def progress(self, progress_id):
        return self.get(f"/progress/{progress_id}")


def next_link(header):
    for part in (header or "").split(","):
        chunk = part.split(";")
        if len(chunk) < 2:
            continue
        if 'rel="next"' in chunk[1].replace(" ", "").replace("'", '"'):
            return chunk[0].strip().strip("<>")
    return None


def explain_http(code, method, url, detail):
    """Canvas's failure modes are few and each has one obvious cause. Saying which
    saves a round of guessing."""
    hints = {
        401: "The token is missing, wrong, or expired. Regenerate it in Canvas: "
             "Account -> Settings -> New Access Token.",
        403: "The token is valid but not allowed to do this. Check that the account "
             "it belongs to is a teacher or TA in this course, and that the course "
             "is not concluded (a concluded course is read-only).",
        404: "Wrong course id, wrong assignment id, or the object was deleted. "
             "Confirm the ids with `course` and `assignments`.",
        422: "Canvas rejected the values. The detail below usually names the field.",
    }
    hint = hints.get(code, "")
    return (f"Canvas returned {code} for {method} {url}\n"
            + (f"  {hint}\n" if hint else "")
            + f"  detail: {detail}")


# ------------------------------------------------------------------ the gate

def check_write_allowed(root, cfg, live, override):
    """Two switches, both deliberate. Returns True if the write may proceed."""
    mode = cfg.get("write_mode", "dry-run")
    if not live:
        print("DRY RUN (no --live). Nothing was sent to Canvas.", file=sys.stderr)
        return False
    if mode != "live" and not override:
        print(f"{course_infra.tool_dir(root, TOOL)}/config.json says "
              f"write_mode={mode!r}, so --live is refused.\n"
              f"Set it to \"live\" once you have watched this do the right thing, "
              f"or pass --override-mode for a one-off.", file=sys.stderr)
        return False
    return True


def record(root, action, target, before=None, after=None, **extra):
    entry = course_infra.log_action(root, TOOL, {
        "action": action, "target": str(target),
        "before": before, "after": after, **extra})
    return entry


# ------------------------------------------------------------------ printing

def show(obj):
    print(json.dumps(obj, indent=2, default=str))


def show_roster(users):
    print(f"{len(users)} student(s)")
    for u in users:
        sis = (u.get("sis_user_id") or "")
        print(f"  {str(u.get('id')).ljust(9)} {(u.get('sortable_name') or u.get('name') or '').ljust(32)} "
              f"{(u.get('email') or '').ljust(34)} {sis}")


def show_assignments(items):
    print(f"{len(items)} assignment(s)")
    for a in items:
        due = (a.get("due_at") or "no due date")[:16].replace("T", " ")
        pts = a.get("points_possible")
        pts = f"{pts:g} pts" if isinstance(pts, (int, float)) else "-"
        pub = "" if a.get("published") else "  [unpublished]"
        print(f"  {str(a.get('id')).ljust(9)} {due.ljust(17)} {pts.ljust(9)} "
              f"{a.get('name', '')}{pub}")


def show_submissions(items):
    graded = sum(1 for s in items if s.get("workflow_state") == "graded")
    print(f"{len(items)} submission(s), {graded} graded")
    for s in items:
        user = (s.get("user") or {}).get("sortable_name") or s.get("user_id")
        score = s.get("score")
        score = f"{score:g}" if isinstance(score, (int, float)) else "-"
        late = " LATE" if s.get("late") else ""
        missing = " MISSING" if s.get("missing") else ""
        print(f"  {str(s.get('user_id')).ljust(9)} {str(user)[:32].ljust(33)} "
              f"{score.rjust(6)}  {s.get('workflow_state', '')}{late}{missing}")


def show_announcements(items):
    print(f"{len(items)} announcement(s)")
    for a in items:
        when = (a.get("posted_at") or a.get("delayed_post_at") or "")[:16].replace("T", " ")
        print(f"  {str(a.get('id')).ljust(9)} {when.ljust(17)} {a.get('title', '')}")


# ---------------------------------------------------------------------- main

def build_client(root):
    cfg = course_infra.load_config(root, TOOL)
    missing = [k for k in ("base_url", "course_id") if not cfg.get(k)]
    if missing:
        sys.exit(f"canvas/config.json is missing {', '.join(missing)}.\n"
                 f"Run: python3 course_infra.py init {root} --tool canvas "
                 f"--base-url https://<school>.instructure.com --course-id <id>")
    creds = course_infra.require_credentials(root, TOOL, ["CANVAS_TOKEN"])
    return Canvas(cfg["base_url"], creds["CANVAS_TOKEN"], cfg["course_id"]), cfg


def main():
    # The global flags go on a parent parser so they are accepted both before and
    # after the subcommand. argparse otherwise rejects `... announce --live`, and
    # putting --live last is what everybody types.
    #
    # SUPPRESS is load-bearing: without it the subparser writes its own default over
    # whatever the top-level parser already collected, so `--course 326 roster` would
    # silently lose the course. Defaults are applied by hand after parsing instead.
    S = argparse.SUPPRESS
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--course", default=S, help="Course name or folder")
    common.add_argument("--live", action="store_true", default=S,
                        help="Actually write to Canvas")
    common.add_argument("--override-mode", action="store_true", default=S,
                        help="Allow a write even though config.json says dry-run")
    common.add_argument("--json", action="store_true", default=S,
                        help="Raw JSON output")

    ap = argparse.ArgumentParser(description="Canvas LMS client for one course.",
                                 parents=[common])
    sub = ap.add_subparsers(dest="command", required=True)

    def add(name, **kw):
        return sub.add_parser(name, parents=[common], **kw)

    for name in ("whoami", "course", "roster", "assignments", "announcements", "undo"):
        add(name)

    p = add("assignment"); p.add_argument("assignment_id")
    p = add("submissions"); p.add_argument("assignment_id")

    p = add("announce")
    p.add_argument("--title", required=True)
    p.add_argument("--file", help="Markdown or HTML body")
    p.add_argument("--text", help="Body text, instead of --file")
    p.add_argument("--at", help="Schedule for later, ISO 8601")

    p = add("create-assignment")
    p.add_argument("--file", required=True, help="JSON of Canvas assignment fields")

    p = add("set-grade")
    p.add_argument("assignment_id")
    p.add_argument("--user", required=True, help="Canvas user id")
    p.add_argument("--score")
    p.add_argument("--comment")
    p.add_argument("--comment-file")

    p = add("set-grades")
    p.add_argument("assignment_id")
    p.add_argument("--file", required=True,
                   help='JSON list of {"user_id":..,"score":..,"comment":..}')

    args = ap.parse_args()
    for key, default in (("course", None), ("live", False),
                         ("override_mode", False), ("json", False)):
        if not hasattr(args, key):
            setattr(args, key, default)

    root = course_infra.resolve(args.course)

    if args.command == "undo":
        return show_undo(root)

    canvas, cfg = build_client(root)

    try:
        return dispatch(args, root, canvas, cfg)
    except CanvasError as e:
        sys.exit(str(e))


def dispatch(args, root, canvas, cfg):
    cmd = args.command

    if cmd == "whoami":
        me = canvas.whoami()
        print(f"{me.get('name')} <{me.get('primary_email') or me.get('login_id')}> "
              f"(user {me.get('id')}) on {canvas.base}")
        c = canvas.course()
        print(f"Course {c.get('id')}: {c.get('name')} [{c.get('course_code')}] "
              f"{c.get('workflow_state')}")
        return 0

    readers = {
        "course": (canvas.course, show),
        "roster": (canvas.roster, show_roster),
        "assignments": (canvas.assignments, show_assignments),
        "announcements": (canvas.announcements, show_announcements),
    }
    if cmd in readers:
        fetch, render = readers[cmd]
        data = fetch()
        show(data) if args.json else render(data)
        return 0

    if cmd == "assignment":
        show(canvas.assignment(args.assignment_id))
        return 0

    if cmd == "submissions":
        data = canvas.submissions(args.assignment_id)
        show(data) if args.json else show_submissions(data)
        return 0

    # ------------------------------------------------------------- the writes

    if cmd == "announce":
        body = read_body(args)
        print(f"Announcement to course {canvas.course_id}: {args.title!r}\n"
              f"---\n{body}\n---")
        if not check_write_allowed(root, cfg, args.live, args.override_mode):
            return 0
        result = canvas.create_announcement(args.title, body, args.at)
        record(root, "announce", result.get("id"), after=args.title)
        print(f"Posted announcement {result.get('id')}: {result.get('html_url')}")
        return 0

    if cmd == "create-assignment":
        spec = json.loads(Path(args.file).read_text())
        print(json.dumps(spec, indent=2))
        if not check_write_allowed(root, cfg, args.live, args.override_mode):
            return 0
        result = canvas.create_assignment(spec)
        record(root, "create-assignment", result.get("id"), after=spec.get("name"))
        print(f"Created assignment {result.get('id')}: {result.get('html_url')}")
        return 0

    if cmd == "set-grade":
        comment = args.comment
        if args.comment_file:
            comment = Path(args.comment_file).read_text().strip()
        if args.score is None and not comment:
            sys.exit("Nothing to set. Give --score, --comment/--comment-file, or both.")
        before = canvas.submission(args.assignment_id, args.user)
        prior = before.get("score")
        print(f"user {args.user} on assignment {args.assignment_id}: "
              f"{prior if prior is not None else 'ungraded'} -> {args.score}")
        if comment:
            print(f"comment:\n{comment}")
        if not check_write_allowed(root, cfg, args.live, args.override_mode):
            return 0
        result = canvas.set_grade(args.assignment_id, args.user, args.score, comment)
        record(root, "set-grade", f"{args.assignment_id}/{args.user}",
               before=prior, after=result.get("score"), commented=bool(comment))
        print(f"Set to {result.get('score')} (was {prior if prior is not None else 'ungraded'})")
        return 0

    if cmd == "set-grades":
        entries = json.loads(Path(args.file).read_text())
        if isinstance(entries, dict):
            entries = entries.get("grades", [])
        # Validate before showing a preview. An entry without a user_id would pass
        # the preview and then fail mid-write, which is the worst place to fail.
        bad = [i for i, e in enumerate(entries)
               if not isinstance(e, dict) or not e.get("user_id")]
        if bad:
            sys.exit(f"{args.file}: entries at position {bad} have no user_id.\n"
                     f"Every entry needs a Canvas user id. Match students by SIS id "
                     f"or email using `roster`, never by name.")
        # Read current scores first: without them the audit log cannot undo this.
        current = {str(s.get("user_id")): s.get("score")
                   for s in canvas.submissions(args.assignment_id)}
        print(f"{len(entries)} grade(s) for assignment {args.assignment_id}")
        for e in entries:
            was = current.get(str(e.get("user_id")))
            print(f"  {str(e.get('user_id')).ljust(9)} "
                  f"{str(was) if was is not None else 'ungraded'} -> {e.get('score')}"
                  + ("  (+comment)" if e.get("comment") else ""))
        overwrites = [e for e in entries if current.get(str(e.get("user_id"))) is not None]
        if overwrites:
            print(f"\n{len(overwrites)} of these already have a score and will be overwritten.")
        if not check_write_allowed(root, cfg, args.live, args.override_mode):
            return 0
        result = canvas.set_grades_bulk(args.assignment_id, entries)
        record(root, "set-grades", args.assignment_id,
               before={str(e["user_id"]): current.get(str(e["user_id"])) for e in entries},
               after={str(e["user_id"]): e.get("score") for e in entries},
               progress=result.get("id"), count=len(entries))
        print(f"\nQueued as progress {result.get('id')}. Canvas applies these in the "
              f"background; check with:\n"
              f"  python3 canvas_api.py --course {root} submissions {args.assignment_id}")
        return 0

    sys.exit(f"Unknown command {cmd!r}")


def read_body(args):
    if args.file:
        return Path(args.file).read_text().strip()
    if args.text:
        return args.text.strip()
    sys.exit("Give the body with --file or --text.")


def show_undo(root):
    """The audit log records the previous value of everything it changed, so the
    reversal is always available. Printing the command beats printing a lecture."""
    log = course_infra.tool_dir(root, TOOL) / course_infra.ACTIONS
    if not log.exists():
        print("No Canvas writes recorded for this course.")
        return 0
    lines = [l for l in log.read_text().splitlines() if l.strip()]
    if not lines:
        print("No Canvas writes recorded for this course.")
        return 0
    last = json.loads(lines[-1])
    print(json.dumps(last, indent=2))
    action, target, before = last.get("action"), last.get("target"), last.get("before")

    if action == "set-grade" and before is not None:
        aid, uid = str(target).split("/")
        print(f"\nTo reverse:\n  python3 canvas_api.py --course {root} set-grade {aid} "
              f"--user {uid} --score {before} --live")
    elif action == "set-grade":
        print("\nThat submission had no score before. Canvas has no 'ungrade' through "
              "this script; clear it in the Canvas gradebook.")
    elif action == "set-grades":
        print("\nTo reverse, write the 'before' values above into a grades.json and "
              "run set-grades again. Entries that were null had no score, and Canvas "
              "cannot un-grade them from here; clear those in the gradebook.")
    elif action in ("announce", "create-assignment"):
        print(f"\nThis script does not delete. Remove {action.split('-')[-1]} {target} "
              f"in the Canvas web UI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
