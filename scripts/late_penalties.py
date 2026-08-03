#!/usr/bin/env python3
"""late_penalties.py: apply a course late policy to already-graded work.

Canvas's built-in late policy is a blunt per-course deduction. Many courses want
something else: a flat percent-per-day on one assignment, or a semester
"late-day budget" a student spends across assignments before penalties kick in.
This computes either from each submission's `late`/`seconds_late` and applies
the adjusted scores as a bulk grade update, with a comment on each explaining
the deduction. Every Canvas call goes through canvas.py; the shared helpers
(die, canvas_cli, the write gate, score formatting) come from canvas_common.

Submissions must already be graded -- the penalty adjusts the entered score.
Ungraded, excused, and on-time submissions are left untouched and reported, and
under the budget policy they also spend no late days (see budget_exclusion).

Two subcommands:

  apply   Flat percent-per-day on one assignment.
            late_penalties.py apply --course 326 --assignment-id 678 \
              --per-day 10 --max-days 5 --grace-minutes 10
            ... add --live once the preview looks right.

  budget  Late-day budget across several assignments. A student spends up to
          `budget_days` late days with no penalty; days beyond the budget are
          charged at `per_day_after` percent. Configured by a JSON file.
            late_penalties.py budget --config late-budget.json --course 326

late-budget.json:
  {
    "budget_days": 3,
    "per_day_after": 10,        // percent of points_possible per over-budget day
    "grace_minutes": 10,
    "floor": 0,                 // never drop a score below this
    "assignments": [231, 245, 262]   // ids, applied in chronological submit order
  }

Deductions are a percent of the assignment's points_possible per late day
(so "10% per day" on a 50-pt assignment is -5 pts/day), floored at `--floor`.

Course resolution: --course names a course folder (its canvas/config.json
supplies course_id and write_mode). --course-id overrides that id for a one-off;
with neither, $CANVAS_COURSE_ID is used.

This is a bulk, student-visible change, so it is gated twice: nothing is sent
without --live, and against a course folder that folder's config.json must also
say "write_mode": "live" (or pass --override-mode). Without --live you get the
whole ledger and no Canvas write. Every applied batch is written to the course's
actions.log with each student's old score, so it can be reversed.

Output: JSON summary on stdout. Errors: JSON on stderr, nonzero exit code.
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canvas_common import (  # noqa: E402
    apply_global_defaults, canvas_cli, canvas_get, die, fmt_score, global_flags,
    load_json_file, log_action, resolve_course_id, should_write,
)


# --------------------------------------------------------------------------- #
# pure penalty math (unit-tested)
# --------------------------------------------------------------------------- #

def days_late(seconds_late, grace_seconds):
    """Whole late days after a grace period, rounding any part-day up.

    Both arguments are in **seconds**. This deliberately mirrors
    mark_late.late_days, which computes the same quantity for the import path;
    a signature mixing seconds and minutes was a standing trap for anyone
    reading the two side by side. Callers holding a minutes-based config value
    (`grace_minutes`) convert at the call site.
    """
    eff = (seconds_late or 0) - (grace_seconds or 0)
    if eff <= 0:
        return 0
    return math.ceil(eff / 86400)


def penalized_score(score, points_possible, days, per_day_pct, floor):
    """Return (new_score, points_deducted). Deduction is per-day % of full marks."""
    if score is None or days <= 0:
        return score, 0.0
    deduction = days * (per_day_pct / 100.0) * (points_possible or 0)
    new = score - deduction
    if new < floor:
        new = floor
    new = round(new, 2)
    return new, round(score - new, 2)


def budget_exclusion(sub):
    """Why this submission may not spend late-day budget, or None if it may.

    THE RULE: a submission spends budget only if it is a submission that could
    actually be charged a late penalty. Everything else is late on paper only,
    and charging it silently steals days from the work that *is* penalizable.

      excused        Canvas excludes it from grading entirely. There is no
                     grade to protect, so there is nothing to spend a day on.
      ungraded       No entered score, so a penalty has nothing to deduct from.
                     (This was the live bug: an ungraded submission three days
                     late drained a three-day budget, and the graded submission
                     one day late that followed it was charged 50 -> 45 for a
                     day the student never should have paid for.)
      not_submitted  No submission time, so nothing was late by anything. A
                     never-submitted row carries `seconds_late` from Canvas but
                     it does not describe a student handing work in late.
      not_marked_late  Canvas does not consider it late -- typically an
                     instructor cleared `late_policy_status` by hand. That
                     decision outranks a stale `seconds_late`.

    These are exactly the conditions `gradeable()` screens out before a write,
    which is the point: the ledger and the write now agree about who is being
    charged, instead of the ledger charging a budget the write never spends.

    Keys absent from `sub` are read permissively, so a caller holding only the
    penalty-math fields (score, points_possible, seconds_late) still gets the
    plain arithmetic.
    """
    if sub.get("excused"):
        return "excused"
    if sub.get("score") is None:
        return "ungraded"
    if sub.get("workflow_state", "graded") != "graded":
        return "ungraded"
    if not sub.get("submitted_at", "unknown"):
        return "not_submitted"
    if not sub.get("late", True):
        return "not_marked_late"
    return None


def submitted_key(sub):
    """Sort key for spending the budget in the order the work came in.

    Canvas `submitted_at` is ISO 8601 in UTC, so a plain string sort is
    chronological. The tuple's first element pushes a missing or empty value to
    the END: sorted to the front (which is where "" lands on its own) a
    never-submitted row would spend the budget before any real submission had a
    chance to, which is the same drain the exclusion rule above exists to stop.
    """
    ts = str(sub.get("submitted_at") or "").strip()
    return (ts == "", ts)


def budget_ledger(subs, budget_days, per_day_after, grace_minutes, floor):
    """Spend a shared late-day budget across a student's submissions in order.

    `subs` is one student's submissions, pre-sorted chronologically (see
    submitted_key), each a dict with keys: assignment_id, name, score,
    points_possible, seconds_late, and -- from Canvas -- excused,
    workflow_state, late, submitted_at.

    Returns a per-submission ledger. Only over-budget days are penalized, and
    only a submission that could actually be penalized spends any budget at all;
    a row that cannot is reported with `spends_budget: false` and a reason, its
    days_late still shown so the exclusion is visible rather than invisible.
    """
    remaining = budget_days
    ledger = []
    for s in subs:
        d = days_late(s.get("seconds_late"), grace_minutes * 60)
        excluded = budget_exclusion(s)
        if excluded:
            used = over = 0
            new, deducted = s.get("score"), 0.0
        else:
            used = min(d, remaining)
            remaining -= used
            over = d - used
            new, deducted = penalized_score(
                s.get("score"), s.get("points_possible"), over, per_day_after, floor)
        ledger.append({
            "assignment_id": s.get("assignment_id"), "name": s.get("name"),
            "days_late": d, "budget_used": used, "penalized_days": over,
            "budget_remaining": remaining, "old_score": s.get("score"),
            "new_score": new, "deducted": deducted,
            "spends_budget": excluded is None, "excluded_reason": excluded,
        })
    return ledger


# --------------------------------------------------------------------------- #
# data helpers
# --------------------------------------------------------------------------- #

def get_assignment(course_id, aid, course=None):
    return canvas_get(f"/courses/{course_id}/assignments/{aid}",
                      course=course, all_pages=False)


def get_submissions(course_id, aid, course=None):
    return canvas_get(f"/courses/{course_id}/assignments/{aid}/submissions",
                      course=course, params=["include[]=user"])


def gradeable(sub):
    """True if this submission is a candidate for a late penalty."""
    return (sub.get("late") and not sub.get("excused")
            and sub.get("score") is not None
            and sub.get("workflow_state") == "graded")


def apply_grade_data(course_id, aid, grade_data, course=None, override=False):
    """Send one assignment's penalties. Only called after the gate has passed,
    so live=True here is not a second decision -- it is carrying the one already
    made through to canvas.py's own check."""
    path = f"/courses/{course_id}/assignments/{aid}/submissions/update_grades"
    data, error = canvas_cli(
        ["post", path, "--json", json.dumps({"grade_data": grade_data})],
        course=course, live=True, override=override)
    if error is not None:
        die(f"Failed to apply penalties for assignment {aid}", error)
    return data


