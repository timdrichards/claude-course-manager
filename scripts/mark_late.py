#!/usr/bin/env python3
"""mark_late.py: analyze Gradescope submission times against the Canvas due
date and mark late submissions, accommodation-aware.

The Gradescope autograder scores work but knows nothing about the Canvas
deadline; Canvas knows the deadline but never saw the Gradescope submission
time (students submit on Gradescope, not through Canvas), so it can't tell a
late submission from an on-time one. This closes that gap: read each student's
Gradescope submission time from the CSV export, compare it to that student's
*effective* Canvas due date (base due date, or a later per-student override /
recorded accommodation), and mark the ones that are actually late.

Marking sets `late_policy_status = "late"` and `seconds_late_override` on the
Canvas submission. The point deduction itself is applied by Canvas's built-in
course late policy (Gradebook -> Settings), which must be enabled and set to
your syllabus rate -- this script verifies that and warns if it isn't. See
references/late-policy.md.

Canvas's built-in policy can express "N% per day (with a floor)" but NOT "late
allowed for only D days, then zero." When your syllabus caps late work, pass
--max-days D --after-max zero and this script applies the zero directly for
over-cap submissions (Canvas can't).

Accommodations are never auto-penalized. A student whose effective deadline is
extended (a Canvas per-student override, or an entry in --accommodations) and
who submitted within it is on-time. A student who is late even past their
extension, or who is marked exempt, is routed to `needs_review` and left
untouched for you to handle individually -- accommodations are individual by
nature (Safety Rule 4).

Every write is a per-student PUT through canvas.py, and every write is gated
twice: nothing is sent without --live, and against a course folder that folder's
config.json must also say "write_mode": "live" (or pass --override-mode).
Without --live you get the whole plan and no Canvas write. Marking late and
posting zeros are student-visible, and the batch is recorded in the course's
actions.log with each student's prior late status, score, and seconds-late
override, so it can be reversed.

Identity matching, CSV loading, and the gate come from canvas_common: this
script and sync_grades.py read the same CSV and must agree on who each row is,
which is now true because they call the same function rather than because two
copies were kept in step by hand.

Usage:
  mark_late.py grades.csv --course 326 --assignment-id 678 \
    --per-day 10 --max-days 2 --after-max zero
  mark_late.py grades.csv --course 326 --assignment-id 678 \
    --per-day 10 --max-days 2 --after-max zero --accommodations accoms.json --live

Course resolution: --course names a course folder (its canvas/config.json
supplies course_id and write_mode). --course-id overrides that id for a one-off;
with neither, $CANVAS_COURSE_ID is used.

--accommodations JSON (assembled by you from Canvas overrides + CLAUDE.md /
STUDENTS.md / a course accommodations file; the script also reads live Canvas
overrides on its own):
  {
    "default_tz": "America/New_York",
    "students": [
      {"email": "a@example.edu", "type": "extension",  "due_at": "2026-07-26T23:59:00-04:00", "note": "accommodation: 48h"},
      {"sid":   "12345678",    "type": "extra_days",  "days": 2, "note": "accommodation: flexible deadlines"},
      {"email": "b@example.edu", "type": "exempt", "note": "religious observance"}
    ]
  }

Column autodetection (override with flags):
  submission time : "Submission Time"
  lateness (fallback) : "Lateness (H:M:S)"
  email : "Email";  sid : "SID", "Student ID"
Matching precedence per row: email, else SID (vs sis_user_id), else login id --
literally the same function sync_grades.py uses.

Output: JSON summary on stdout. Errors: JSON on stderr, nonzero exit code.
"""

import argparse
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canvas_common import (  # noqa: E402
    EMAIL_CANDIDATES, SID_CANDIDATES, STATUS_CANDIDATES, apply_global_defaults,
    build_roster_maps, canvas_cli, canvas_get, die, global_flags, load_csv,
    load_json_file, log_action, match_row, pick_column, resolve_course_id,
    should_write,
)

# This script used to carry its own matcher called match_identity(email, sid,
# maps), kept in step with sync_grades' copy by hand and by a test. The copy is
# gone; the old name stays pointed at the one shared function so anything still
# reaching for mark_late.match_identity gets that and not a second copy. Note
# the signature is now match_row's: a row dict plus a column map.
match_identity = match_row

