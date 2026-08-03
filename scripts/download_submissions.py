#!/usr/bin/env python3
"""download_submissions.py: pull every submission for an assignment to disk.

For offline grading, feedback, or feeding a similarity checker (MOSS for code,
Turnitin and friends for prose), this downloads each student's uploaded files,
text entry, and submitted URL into a per-student folder. The submission *list*
comes through canvas.py; the file
bytes are fetched directly from Canvas's pre-signed attachment urls (which
carry their own verifier token), falling back to the API token if a url ever
needs auth.

That fallback is the one place in this plugin outside canvas.py that needs a
token in hand, and it gets it from canvas_common.canvas_token() -- the course
folder's credentials file first, the environment second -- rather than reading
os.environ itself. Nothing here writes to Canvas, only to local disk, so there
is no write gate and no --live: downloading student work changes nothing on the
server, and pretending otherwise would dilute the flag everywhere else.

Output goes under .canvas-cache by default so it inherits this skill's gitignore
protection (Safety Rule 7 -- student work is PII). Layout:

  .canvas-cache/<course_id>/submissions/<assignment_id>/
    <sortable_name>_<user_id>/
      <uploaded files...>
      text_entry.html          (if the student typed a text submission)
      submitted_url.txt        (if the student submitted a url)
      _submission.json         (metadata: attempt, submitted_at, late, score)

Usage:
  download_submissions.py --course 326 --assignment-id 678
  download_submissions.py --course 326 --assignment-id 678 --out ./hw3-code
  download_submissions.py --course 326 --assignment-id 678 --dry-run
  download_submissions.py --course 326 --assignment-id 678 --submitted-only
  download_submissions.py --course-id 12345 --assignment-id 678   # no course folder

Output: JSON summary on stdout. Errors: JSON on stderr, nonzero exit code.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canvas_common  # noqa: E402

die = canvas_common.die


def safe_name(text, fallback="unknown"):
    """Filesystem-safe slug: keep it readable, drop path-hostile characters."""
    text = (text or "").strip()
    text = re.sub(r"[^\w.\- ]+", "_", text).strip(". ")
    text = re.sub(r"\s+", "_", text)
    return text or fallback


def download(url, dest_path, token):
    """Fetch url to dest_path. Try unauthenticated first (attachment urls carry
    a verifier), fall back to the API token on 401/403. Returns bytes written.

    The order matters and is not an oversight: Canvas attachment urls are
    pre-signed and already carry their own verifier, and sending a bearer token
    to the file host is both unnecessary and a way to leak an instructor token to
    whatever CDN the url points at. The token is the fallback, not the default.
    """
    def attempt(with_auth):
        headers = {"Authorization": f"Bearer {token}"} if with_auth else {}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        return len(data)

    try:
        return attempt(with_auth=False)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return attempt(with_auth=True)
        raise


def plan_student(sub):
    """Summarize what would be pulled for one submission."""
    user = sub.get("user") or {}
    attachments = sub.get("attachments") or []
    return {
        "user_id": sub.get("user_id") or user.get("id"),
        "name": user.get("sortable_name") or user.get("name"),
        "workflow_state": sub.get("workflow_state"),
        "attachments": len(attachments),
        "has_text": bool(sub.get("body")),
        "has_url": bool(sub.get("url")),
        "late": sub.get("late"),
    }


def main():
    # No --live/--override-mode: every byte this writes lands on local disk.
    p = argparse.ArgumentParser(
        description="Download all submissions for an assignment",
        parents=[canvas_common.global_flags(write=False)])
    p.add_argument("--assignment-id", type=int, required=True)
    p.add_argument("--out", default=None,
                   help="Output dir (default: .canvas-cache/<course>/submissions/<aid>)")
    p.add_argument("--submitted-only", action="store_true",
                   help="Skip students who never submitted (default: skip only if nothing to save)")
    args = canvas_common.apply_global_defaults(p.parse_args())
    course_id = canvas_common.resolve_course_id(args.course, args.course_id)

    token = canvas_common.canvas_token(args.course)
    if not token and not args.dry_run:
        die("No Canvas API token",
            "Put CANVAS_TOKEN in the course's .infra/canvas/credentials (see "
            "`course_infra.py verify <course> --tool canvas`), or export "
            "CANVAS_API_TOKEN. It is only used as a fallback for attachment urls "
            "that refuse the anonymous fetch, but a run without it can fail "
            "part-way through a roster.")

    subs, error = canvas_common.canvas_cli(
        ["get", f"/courses/{course_id}/assignments/{args.assignment_id}/submissions",
         "--all", "--param", "include[]=user"], course=args.course)
    if error is not None:
        die("Failed to list submissions", error)

    out_root = args.out or os.path.join(
        ".canvas-cache", str(course_id), "submissions", str(args.assignment_id))

    planned, skipped_test, skipped_empty = [], 0, 0
    to_process = []
    for sub in subs:
        user = sub.get("user") or {}
        name = user.get("sortable_name") or user.get("name") or ""
        if name.strip().lower() == "test student" or user.get("test_student"):
            skipped_test += 1
            continue
        has_content = bool(sub.get("attachments")) or bool(sub.get("body")) or bool(sub.get("url"))
        if not has_content:
            if args.submitted_only or sub.get("workflow_state") == "unsubmitted":
                skipped_empty += 1
                continue
        to_process.append(sub)
        planned.append(plan_student(sub))

    if args.dry_run:
        print(json.dumps({
            "dry_run": True, "course_id": course_id,
            "assignment_id": args.assignment_id, "out_dir": out_root,
            "students": planned, "students_to_download": len(to_process),
            "skipped_test_student": skipped_test, "skipped_no_submission": skipped_empty,
        }, indent=2))
        return

    results, errors = [], []
    for sub in to_process:
        user = sub.get("user") or {}
        uid = sub.get("user_id") or user.get("id")
        folder = os.path.join(
            out_root, f"{safe_name(user.get('sortable_name') or user.get('name'), 'student')}_{uid}")
        os.makedirs(folder, exist_ok=True)
        saved = []

        try:
            seen = {}
            for att in sub.get("attachments") or []:
                fname = safe_name(att.get("display_name") or att.get("filename"), "file")
                seen[fname] = seen.get(fname, 0) + 1
                if seen[fname] > 1:  # disambiguate duplicate filenames
                    root, ext = os.path.splitext(fname)
                    fname = f"{root}_{seen[fname]}{ext}"
                url = att.get("url")
                if not url:
                    continue
                n = download(url, os.path.join(folder, fname), token)
                saved.append({"file": fname, "bytes": n})
            if sub.get("body"):
                with open(os.path.join(folder, "text_entry.html"), "w", encoding="utf-8") as f:
                    f.write(sub["body"])
                saved.append({"file": "text_entry.html"})
            if sub.get("url"):
                with open(os.path.join(folder, "submitted_url.txt"), "w", encoding="utf-8") as f:
                    f.write(sub["url"] + "\n")
                saved.append({"file": "submitted_url.txt"})
            meta = {k: sub.get(k) for k in
                    ("user_id", "attempt", "submitted_at", "late", "seconds_late",
                     "workflow_state", "score", "grade")}
            meta["name"] = user.get("name")
            with open(os.path.join(folder, "_submission.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            results.append({"user_id": uid, "folder": folder, "saved": saved})
        except (urllib.error.URLError, OSError) as e:
            errors.append({"user_id": uid, "folder": folder, "error": str(e)})

    print(json.dumps({
        "dry_run": False, "course_id": course_id,
        "assignment_id": args.assignment_id, "out_dir": out_root,
        "downloaded": len(results), "students": results, "errors": errors,
        "skipped_test_student": skipped_test, "skipped_no_submission": skipped_empty,
    }, indent=2))
    if errors:
        sys.exit(2)


if __name__ == "__main__":
    main()