# --------------------------------------------------------------------------- #
# apply
# --------------------------------------------------------------------------- #

def cmd_apply(args, course_id):
    assignment = get_assignment(course_id, args.assignment_id, args.course)
    points = assignment.get("points_possible") or 0
    subs = get_submissions(course_id, args.assignment_id, args.course)

    changes, untouched = [], []
    grade_data = {}
    for sub in subs:
        user = sub.get("user") or {}
        uid = sub.get("user_id") or user.get("id")
        if not gradeable(sub):
            reason = ("not late" if not sub.get("late") else
                      "excused" if sub.get("excused") else
                      "ungraded" if sub.get("score") is None else "not graded")
            untouched.append({"user_id": uid, "reason": reason})
            continue
        d = days_late(sub.get("seconds_late"), args.grace_minutes * 60)
        if args.max_days:
            d = min(d, args.max_days)
        new, deducted = penalized_score(sub["score"], points, d, args.per_day, args.floor)
        if deducted <= 0:
            untouched.append({"user_id": uid, "reason": "within grace / no deduction"})
            continue
        comment = (f"Late by {d} day(s); -{args.per_day}%/day late penalty "
                   f"({deducted} pts). Adjusted {fmt_score(sub['score'])} -> "
                   f"{fmt_score(new)}.")
        grade_data[str(uid)] = {"posted_grade": fmt_score(new), "text_comment": comment}
        changes.append({"user_id": uid, "name": user.get("name"), "days_late": d,
                        "old_score": sub["score"], "new_score": new, "deducted": deducted})

    summary = {"course_id": course_id,
               "assignment": {"id": args.assignment_id, "name": assignment.get("name"),
                              "points_possible": points},
               "policy": {"per_day_percent": args.per_day, "max_days": args.max_days,
                          "grace_minutes": args.grace_minutes, "floor": args.floor},
               "changes": changes, "changes_count": len(changes),
               "untouched_count": len(untouched)}

    if not grade_data:
        summary["dry_run"] = True
        if not args.dry_run:
            summary["note"] = "No late, graded submissions to penalize."
        print(json.dumps(summary, indent=2))
        return

    print(f"{len(grade_data)} student(s) already have a score and will be "
          f"overwritten with a penalized one.", file=sys.stderr)
    if not should_write(args, what=f"{len(grade_data)} penalized score(s) for "
                                   f"assignment {args.assignment_id}"):
        summary["dry_run"] = True
        print(json.dumps(summary, indent=2))
        return

    progress = apply_grade_data(course_id, args.assignment_id, grade_data,
                                args.course, args.override_mode) or {}
    log_action(args.course, "late-penalty-apply", args.assignment_id,
               before={str(c["user_id"]): c["old_score"] for c in changes},
               after={str(c["user_id"]): c["new_score"] for c in changes},
               count=len(changes), per_day_percent=args.per_day,
               progress=(progress or {}).get("id"))
    summary["dry_run"] = False
    summary["progress"] = {"id": progress.get("id"), "url": progress.get("url"),
                           "note": "async; poll GET /progress/<id> until completed"}
    print(json.dumps(summary, indent=2))