SUBTIME_CANDIDATES = ["Submission Time", "Submitted At", "Submission Date"]
LATENESS_CANDIDATES = ["Lateness (H:M:S)", "Lateness", "Lateness (H:M:S) "]

# The accommodations file names people by the same two keys the CSV does, so
# matching it reuses the CSV matcher with a one-line column map instead of a
# second, subtly different identity function.
ACCOM_COLS = {"email": "email", "sid": "sid"}


# --------------------------------------------------------------------------- #
# pure time / classification helpers (unit-testable, no Canvas)
# --------------------------------------------------------------------------- #

def system_utc_offset():
    """This machine's current UTC offset as '+HH:MM' / '-HH:MM'.

    Used as the default for naive timestamps instead of hardcoding one
    region's offset. It is the offset *right now*, so a naive timestamp from
    the other side of a DST boundary can be off by an hour -- pass an IANA
    zone (e.g. --tz America/New_York) when that matters.
    """
    off = datetime.now().astimezone().utcoffset() or timedelta(0)
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def parse_offset(off):
    """A tzinfo from '-04:00' | '-0400' | 'Z' | an IANA name. Defaults to UTC.

    An IANA name ('America/New_York', 'Europe/London') is DST-aware and is the
    correct choice when submissions straddle a clock change; a fixed offset is
    applied uniformly.
    """
    if off is None:
        return timezone.utc
    s = str(off).strip()
    if not s or s in ("Z", "z"):
        return timezone.utc
    if s[0] not in "+-":
        # Not offset-shaped: treat as an IANA zone name.
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(s)
        except Exception:
            die(f"Unrecognized --tz value: {s!r}",
                "Use an offset like -04:00, or an IANA zone like America/New_York.")
    s = s.replace(":", "")
    try:
        sign = 1 if s[0] == "+" else -1
        hh, mm = int(s[1:3]), int(s[3:5])
    except (ValueError, IndexError):
        die(f"Unrecognized --tz offset: {off!r}", "Expected a form like -04:00 or +0530.")
    return timezone(sign * timedelta(hours=hh, minutes=mm))


def parse_dt(raw, default_tz):
    """Parse an ISO or Gradescope datetime to an aware datetime, or None.

    Handles 'Z', +HH:MM / +HHMM offsets, 12- and 24-hour clocks, and 'T' or
    space date/time separators. A naive value gets `default_tz`.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace("T", " ")
    if s[-1] in ("Z", "z"):
        s = s[:-1] + "+0000"
    s = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", s)  # +04:00 -> +0400
    for f in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S%z",
              "%Y-%m-%d %I:%M:%S %p %z", "%Y-%m-%d %I:%M:%S %p%z",
              "%Y-%m-%d %H:%M %z", "%Y-%m-%d %H:%M%z"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    tz = parse_offset(default_tz)
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, f).replace(tzinfo=tz)
        except ValueError:
            pass
    return None


def parse_hms(raw):
    """Gradescope 'Lateness (H:M:S)' like '26:30:00' -> seconds, or None."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s or s in ("0", "00:00:00", "0:00:00"):
        return 0
    m = re.match(r"^(\d+):(\d{1,2}):(\d{1,2})$", s)
    if not m:
        return None
    h, mnt, sec = (int(x) for x in m.groups())
    return h * 3600 + mnt * 60 + sec


def late_days(seconds_late, grace_seconds):
    """Whole late days after a grace period, rounding any part-day up."""
    eff = (seconds_late or 0) - (grace_seconds or 0)
    if eff <= 0:
        return 0
    return math.ceil(eff / 86400)


