#!/usr/bin/env python3
"""
Gradescope client. Read-only, on purpose and for a specific reason.

Gradescope has no public API. Their own guide says so and points at a feature
request. Everything here is scraping their Rails app, which means two things.

First, it breaks. Surveying the maintained open-source clients, the HTML parsing
broke roughly once a quarter over the last year while the login flow and URLs
stayed put for six. So every selector in this file raises loudly when it finds
nothing. A gradebook full of silent Nones is a far worse outcome than a stack
trace, because the stack trace is the only version you notice.

Second, and more important: there is no confirmed way to *write* a score. No
maintained client implements it, Gradescope documents no import path, and the
data model computes scores from rubric selections rather than point values.
Rather than ship a plausible-looking endpoint that quietly does nothing, this
script does not write at all. Push grades through Canvas, which has a real API.
If you want Gradescope writes, open its grading UI with DevTools, grade one
question, and capture the real request; then it can be added here honestly.

Requires:
    pip install requests beautifulsoup4

Setup:
    python3 course_infra.py init 326 --tool gradescope --course-id 753413
    # then fill GRADESCOPE_EMAIL / GRADESCOPE_PASSWORD in
    # <course>/.infra/gradescope/credentials

SSO: if you sign in through your school, you likely have no Gradescope password.
Try "Forgot your password?" once. If that fails, log in with a browser, copy the
_gradescope_session cookie, and put it in credentials as GRADESCOPE_SESSION.

Usage:
    python3 gradescope_fetch.py --course 326 courses
    python3 gradescope_fetch.py --course 326 assignments
    python3 gradescope_fetch.py --course 326 roster
    python3 gradescope_fetch.py --course 326 scores 1234567
    python3 gradescope_fetch.py --course 326 submissions 1234567
    python3 gradescope_fetch.py --course 326 download 1234567 --out ./subs
"""

import argparse
import csv
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import course_infra  # noqa: E402

TOOL = "gradescope"
BASE = "https://www.gradescope.com"
TIMEOUT = 30
POLITE_DELAY = 0.2  # no documented rate limit; this is courtesy, not a measurement


def need(module, package):
    try:
        return __import__(module)
    except ImportError:
        sys.exit(f"{module} is not installed. Run: pip install {package}")


class ScrapeError(RuntimeError):
    """Raised when a selector finds nothing. Always fatal, never swallowed."""


def must(value, what, url):
    """Every parse goes through here. When Gradescope restructures a page, this is
    the line that tells you which one and where to look."""
    if value is None or (hasattr(value, "__len__") and len(value) == 0):
        raise ScrapeError(
            f"Could not find {what} on {url}.\n"
            f"Gradescope almost certainly changed that page's HTML. This script's "
            f"selectors need updating; nothing is wrong with your course or login.")
    return value


# -------------------------------------------------------------------- session

def login(email=None, password=None, session_cookie=None):
    """Two ways in. The password form is the normal path; the cookie is the SSO
    escape hatch, because a SAML redirect chain with MFA is not scriptable and
    pretending otherwise just produces a confusing failure."""
    requests = need("requests", "requests")
    bs4 = need("bs4", "beautifulsoup4")
    from bs4 import BeautifulSoup

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0 (course-plugin gradescope client)"})

    if session_cookie:
        sess.cookies.set("_gradescope_session", session_cookie, domain="www.gradescope.com")
        check = sess.get(f"{BASE}/account", timeout=TIMEOUT, allow_redirects=True)
        if "login" in check.url:
            sys.exit("That GRADESCOPE_SESSION cookie is not valid any more.\n"
                     "Log in with a browser, copy a fresh _gradescope_session value, "
                     "and update the credentials file. These expire.")
        return sess, BeautifulSoup(check.text, "html.parser")

    page = sess.get(f"{BASE}/login", timeout=TIMEOUT)
    soup = BeautifulSoup(page.text, "html.parser")
    field = soup.select_one('form[action="/login"] input[name="authenticity_token"]')
    must(field, "the login form's CSRF token", f"{BASE}/login")

    resp = sess.post(f"{BASE}/login", timeout=TIMEOUT, allow_redirects=True, data={
        "utf8": "✓",
        "authenticity_token": field["value"],
        "session[email]": email,
        "session[password]": password,
        "session[remember_me]": 0,
        "commit": "Log In",
        "session[remember_me_sso]": 0,
    })

    # A failed login is a 200 that re-renders /login, not a 401. Checking status
    # would pass right through it.
    if "login" in resp.url.rsplit("/", 1)[-1] or not resp.history:
        sys.exit(
            "Gradescope login failed.\n"
            "  - Wrong password, or the account has no Gradescope-native password.\n"
            "  - If you sign in through your school, use the SSO fallback: log in "
            "with a browser, copy the _gradescope_session cookie, and set "
            "GRADESCOPE_SESSION in the credentials file.")

    soup = BeautifulSoup(resp.text, "html.parser")
    meta = soup.select_one('meta[name="csrf-token"]')
    if meta:
        sess.headers.update({"X-CSRF-Token": meta.get("content", "")})
    return sess, soup