# --------------------------------------------------------------------------- #
# budget
# --------------------------------------------------------------------------- #

def cmd_budget(args, course_id):
    cfg = load_json_file(args.config, what="--config late-budget file")
    aids = cfg.get("assignments")
    if not isinstance(aids, list) or not aids:
        die("config needs a non-empty 'assignments' array of ids")
    aids = [a["id"] if isinstance(a, dict) else a for a in aids]
    budget_days = cfg.get("budget_days", 0)
    per_day_after = cfg.get("per_day_after", 0)
    grace_minutes = cfg.get("grace_minutes", 0)
    floor = cfg.get("floor", 0)

    # Gather each assignment's meta + submissions; index submissions per student.
    meta = {}
    per_student = {}   # uid -> list of submission dicts
    names = {}
    for aid in aids:
        a = get_assignment(course_id, aid, args.course)
        meta[aid] = {"name": a.get("name"), "points_possible": a.get("points_possible") or 0,
                     "due_at": a.get("due_at")}
        for sub in get_submissions(course_id, aid, args.course):
            user = sub.get("user") or {}
            uid = sub.get("user_id") or user.get("id")
            if uid is None:
                continue
            names[uid] = user.get("name")
            per_student.setdefault(uid, []).append({
                "assignment_id": aid, "name": a.get("name"),
                "points_possible": meta[aid]["points_possible"],
                "score": sub.get("score"), "late": sub.get("late"),
                "excused": sub.get("excused"), "workflow_state": sub.get("workflow_state"),
                "seconds_late": sub.get("seconds_late"),
                "submitted_at": sub.get("submitted_at") or "",
            })

    # Build per-assignment grade_data from each student's ledger.
    grade_data = {aid: {} for aid in aids}
    student_reports = []
    for uid, subs in per_student.items():
        subs.sort(key=submitted_key)  # chronological budget spend, blanks last
        # budget_ledger charges a day of budget only to a submission that could
        # actually be penalized (graded, submitted, not excused, marked late);
        # everything else passes through with budget_used 0 and an
        # excluded_reason. gradeable() then guards the write, and the two agree.
        ledger = budget_ledger(subs, budget_days, per_day_after, grace_minutes, floor)
        applied = []
        for row, sub in zip(ledger, subs):
            if row["penalized_days"] > 0 and gradeable(sub):
                comment = (f"Late by {row['days_late']} day(s), "
                           f"{row['budget_used']} covered by late-day budget; "
                           f"{row['penalized_days']} over-budget day(s) charged at "
                           f"-{per_day_after}%/day ({row['deducted']} pts). "
                           f"Adjusted {fmt_score(row['old_score'])} -> "
                           f"{fmt_score(row['new_score'])}.")
                grade_data[row["assignment_id"]][str(uid)] = {
                    "posted_grade": fmt_score(row["new_score"]), "text_comment": comment}
                applied.append(row)
        student_reports.append({
            "user_id": uid, "name": names.get(uid),
            "late_days_used": budget_days - (ledger[-1]["budget_remaining"] if ledger else budget_days),
            "budget_remaining": ledger[-1]["budget_remaining"] if ledger else budget_days,
            "not_charged_to_budget": [
                {"assignment_id": r["assignment_id"], "days_late": r["days_late"],
                 "reason": r["excluded_reason"]}
                for r in ledger if r["excluded_reason"] and r["days_late"] > 0],
            "penalties": applied})

    total_changes = sum(len(gd) for gd in grade_data.values())
    summary = {"course_id": course_id,
               "policy": {"budget_days": budget_days, "per_day_after": per_day_after,
                          "grace_minutes": grace_minutes, "floor": floor,
                          "assignments": [{"id": a, **meta[a]} for a in aids]},
               "students": student_reports, "total_penalties": total_changes}

    if total_changes == 0:
        summary["dry_run"] = True
        if not args.dry_run:
            summary["note"] = "No over-budget late penalties to apply."
        print(json.dumps(summary, indent=2))
        return

    print(f"{total_changes} student score(s) across {len(aids)} assignment(s) already "
          f"have a score and will be overwritten with a penalized one.", file=sys.stderr)
    if not should_write(args, what=f"{total_changes} penalized score(s) across "
                                   f"{len(aids)} assignment(s)"):
        summary["dry_run"] = True
        print(json.dumps(summary, indent=2))
        return

    # One log entry per assignment: each is its own async batch with its own
    # progress id, so that is the granularity an undo would work at.
    before_by_aid = {aid: {} for aid in aids}
    after_by_aid = {aid: {} for aid in aids}
    for rep in student_reports:
        for row in rep["penalties"]:
            before_by_aid[row["assignment_id"]][str(rep["user_id"])] = row["old_score"]
            after_by_aid[row["assignment_id"]][str(rep["user_id"])] = row["new_score"]

    progresses = []
    for aid in aids:
        if grade_data[aid]:
            prog = apply_grade_data(course_id, aid, grade_data[aid],
                                    args.course, args.override_mode) or {}
            log_action(args.course, "late-penalty-budget", aid,
                       before=before_by_aid[aid], after=after_by_aid[aid],
                       count=len(grade_data[aid]), budget_days=budget_days,
                       per_day_after=per_day_after,
                       progress=(prog or {}).get("id"))
            progresses.append({"assignment_id": aid, "progress_id": prog.get("id"),
                               "url": prog.get("url")})
    summary["dry_run"] = False
    summary["progress"] = progresses
    summary["note"] = "Bulk grading is async; poll each GET /progress/<id> until completed."
    print(json.dumps(summary, indent=2))