def classify(seconds_late, accommodated, exempt, grace_seconds,
             max_days, after_max):
    """Decide what to do for one student. Pure; returns an action dict.

    action.kind:
      on_time            submitted on/before effective due -> ensure not late
      accommodated       has an extension and is on-time under it -> leave/clear
      needs_review       accommodated but late past extension, or exempt
      mark_late          late, within cap -> set late status + seconds override
      zero               late, over cap, after_max=zero -> post 0
      accept             late, over cap, after_max=accept -> mark late anyway
    """
    if exempt:
        return {"kind": "needs_review", "reason": "exempt"}
    d = late_days(seconds_late, grace_seconds)
    if d <= 0:
        # On time (or inside grace). Accommodated on-time is just on-time.
        return {"kind": "accommodated" if accommodated else "on_time",
                "days_late": 0}
    if accommodated:
        # Late even past their extended deadline: never auto-penalize.
        return {"kind": "needs_review", "reason": "late_past_accommodation",
                "days_late": d}
    if max_days and d > max_days:
        if after_max == "zero":
            return {"kind": "zero", "days_late": d, "over_by": d - max_days}
        if after_max == "accept":
            return {"kind": "accept", "days_late": d}
        return {"kind": "needs_review", "reason": "over_max_days",
                "days_late": d, "over_by": d - max_days}
    return {"kind": "mark_late", "days_late": d}


# --------------------------------------------------------------------------- #
# accommodations
# --------------------------------------------------------------------------- #

def load_accommodations(path, maps):
    """Resolve the --accommodations file to {uid: {type, due_at?, days?, note}}."""
    if not path:
        return {}, []
    cfg = load_json_file(path, what="--accommodations file")
    default_tz = cfg.get("default_tz")
    resolved, unresolved = {}, []
    for entry in cfg.get("students", []):
        uid, how = match_row(
            {"email": entry.get("email"), "sid": entry.get("sid")}, ACCOM_COLS, maps)
        ident = entry.get("email") or entry.get("sid") or "(unnamed)"
        if uid is None:
            unresolved.append({"identity": ident, "reason": how})
            continue
        resolved[uid] = {**entry, "_default_tz": default_tz}
    return resolved, unresolved


# --------------------------------------------------------------------------- #
# effective due date
# --------------------------------------------------------------------------- #

