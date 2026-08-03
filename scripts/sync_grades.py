#!/usr/bin/env python3
"""sync_grades.py: push grades from a Gradescope CSV export into a Canvas assignment.

Gradescope autogrades; the scores then have to get into the Canvas gradebook.
This closes that loop: read a Gradescope CSV, match each row to a Canvas
student by email (or SID / login id), and bulk-post the scores to one Canvas
assignment -- with a preview and a mismatch report so nobody is graded wrong or
silently skipped.

Like the other helpers here, it never calls Canvas directly: the roster read,
the current-score read, and the bulk-grade write all go through canvas.py.
Identity matching, CSV loading, and the write gate come from canvas_common, so
there is exactly one copy of each.

Before posting, this reads every current submission score. That read is what
makes the write reversible: the old scores go into the course's actions.log as
the `before` value, and it is also how the preview can tell you how many
students already have a score and are about to be overwritten. A bulk grade
post with no recorded before-state is a change you cannot walk back.

Usage:
  sync_grades.py grades.csv --course 326 --assignment-id 678
  sync_grades.py grades.csv --course 326 --assignment-id 678 --live
  sync_grades.py grades.csv --course-id 12345 --assignment-id 678 \
      --score-column "Total Score" --email-column Email
  sync_grades.py grades.csv --course 326 --assignment-id 678 --missing-zero

Course resolution: --course names a course folder (its canvas/config.json
supplies base_url, course_id, and write_mode). --course-id overrides that id
for a one-off; with neither, $CANVAS_COURSE_ID is used.

Column autodetection (override with the flags):
  score : "Total Score", then "Score"
  email : "Email"
  sid   : "SID", then "Student ID"
Matching precedence per row: the column you named, else email, else SID
(against Canvas sis_user_id), else login id. Ambiguous or unmatched rows are
reported, never guessed.

By default a row with an empty score (a student who never submitted, or a
Gradescope "Missing" status) is skipped and reported, not posted as zero. Pass
--missing-zero to post 0 for those instead.

Grading is student-visible, so writes are gated twice: nothing is sent without
--live, and when running against a course folder that folder's config.json must
also say "write_mode": "live" (or you pass --override-mode for a considered
one-off). Without --live you get the full plan and no Canvas write.

Output: JSON summary on stdout. Errors: JSON on stderr, nonzero exit code.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canvas_common import (  # noqa: E402
    EMAIL_CANDIDATES, MAXPTS_CANDIDATES, SCORE_CANDIDATES, SID_CANDIDATES,
    STATUS_CANDIDATES, apply_global_defaults, build_roster_maps, canvas_cli,
    canvas_get, die, fmt_score, global_flags, load_csv, log_action, match_row,
    pick_column, resolve_course_id, should_write,
)


def parse_score(raw):
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def build_grade_plan(rows, cols, maps, missing_zero, current_scores=None):
    """Return (grade_data, matched, skipped, unmatched).

    `current_scores` maps str(user_id) -> the score Canvas holds right now. It
    is optional so the pure-logic tests can call this without a Canvas read,
    but main() always passes it: each matched row then carries the value it is
    about to replace, which is what makes the preview honest and the audit log
    reversible.
    """
    current_scores = current_scores or {}
    grade_data, matched, skipped, unmatched = {}, [], [], []
    for i, row in enumerate(rows):
        uid, how = match_row(row, cols, maps)
        ident = (row.get(cols.get("email", "")) or row.get(cols.get("sid", "")) or
                 row.get("Name") or f"row {i + 2}")
        score = parse_score(row.get(cols["score"]))
        status = (row.get(cols["status"]) or "").strip() if cols.get("status") else ""

        if uid is None:
            unmatched.append({"csv_identity": ident, "reason": how})
            continue
        if score is None:
            if missing_zero:
                score = 0.0
            else:
                skipped.append({"user_id": uid, "csv_identity": ident,
                                "reason": "empty_score", "status": status or None})
                continue
        # Last row wins if a student appears twice; flag it.
        if str(uid) in grade_data:
            skipped.append({"user_id": uid, "csv_identity": ident,
                            "reason": "duplicate_row_overwrote_earlier"})
        grade_data[str(uid)] = {"posted_grade": fmt_score(score)}
        matched.append({"user_id": uid, "name": maps["name"].get(uid),
                        "matched_by": how, "score": score,
                        "old_score": current_scores.get(str(uid))})
    return grade_data, matched, skipped, unmatched


def main():
    # --course / --course-id / --dry-run / --live / --override-mode come from
    # canvas_common.global_flags() on a parent parser, so they are accepted
    # before or after the positional CSV path and are spelled identically in
    # every script here. apply_global_defaults fills in the ones argparse
    # suppressed.
    p = argparse.ArgumentParser(
        description="Sync a Gradescope CSV into a Canvas assignment",
        parents=[global_flags()])
    p.add_argument("csv_file", help="Path to a Gradescope grade export CSV")
    p.add_argument("--assignment-id", type=int, required=True,
                   help="Canvas assignment to post the grades to")
    p.add_argument("--score-column", help="CSV column holding the score")
    p.add_argument("--email-column", help="CSV column holding the student email")
    p.add_argument("--sid-column", help="CSV column holding the SIS/student id")
    p.add_argument("--missing-zero", action="store_true",
                   help="Post 0 for rows with an empty score (default: skip them)")
    args = apply_global_defaults(p.parse_args())

    course_id = resolve_course_id(args.course, args.course_id)

    headers, rows = load_csv(args.csv_file)
    if not rows:
        die("CSV has no data rows")
    cols = {
        "score": pick_column(headers, args.score_column, SCORE_CANDIDATES, "score"),
        "email": pick_column(headers, args.email_column, EMAIL_CANDIDATES, "email", required=False),
        "sid": pick_column(headers, args.sid_column, SID_CANDIDATES, "sid", required=False),
        "status": next((c for c in STATUS_CANDIDATES if c in headers), None),
    }
    if not cols["email"] and not cols["sid"]:
        die("Need at least an email or SID column to match students",
            {"available_columns": headers})
    maxpts_col = next((c for c in MAXPTS_CANDIDATES if c in headers), None)

    # Canvas assignment (for points sanity check), roster, and current scores.
    # The submissions read is the one that was missing: without it there is no
    # `before` value to log and no way to say how many grades get overwritten.
    assignment = canvas_get(f"/courses/{course_id}/assignments/{args.assignment_id}",
                            course=args.course, all_pages=False)
    users = canvas_get(f"/courses/{course_id}/users", course=args.course,
                       params=["enrollment_type[]=student", "include[]=email"])
    maps = build_roster_maps(users)
    submissions = canvas_get(
        f"/courses/{course_id}/assignments/{args.assignment_id}/submissions",
        course=args.course)
    current = {str(s.get("user_id")): s.get("score")
               for s in submissions if s.get("user_id") is not None}

    grade_data, matched, skipped, unmatched = build_grade_plan(
        rows, cols, maps, args.missing_zero, current)

    # Points sanity check: Gradescope max vs Canvas points_possible.
    warnings = []
    canvas_points = assignment.get("points_possible")
    gs_max = None
    if maxpts_col:
        gs_max = parse_score(rows[0].get(maxpts_col))
    if gs_max is not None and canvas_points is not None and gs_max != canvas_points:
        warnings.append(
            f"Gradescope max points ({gs_max}) != Canvas points_possible "
            f"({canvas_points}). Scores are posted as raw points either way; "
            "confirm the assignment is worth what you expect.")
    # Students on Canvas with no CSV row (never graded in Gradescope).
    graded_ids = {int(k) for k in grade_data}
    no_csv = [{"user_id": uid, "name": maps["name"][uid]}
              for uid in maps["name"] if uid not in graded_ids
              and uid not in {m["user_id"] for m in skipped}]

    # An overwrite is the change worth naming out loud: a student who already
    # has a score in the gradebook is having a real number replaced, not an
    # empty cell filled in.
    overwrites = [uid for uid in grade_data if current.get(uid) is not None]

    summary = {
        "course_id": course_id,
        "assignment": {"id": args.assignment_id, "name": assignment.get("name"),
                       "points_possible": canvas_points},
        "csv_rows": len(rows),
        "to_post": len(grade_data),
        "already_scored_would_be_overwritten": len(overwrites),
        "matched": matched,
        "skipped": skipped,
        "unmatched_csv_rows": unmatched,
        "canvas_students_without_a_csv_row": no_csv,
        "warnings": warnings,
    }

    if overwrites:
        print(f"{len(overwrites)} of these {len(grade_data)} students already have a "
              f"score and will be overwritten.", file=sys.stderr)

    if not grade_data:
        summary["dry_run"] = True
        if not args.dry_run:
            summary["note"] = "Nothing matched with a postable score; nothing to do."
        print(json.dumps(summary, indent=2))
        return

    if not should_write(args, what=f"{len(grade_data)} grade(s) for assignment "
                                   f"{args.assignment_id}"):
        summary["dry_run"] = True
        print(json.dumps(summary, indent=2))
        return

    path = f"/courses/{course_id}/assignments/{args.assignment_id}/submissions/update_grades"
    response, error = canvas_cli(
        ["post", path, "--json", json.dumps({"grade_data": grade_data})],
        course=args.course, live=True, override=args.override_mode)
    if error is not None:
        die("Bulk grade post failed", error)

    # Log the before-state keyed by user id, so `undo` can reconstruct the batch.
    # Values are the scores Canvas held a moment ago; None means "was ungraded",
    # which Canvas cannot be told to return to and a human has to decide about.
    log_action(args.course, "sync-grades", args.assignment_id,
               before={uid: current.get(uid) for uid in grade_data},
               after={uid: entry["posted_grade"] for uid, entry in grade_data.items()},
               count=len(grade_data), overwrote=len(overwrites),
               csv_file=args.csv_file,
               progress=(response or {}).get("id"))

    summary["dry_run"] = False
    summary["progress"] = {
        "id": (response or {}).get("id"),
        "url": (response or {}).get("url"),
        "workflow_state": (response or {}).get("workflow_state"),
        "note": "Bulk grading is asynchronous; poll GET /progress/<id> until completed.",
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