def main():
    # canvas_common.global_flags() puts --course / --course-id / --dry-run /
    # --live / --override-mode on a parent parser handed to BOTH the top-level
    # parser and every subparser. That is what makes `late_penalties.py budget
    # --config f --live` work -- argparse otherwise rejects a top-level flag
    # after the subcommand, and after the subcommand is where everybody types
    # it. apply_global_defaults fills in the ones argparse suppressed.
    common = global_flags()
    parser = argparse.ArgumentParser(description="Apply a late policy to graded work",
                                     parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(name, **kw):
        return sub.add_parser(name, parents=[common], **kw)

    pa = add_common("apply", help="Flat percent-per-day on one assignment")
    pa.add_argument("--assignment-id", type=int, required=True)
    pa.add_argument("--per-day", type=float, required=True,
                    help="Percent of points_possible deducted per late day")
    pa.add_argument("--max-days", type=int, default=0,
                    help="Cap the number of penalized days (0 = no cap)")
    pa.add_argument("--grace-minutes", type=int, default=0,
                    help="Lateness under this many minutes is not penalized")
    pa.add_argument("--floor", type=float, default=0,
                    help="Never drop an adjusted score below this (default 0)")

    pb = add_common("budget", help="Late-day budget across several assignments")
    pb.add_argument("--config", required=True, help="Path to a late-budget JSON file")

    args = apply_global_defaults(parser.parse_args())
    course_id = resolve_course_id(args.course, args.course_id)

    if args.command == "apply":
        cmd_apply(args, course_id)
    elif args.command == "budget":
        cmd_budget(args, course_id)


if __name__ == "__main__":
    main()