def get_soup(sess, url):
    from bs4 import BeautifulSoup
    time.sleep(POLITE_DELAY)
    resp = sess.get(url, timeout=TIMEOUT)
    if "login" in resp.url and "/login" not in url:
        sys.exit("Gradescope bounced us to the login page. The session expired.")
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


# --------------------------------------------------------------------- reads

def list_courses(sess):
    """The most fragile endpoint in the set; its parser broke in Nov 2025."""
    url = f"{BASE}/account"
    soup = get_soup(sess, url)
    out = []
    for box in soup.select("a.courseBox"):
        href = box.get("href", "")
        if "/courses/" not in href:
            continue
        short = box.select_one(".courseBox--shortname")
        name = box.select_one(".courseBox--name")
        out.append({
            "id": href.rstrip("/").split("/")[-1],
            "short_name": short.get_text(strip=True) if short else "",
            "name": name.get_text(strip=True) if name else "",
            "url": BASE + href,
        })
    must(out, "any courses", url)
    return out


def list_assignments(sess, course_id):
    """The pleasant one: a React props blob rather than DOM scraping, which makes
    it the most durable read here."""
    url = f"{BASE}/courses/{course_id}/assignments"
    soup = get_soup(sess, url)
    el = soup.find("div", {"data-react-class": "AssignmentsTable"})
    must(el, "the assignments table", url)
    try:
        data = json.loads(el["data-react-props"])
    except (KeyError, json.JSONDecodeError) as e:
        raise ScrapeError(f"The assignments table on {url} was not readable JSON: {e}")

    out = []
    for row in data.get("table_data", []):
        if row.get("type") != "assignment":
            continue
        window = row.get("submission_window") or {}
        out.append({
            "id": str(row.get("url", "")).rstrip("/").split("/")[-1] or row.get("id"),
            "title": row.get("title"),
            "points": row.get("total_points"),
            "due": window.get("due_date"),
            "hard_due": window.get("hard_due_date"),
            "released": window.get("release_date"),
            "submissions": row.get("active_submissions"),
            "grading_progress": row.get("grading_progress"),
            "published": row.get("published"),
            "regrade_requests": row.get("regrade_request_count"),
            "url": BASE + str(row.get("url", "")),
        })
    must(out, "any assignment rows inside the assignments table", url)
    return out