def effective_due(base_due, cached_due, accom, default_tz):
    """The latest deadline this student is entitled to, and its source.

    Later wins: base assignment date, a Canvas per-student override
    (cached_due_date), or a recorded accommodation extension/extra_days.
    Returns (due_dt_or_None, source, is_extended, is_exempt).
    """
    best = base_due
    source = "base"
    if cached_due and (best is None or cached_due > best):
        best, source = cached_due, "canvas_override"
    is_exempt = False
    if accom:
        atype = (accom.get("type") or "").strip().lower()
        if atype == "exempt":
            is_exempt = True
        elif atype == "extension" and accom.get("due_at"):
            d = parse_dt(accom["due_at"], accom.get("_default_tz") or default_tz)
            if d and (best is None or d > best):
                best, source = d, "accommodation_file"
        elif atype == "extra_days" and accom.get("days") and base_due:
            d = base_due + timedelta(days=float(accom["days"]))
            if best is None or d > best:
                best, source = d, "accommodation_file"
    is_extended = source in ("canvas_override", "accommodation_file")
    return best, source, is_extended, is_exempt


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main():
    # --course / --course-id / --dry-run / --live / --override-mode come from
    # canvas_common.global_flags() on a parent parser, so they work before OR
    # after the positional CSV path and read the same as in every other script
    # here. apply_global_defaults fills in the ones argparse suppressed.
    p = argparse.ArgumentParser(
        description="Mark late Gradescope submissions in Canvas, accommodation-aware",
        parents=[global_flags()])
    p.add_argument("csv_file", help="Path to a Gradescope grade export CSV (with a submission-time column)")
    p.add_argument("--assignment-id", type=int, required=True)
    p.add_argument("--per-day", type=float, default=None,
                   help="Syllabus late rate, %% of full marks per day (for the Canvas-policy check)")
    p.add_argument("--max-days", type=int, default=0,
                   help="Days late allowed before the after-max rule (0 = no cap)")
    p.add_argument("--after-max", choices=["flag", "zero", "accept"], default="flag",
                   help="Over the cap: flag for review (default), post zero, or accept as late")
    p.add_argument("--grace-minutes", type=int, default=0,
                   help="Lateness under this many minutes is treated as on-time")
    p.add_argument("--tz", default=system_utc_offset(),
                   help="Timezone for naive submission times / due dates: an offset "
                        "(-04:00) or an IANA zone (America/New_York). Defaults to this "
                        "machine's current offset. Prefer an IANA zone if submissions "
                        "straddle a daylight-saving change.")
    p.add_argument("--accommodations", help="Path to an accommodations JSON file")
    p.add_argument("--submission-time-column")
    p.add_argument("--lateness-column")
    p.add_argument("--email-column")
    p.add_argument("--sid-column")
    args = apply_global_defaults(p.parse_args())

    course_id = resolve_course_id(args.course, args.course_id)
    grace_seconds = args.grace_minutes * 60

    headers, rows = load_csv(args.csv_file)
    if not rows:
        die("CSV has no data rows")
    cols = {
        "subtime": pick_column(headers, args.submission_time_column,
                               SUBTIME_CANDIDATES, "submission-time", required=False),
        "lateness": pick_column(headers, args.lateness_column,
                                LATENESS_CANDIDATES, "lateness", required=False),
        "email": pick_column(headers, args.email_column, EMAIL_CANDIDATES, "email", required=False),
        "sid": pick_column(headers, args.sid_column, SID_CANDIDATES, "sid", required=False),
        "status": next((c for c in STATUS_CANDIDATES if c in headers), None),
    }
    if not cols["subtime"] and not cols["lateness"]:
        die("CSV has neither a submission-time nor a lateness column",
            {"available_columns": headers,
             "hint": "Export the per-assignment Gradescope CSV (Review Grades -> "
                     "Download Grades -> CSV); it includes 'Submission Time' and "
                     "'Lateness (H:M:S)'. Or pass --submission-time-column."})
    if not cols["email"] and not cols["sid"]:
        die("Need at least an email or SID column to match students",
            {"available_columns": headers})

    # Canvas: assignment (base due + points), roster, per-student submissions.
    # Fetch with all_dates=true: when any override exists, the plain `due_at`
    # field can reflect an override's date instead of the "Everyone else" base
    # date, which would silently poison every student's effective due date
    # (effective_due() takes the latest of base_due vs. cached_due, so a
    # base_due that's already the override's date makes cached_due never win).
    assignment = canvas_get(f"/courses/{course_id}/assignments/{args.assignment_id}",
                            course=args.course, params=["all_dates=true"],
                            all_pages=False)
    base_due_raw = assignment.get("due_at")
    for d in (assignment.get("all_dates") or []):
        if d.get("base"):
            base_due_raw = d.get("due_at")
            break
    base_due = parse_dt(base_due_raw, args.tz)
    points = assignment.get("points_possible")
    users = canvas_get(f"/courses/{course_id}/users", course=args.course,
                       params=["enrollment_type[]=student", "include[]=email"])
    maps = build_roster_maps(users)
    subs = canvas_get(
        f"/courses/{course_id}/assignments/{args.assignment_id}/submissions",
        course=args.course)
    cached_due = {}      # uid -> effective Canvas due date (reflects overrides)
    cur_status = {}      # uid -> current late_policy_status
    before_state = {}    # uid -> everything a write here could clobber
    for s in subs:
        uid = s.get("user_id")
        if uid is None:
            continue
        cached_due[uid] = parse_dt(s.get("cached_due_date"), args.tz)
        cur_status[uid] = s.get("late_policy_status")
        # The submissions read is already happening, so recording what each PUT
        # is about to overwrite costs nothing and is the only way the audit log
        # can describe an undo: a zero posted over a real score is not
        # recoverable from the summary alone.
        before_state[uid] = {"late_policy_status": s.get("late_policy_status"),
                             "seconds_late_override": s.get("seconds_late_override"),
                             "score": s.get("score")}

    accoms, accom_unresolved = load_accommodations(args.accommodations, maps)

    # Course late-policy preflight: marking late only deducts if the built-in
    # policy is enabled and matches the syllabus rate. Read-only warning here;
    # the full syllabus reconciliation lives in references/late-policy.md.
    policy, perr = canvas_cli(["get", f"/courses/{course_id}/late_policy"],
                              course=args.course)
    policy_warnings = []
    if perr is not None:
        policy_warnings.append("Could not read the course late policy; verify it "
                               "in Gradebook -> Settings so marked-late grades deduct.")
    else:
        lp = (policy or {}).get("late_policy", policy) or {}
        if not lp.get("late_submission_deduction_enabled"):
            policy_warnings.append("Canvas's built-in late policy is DISABLED — marking "
                                   "submissions late will not deduct any points until you "
                                   "enable it (see references/late-policy.md).")
        elif args.per_day is not None:
            rate = lp.get("late_submission_deduction")
            interval = lp.get("late_submission_interval")
            if interval != "day" or (rate is not None and float(rate) != float(args.per_day)):
                policy_warnings.append(
                    f"Canvas late policy is {rate}%/{interval}, but the syllabus rate you "
                    f"passed is {args.per_day}%/day — reconcile before relying on Canvas to "
                    "deduct (references/late-policy.md).")

    # Build the per-student plan.
    buckets = {"mark_late": [], "zero": [], "accept": [], "clear_late": [],
               "on_time": [], "accommodated_on_time": [], "needs_review": [],
               "unmatched": [], "no_submission_time": []}
    writes = []  # (uid, put_body, human)
    seen = set()
    for i, row in enumerate(rows):
        email = row.get(cols["email"], "") if cols["email"] else ""
        sid = row.get(cols["sid"], "") if cols["sid"] else ""
        uid, how = match_row(row, cols, maps)
        ident = (email or sid or row.get("Name") or f"row {i + 2}")
        status = (row.get(cols["status"]) or "").strip() if cols["status"] else ""
        if uid is None:
            buckets["unmatched"].append({"csv_identity": ident, "reason": how})
            continue
        if uid in seen:
            continue
        seen.add(uid)

        # Lateness: prefer submission time vs the student's effective due date;
        # fall back to Gradescope's own lateness column if there's no due date
        # or no submission time.
        accom = accoms.get(uid)
        due, due_src, extended, exempt = effective_due(
            base_due, cached_due.get(uid), accom, args.tz)
        subtime = parse_dt(row.get(cols["subtime"]), args.tz) if cols["subtime"] else None
        seconds_late = None
        basis = None
        if subtime is not None and due is not None:
            seconds_late = max(0, int((subtime - due).total_seconds()))
            basis = "submission_time_vs_effective_due"
        elif cols["lateness"]:
            hms = parse_hms(row.get(cols["lateness"]))
            if hms is not None:
                seconds_late = hms
                basis = "gradescope_lateness_column"
        if seconds_late is None:
            # Missing/never-submitted rows are sync_grades' concern, not ours.
            if status.lower() in ("missing", "") and not (row.get(cols["subtime"]) if cols["subtime"] else ""):
                buckets["no_submission_time"].append(
                    {"user_id": uid, "name": maps["name"].get(uid), "status": status or None})
            else:
                buckets["no_submission_time"].append(
                    {"user_id": uid, "name": maps["name"].get(uid),
                     "reason": "could_not_parse_time", "status": status or None})
            continue

        action = classify(seconds_late, extended, exempt, grace_seconds,
                          args.max_days, args.after_max)
        name = maps["name"].get(uid)
        common_fields = {"user_id": uid, "name": name, "seconds_late": seconds_late,
                         "days_late": action.get("days_late"), "basis": basis,
                         "effective_due": due.isoformat() if due else None,
                         "due_source": due_src}

        kind = action["kind"]
        if kind == "on_time":
            buckets["on_time"].append(common_fields)
            if cur_status.get(uid) == "late":  # stale from a prior run/resubmit
                writes.append((uid, {"submission": {"late_policy_status": "none"}},
                               f"{name}: on time now — clearing stale late status"))
                buckets["clear_late"].append(common_fields)
        elif kind == "accommodated":
            item = {**common_fields, "accommodation": due_src}
            buckets["accommodated_on_time"].append(item)
            if cur_status.get(uid) == "late":
                writes.append((uid, {"submission": {"late_policy_status": "none"}},
                               f"{name}: on time under accommodation — clearing stale late status"))
                buckets["clear_late"].append(item)
        elif kind == "needs_review":
            buckets["needs_review"].append(
                {**common_fields, "reason": action.get("reason"),
                 "accommodation": due_src if extended else action.get("reason"),
                 "note": (accom or {}).get("note")})
        elif kind in ("mark_late", "accept"):
            body = {"submission": {"late_policy_status": "late",
                                   "seconds_late_override": seconds_late}}
            buckets[kind].append(common_fields)
            writes.append((uid, body,
                           f"{name}: late {action['days_late']}d "
                           f"({seconds_late}s) — mark late, Canvas deducts"))
        elif kind == "zero":
            comment = (f"Submitted {action['days_late']} day(s) late; the syllabus "
                       f"accepts late work for {args.max_days} day(s), after which it "
                       f"is scored 0. ({action['over_by']} day(s) over.)")
            body = {"submission": {"posted_grade": "0", "late_policy_status": "late",
                                   "seconds_late_override": seconds_late},
                    "comment": {"text_comment": comment}}
            buckets["zero"].append({**common_fields, "over_by": action.get("over_by")})
            writes.append((uid, body,
                           f"{name}: late {action['days_late']}d — over cap, post 0"))

    students_without_row = [
        {"user_id": uid, "name": maps["name"][uid]}
        for uid in maps["name"] if uid not in seen]

    # A zero posted over an existing score is the destructive case in this
    # script; name it before the gate the way canvas_api.py names an overwrite.
    zeroed_over_a_score = [b for b in buckets["zero"]
                           if before_state.get(b["user_id"], {}).get("score") is not None]

    summary = {
        "course_id": course_id,
        "assignment": {"id": args.assignment_id, "name": assignment.get("name"),
                       "points_possible": points,
                       "base_due": base_due.isoformat() if base_due else None},
        "policy": {"per_day": args.per_day, "max_days": args.max_days,
                   "after_max": args.after_max, "grace_minutes": args.grace_minutes},
        "canvas_late_policy_warnings": policy_warnings,
        "accommodations_unresolved": accom_unresolved,
        "planned_writes": len(writes),
        "already_scored_would_be_overwritten": len(zeroed_over_a_score),
        "counts": {k: len(v) for k, v in buckets.items()},
        "mark_late": buckets["mark_late"],
        "zero": buckets["zero"],
        "accept": buckets["accept"],
        "clear_stale_late": buckets["clear_late"],
        "needs_review": buckets["needs_review"],
        "accommodated_on_time": buckets["accommodated_on_time"],
        "on_time_count": len(buckets["on_time"]),
        "unmatched_csv_rows": buckets["unmatched"],
        "no_submission_time": buckets["no_submission_time"],
        "canvas_students_without_a_csv_row": students_without_row,
    }

    if not writes:
        summary["dry_run"] = True
        if not args.dry_run:
            summary["note"] = "Nothing to mark: no late, un-accommodated submissions."
        print(json.dumps(summary, indent=2))
        return

    if zeroed_over_a_score:
        print(f"{len(zeroed_over_a_score)} of these already have a score and will be "
              f"overwritten with 0.", file=sys.stderr)
    if not should_write(args, what=f"{len(writes)} late-status change(s) on assignment "
                                   f"{args.assignment_id}"):
        summary["dry_run"] = True
        print(json.dumps(summary, indent=2))
        return

    # Apply: one PUT per student (Canvas has no bulk endpoint for
    # late_policy_status). canvas.py backs off on rate limits. The gate was
    # decided once above; live=True here carries that decision through.
    applied, failed = [], []
    base = f"/courses/{course_id}/assignments/{args.assignment_id}/submissions"
    for uid, body, human in writes:
        _, error = canvas_cli(["put", f"{base}/{uid}", "--json", json.dumps(body)],
                              course=args.course, live=True,
                              override=args.override_mode)
        if error is not None:
            failed.append({"user_id": uid, "error": error})
        else:
            applied.append({"user_id": uid, "did": human})

    # One log entry for the batch, holding the prior late status / score /
    # override of every student actually written. Per-write entries would be
    # noisier and no more reversible.
    if applied:
        applied_ids = {a["user_id"] for a in applied}
        log_action(args.course, "mark-late", args.assignment_id,
                   before={str(uid): before_state.get(uid) for uid in applied_ids},
                   after={str(uid): body["submission"]
                          for uid, body, _ in writes if uid in applied_ids},
                   count=len(applied), failed=len(failed),
                   csv_file=args.csv_file, after_max=args.after_max)

    summary["dry_run"] = False
    summary["applied"] = applied
    summary["applied_count"] = len(applied)
    summary["failed"] = failed
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