def roster(sess, course_id):
    """Roster data hides in button attributes rather than cell text. This parser
    was patched twice in the last year; treat a break here as expected."""
    url = f"{BASE}/courses/{course_id}/memberships"
    soup = get_soup(sess, url)
    rows = soup.select("tr.rosterRow")
    must(rows, "any roster rows", url)

    out = []
    for row in rows:
        edit = row.select_one("button.rosterCell--editIcon")
        if not edit:
            continue
        try:
            cm = json.loads(edit.get("data-cm") or "{}")
        except json.JSONDecodeError:
            cm = {}
        name_btn = row.select_one("button.js-rosterName")
        user_id = None
        if name_btn and "user_id=" in (name_btn.get("data-url") or ""):
            user_id = name_btn["data-url"].split("user_id=")[-1]
        out.append({
            "user_id": user_id,
            "name": cm.get("full_name"),
            "first_name": cm.get("first_name"),
            "last_name": cm.get("last_name"),
            "sid": cm.get("sid"),
            "email": edit.get("data-email"),
            "role": {"0": "student", "1": "instructor", "2": "ta",
                     "3": "reader"}.get(str(edit.get("data-role")), edit.get("data-role")),
            "sections": edit.get("data-sections"),
        })
    must(out, "any readable roster entries (rows were found but none parsed)", url)
    return out


def scores(sess, course_id, assignment_id):
    """One request for the whole assignment, instead of one per submission. The
    per-submission route exists and is roughly 300 requests for a 300-person
    course; its own upstream docstring calls it not recommended."""
    url = f"{BASE}/courses/{course_id}/assignments/{assignment_id}/scores.csv"
    time.sleep(POLITE_DELAY)
    resp = sess.get(url, timeout=TIMEOUT)
    if resp.status_code == 404:
        sys.exit(f"No scores.csv for assignment {assignment_id}. Check the id with "
                 f"`assignments`, and that the assignment has been graded.")
    resp.raise_for_status()
    text = resp.text

    # The header row is not reliably first; find it rather than assuming an offset.
    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines[:5]):
        low = line.lower()
        if "email" in low or "sid" in low or "name" in low:
            start = i
            break
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    rows = list(reader)
    must(rows, "any score rows", url)
    return rows


def submissions(sess, course_id, assignment_id):
    url = f"{BASE}/courses/{course_id}/assignments/{assignment_id}/review_grades"
    soup = get_soup(sess, url)
    links = soup.select("td.table--primaryLink a")
    must(links, "any submission links", url)
    out = []
    for a in links:
        href = a.get("href", "")
        out.append({
            "submission_id": href.rstrip("/").split("/")[-1],
            "name": a.get_text(strip=True),
            "url": BASE + href,
        })
    return out


def download(sess, course_id, assignment_id, out_dir, limit=None):
    """The .zip route works for every submission type. The .json text_files route
    is cleaner but silently excludes image and PDF submissions, which is exactly
    the kind of quiet partial result worth avoiding."""
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    subs = submissions(sess, course_id, assignment_id)
    if limit:
        subs = subs[:limit]

    saved = []
    for s in subs:
        time.sleep(POLITE_DELAY)
        resp = sess.get(f"{s['url']}.zip", timeout=TIMEOUT)
        if resp.status_code != 200 or not resp.content:
            print(f"  skipped {s['submission_id']} ({s['name']}): "
                  f"HTTP {resp.status_code}", file=sys.stderr)
            continue
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in s["name"]).strip()
        path = out_dir / f"{s['submission_id']}_{safe or 'submission'}.zip"
        path.write_bytes(resp.content)
        saved.append(str(path))
        print(f"  {path.name}")
    return saved


# ---------------------------------------------------------------------- main

def connect(root):
    creds = course_infra.load_credentials(root, TOOL)
    if creds.get("GRADESCOPE_SESSION"):
        return login(session_cookie=creds["GRADESCOPE_SESSION"])
    creds = course_infra.require_credentials(
        root, TOOL, ["GRADESCOPE_EMAIL", "GRADESCOPE_PASSWORD"])
    return login(creds["GRADESCOPE_EMAIL"], creds["GRADESCOPE_PASSWORD"])


def write_out(root, name, payload, quiet=False):
    """Land results in the tool's inbox, same as Piazza fetches, so a later step
    can work from a file instead of a scrollback buffer."""
    inbox = course_infra.tool_dir(root, TOOL) / course_infra.INBOX
    inbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = inbox / f"{stamp}-{name}.json"
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    if not quiet:
        print(f"\nWrote {path}")
    return path


def main():
    ap = argparse.ArgumentParser(description="Read a Gradescope course. Never writes.")
    ap.add_argument("--course", help="Course name or folder")
    ap.add_argument("--json", action="store_true", help="Raw JSON to stdout")
    ap.add_argument("--no-save", action="store_true", help="Do not write to inbox/")

    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("courses")
    sub.add_parser("assignments")
    sub.add_parser("roster")
    p = sub.add_parser("scores"); p.add_argument("assignment_id")
    p = sub.add_parser("submissions"); p.add_argument("assignment_id")
    p = sub.add_parser("download")
    p.add_argument("assignment_id")
    p.add_argument("--out", default="./submissions")
    p.add_argument("--limit", type=int)

    args = ap.parse_args()
    root = course_infra.resolve(args.course)
    cfg = course_infra.load_config(root, TOOL)
    course_id = cfg.get("course_id")

    if args.command != "courses" and not course_id:
        sys.exit(f"gradescope/config.json has no course_id.\n"
                 f"Find it in the Gradescope URL for your course, then run:\n"
                 f"  python3 course_infra.py init {root} --tool gradescope --course-id <id>")

    try:
        sess, _ = connect(root)
        result = run(args, sess, course_id)
    except ScrapeError as e:
        sys.exit(str(e))

    if result is None:
        return 0
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    if not args.no_save:
        write_out(root, args.command, result, quiet=args.json)
    return 0


def run(args, sess, course_id):
    cmd = args.command

    if cmd == "courses":
        items = list_courses(sess)
        if not args.json:
            print(f"{len(items)} course(s)")
            for c in items:
                print(f"  {c['id'].ljust(9)} {(c['short_name'] or '').ljust(14)} {c['name']}")
        return items

    if cmd == "assignments":
        items = list_assignments(sess, course_id)
        if not args.json:
            print(f"{len(items)} assignment(s)")
            for a in items:
                due = str(a.get("due") or "no due date")[:16].replace("T", " ")
                prog = a.get("grading_progress")
                prog = f"{prog}% graded" if prog is not None else ""
                print(f"  {str(a['id']).ljust(9)} {due.ljust(17)} "
                      f"{str(a.get('points') or '-').rjust(5)} pts  "
                      f"{str(a.get('submissions') or 0).rjust(4)} subs  "
                      f"{prog.ljust(12)} {a.get('title', '')}")
        return items

    if cmd == "roster":
        people = roster(sess, course_id)
        if not args.json:
            students = [p for p in people if p["role"] == "student"]
            print(f"{len(people)} member(s), {len(students)} student(s)")
            for p in people:
                print(f"  {str(p.get('user_id') or '-').ljust(9)} "
                      f"{str(p.get('name') or '')[:30].ljust(31)} "
                      f"{str(p.get('email') or '').ljust(34)} "
                      f"{p.get('sid') or ''}  {p['role']}")
        return people

    if cmd == "scores":
        rows = scores(sess, course_id, args.assignment_id)
        if not args.json:
            print(f"{len(rows)} row(s); columns: {', '.join(list(rows[0].keys())[:8])}")
            for r in rows[:15]:
                name = r.get("Name") or r.get("name") or ""
                total = r.get("Total Score") or r.get("Score") or r.get("total_score") or ""
                print(f"  {str(name)[:32].ljust(33)} {str(total).rjust(8)}")
            if len(rows) > 15:
                print(f"  ... {len(rows) - 15} more")
        return rows

    if cmd == "submissions":
        items = submissions(sess, course_id, args.assignment_id)
        if not args.json:
            print(f"{len(items)} submission(s)")
            for s in items[:25]:
                print(f"  {s['submission_id'].ljust(11)} {s['name']}")
            if len(items) > 25:
                print(f"  ... {len(items) - 25} more")
        return items

    if cmd == "download":
        print(f"Downloading submissions for assignment {args.assignment_id}")
        saved = download(sess, course_id, args.assignment_id, args.out, args.limit)
        print(f"\n{len(saved)} file(s) in {args.out}")
        return None

    sys.exit(f"Unknown command {cmd!r}")


if __name__ == "__main__":
    sys.exit(main())
