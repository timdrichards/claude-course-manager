#!/usr/bin/env python3
"""rubric.py: create real Canvas rubrics and grade with them, through the API.

Two subcommands, one for each half of the rubric lifecycle:

  create   Build a rubric from a JSON file and (optionally) attach it to an
           assignment for grading, so it shows up in SpeedGrader and drives
           the score. Handles the indexed-hash encoding Canvas's create-rubric
           endpoint demands (criteria[0][ratings][0][points], NOT an array).

  grade    Apply per-criterion scores/comments to student submissions on an
           assignment that already has a rubric. Resolves human-readable
           criterion and rating names to the opaque ids Canvas requires, so a
           grader never has to look them up by hand. When the rubric is
           attached with use_for_grading, Canvas sums the criteria into the
           submission score automatically.

Like upload_quiz.py, this never talks to Canvas directly -- every request is
delegated to canvas.py so auth, pagination, retry, and encoding live in one
place. Writes use --form because the rubric endpoints are unreliable with JSON
bodies and need bracket-encoded, index-keyed params.

Both writing subcommands are gated the same way every write in this plugin is:
nothing reaches Canvas without --live, and when the run is pointed at a course
folder that folder's canvas/config.json must also say "write_mode": "live".
Without --live you get the request that would have been sent. --dry-run is the
same preview, and beats --live if both are given. Every write that does land is
appended to the course's actions.log, with the previous rubric assessment where
one existed, because that is the only thing an undo can be reconstructed from.

Usage:
  rubric.py create rubric.json --course 326
  rubric.py create rubric.json --course 326 --assignment-id 678 --use-for-grading --live
  rubric.py create rubric.json --course 326 --assignment-id 678 --dry-run

  rubric.py grade grades.json --course 326 --assignment-id 678 --live
  rubric.py grade grades.json --course 326 --assignment-id 678 --dry-run
  rubric.py grade grades.json --course-id 12345 --assignment-id 678   # no folder

Input shape for `create` (see references/rubrics.md for the full schema):
  {
    "rubric": {
      "title": "HW7 Rubric",
      "free_form_criterion_comments": false,
      "criteria": [
        {"description": "Correctness", "long_description": "...", "points": 20,
         "ratings": [
           {"description": "Full marks", "points": 20},
           {"description": "Partial",    "points": 10},
           {"description": "No marks",   "points": 0}
         ]}
      ]
    },
    "association": {                 // optional; also settable via CLI flags
      "assignment_id": 678,
      "use_for_grading": true,
      "hide_score_total": false,
      "hide_points": false,
      "purpose": "grading"
    }
  }

Input shape for `grade`:
  {
    "grades": [
      {"user_id": 11111, "comment": "Nice work overall",
       "criteria": {
          "Correctness": {"points": 18, "comments": "One edge case missed"},
          "Style":       {"rating": "Full marks"},
          "Docs":        {"points": 5}
       }}
    ]
  }
  Each key under "criteria" is a criterion description (or its id). A value may
  give "points" and/or a "rating" name; a bare "rating" pulls that rating's
  points. Matching a known rating id also highlights the cell in SpeedGrader.

Output: JSON summary on stdout. Errors: JSON on stderr, nonzero exit code.
Partial failures stop and report rather than pressing on (a half-graded roster
is worse reported than hidden), matching upload_quiz.py's fail-fast stance.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canvas_common  # noqa: E402

die = canvas_common.die


# --------------------------------------------------------------------------- #
# create
# --------------------------------------------------------------------------- #

def build_rubric_payload(data, assignment_id=None, use_for_grading=None):
    """Turn the author-friendly rubric JSON into Canvas's index-keyed payload.

    Canvas's POST /rubrics wants criteria as a hash keyed by string index
    (criteria[0], criteria[1]) with ratings likewise, NOT a JSON array -- an
    array loses the index that ties each rating to its criterion. We build a
    plain dict with "0"/"1"/... keys; canvas.py --form flattens that to the
    exact bracket notation Canvas parses. Returns (payload, criteria_summary).
    """
    rubric_in = data.get("rubric")
    if not isinstance(rubric_in, dict):
        die("Input must have a 'rubric' object")
    criteria_in = rubric_in.get("criteria")
    if not isinstance(criteria_in, list) or not criteria_in:
        die("rubric.criteria must be a non-empty array")

    criteria_hash = {}
    summary = []
    total_points = 0
    for i, crit in enumerate(criteria_in):
        if "description" not in crit or "points" not in crit:
            die(f"criteria[{i}] needs at least 'description' and 'points'")
        entry = {
            "description": crit["description"],
            "points": crit["points"],
        }
        if crit.get("long_description") is not None:
            entry["long_description"] = crit["long_description"]
        if crit.get("id") is not None:  # let the author pin an id if they want
            entry["id"] = crit["id"]

        ratings_in = crit.get("ratings") or []
        if ratings_in:
            ratings_hash = {}
            for j, rating in enumerate(ratings_in):
                if "description" not in rating or "points" not in rating:
                    die(f"criteria[{i}].ratings[{j}] needs 'description' and 'points'")
                r = {"description": rating["description"], "points": rating["points"]}
                if rating.get("long_description") is not None:
                    r["long_description"] = rating["long_description"]
                ratings_hash[str(j)] = r
            entry["ratings"] = ratings_hash

        criteria_hash[str(i)] = entry
        total_points += crit["points"] or 0
        summary.append({"index": i, "description": crit["description"],
                        "points": crit["points"], "ratings": len(ratings_in)})

    rubric_payload = {
        "title": rubric_in.get("title", "Rubric"),
        "criteria": criteria_hash,
    }
    for flag in ("free_form_criterion_comments", "hide_score_total", "points_possible"):
        if rubric_in.get(flag) is not None:
            rubric_payload[flag] = rubric_in[flag]

    payload = {"rubric": rubric_payload}

    assoc_in = dict(data.get("association") or {})
    if assignment_id is not None:
        assoc_in["assignment_id"] = assignment_id
    if use_for_grading is not None:
        assoc_in["use_for_grading"] = use_for_grading

    if assoc_in.get("assignment_id"):
        association = {
            "association_type": "Assignment",
            "association_id": assoc_in["assignment_id"],
            # purpose MUST be "grading" for the rubric to attach for scoring and
            # appear in SpeedGrader; "bookmark" just saves it to the course.
            "purpose": assoc_in.get("purpose", "grading"),
        }
        if assoc_in.get("use_for_grading") is not None:
            association["use_for_grading"] = assoc_in["use_for_grading"]
        for flag in ("hide_score_total", "hide_points", "hide_outcome_results",
                     "bookmarked"):
            if assoc_in.get(flag) is not None:
                association[flag] = assoc_in[flag]
        payload["rubric_association"] = association

    return payload, {"criteria": summary, "total_points": total_points,
                     "associated_assignment": assoc_in.get("assignment_id")}


def cmd_create(args, course_id):
    data = canvas_common.load_json_file(args.spec_file, what="Rubric file")
    json_assignment = (data.get("association") or {}).get("assignment_id")
    if args.use_for_grading and args.assignment_id is None and not json_assignment:
        die("--use-for-grading needs an assignment",
            "Pass --assignment-id or set association.assignment_id in the JSON")
    use_for_grading = True if args.use_for_grading else None
    payload, summary = build_rubric_payload(
        data, assignment_id=args.assignment_id, use_for_grading=use_for_grading)

    path = f"/courses/{course_id}/rubrics"
    cli = ["post", path, "--form", "--json", json.dumps(payload)]

    # The gate first, the request second. Refused writes die inside should_write;
    # a plain preview falls through to canvas.py --dry-run, which echoes the
    # fully form-encoded request -- the only way to see the indexed-hash encoding
    # before it goes out.
    if not canvas_common.should_write(args, "the rubric"):
        response, error = canvas_common.canvas_cli(cli + ["--dry-run"],
                                                   course=args.course)
        if error is not None:
            die("Failed to build the rubric request", error)
        print(json.dumps({"dry_run": True, "course_id": course_id,
                          "plan": summary, "request": response}, indent=2))
        return

    response, error = canvas_common.canvas_cli(
        cli, course=args.course, live=True, override=args.override_mode)
    if error is not None:
        die("Failed to create rubric", error)

    # POST /rubrics returns {"rubric": {..., "data": [criteria]}, "rubric_association": {...}}
    rubric = response.get("rubric", response) if isinstance(response, dict) else {}
    criteria_out = []
    for crit in rubric.get("data", []) or []:
        criteria_out.append({
            "id": crit.get("id"),
            "description": crit.get("description"),
            "points": crit.get("points"),
            "ratings": [{"id": r.get("id"), "description": r.get("description"),
                         "points": r.get("points")} for r in crit.get("ratings", []) or []],
        })

    assoc = response.get("rubric_association") if isinstance(response, dict) else None

    # No before-value exists: this rubric did not exist a moment ago. Recording
    # None is the honest entry; the undo for a creation is a deletion, and the
    # log says what to delete.
    canvas_common.log_action(
        args.course, "rubric-create", rubric.get("id") or path,
        before=None,
        after={"title": rubric.get("title"),
               "points_possible": rubric.get("points_possible"),
               "criteria": len(criteria_out),
               "assignment_id": (assoc or {}).get("association_id")},
        course_id=course_id)

    print(json.dumps({
        "dry_run": False,
        "course_id": course_id,
        "rubric": {"id": rubric.get("id"), "title": rubric.get("title"),
                   "points_possible": rubric.get("points_possible")},
        "association": {
            "id": (assoc or {}).get("id"),
            "assignment_id": (assoc or {}).get("association_id"),
            "use_for_grading": (assoc or {}).get("use_for_grading"),
            "purpose": (assoc or {}).get("purpose"),
        } if assoc else None,
        "criteria": criteria_out,
    }, indent=2))


# --------------------------------------------------------------------------- #
# grade
# --------------------------------------------------------------------------- #

def fetch_rubric_for_assignment(course, course_id, assignment_id):
    """Return the assignment's rubric criteria list, or die with guidance."""
    path = f"/courses/{course_id}/assignments/{assignment_id}"
    response, error = canvas_common.canvas_cli(
        ["get", path, "--param", "include[]=rubric"], course=course)
    if error is not None:
        die("Failed to read assignment", error)
    rubric = (response or {}).get("rubric")
    if not rubric:
        die("Assignment has no rubric attached",
            "Attach one first with `rubric.py create ... --assignment-id "
            f"{assignment_id} --use-for-grading`. If a rubric exists but isn't "
            "showing, its association purpose may be 'bookmark' rather than 'grading'.")
    settings = (response or {}).get("rubric_settings") or {}
    return rubric, settings


def fetch_prior_assessments(course, course_id, assignment_id):
    """Current score and rubric assessment per user, for the audit log's `before`.

    One extra paginated read buys a reconstructible undo: without the previous
    assessment the log can say what a criterion became but not what it was, and
    regrading over an existing assessment is exactly the write someone wants to
    reverse. If the read fails the grading still proceeds -- a missing before is
    a worse log, not a reason to refuse to grade -- and the caller records None.
    """
    subs, error = canvas_common.canvas_cli(
        ["get", f"/courses/{course_id}/assignments/{assignment_id}/submissions",
         "--all", "--param", "include[]=rubric_assessment"], course=course)
    if error is not None:
        print(json.dumps({"warning": "could not read existing rubric assessments; "
                                     "the audit log will have no before-values",
                          "detail": error}), file=sys.stderr)
        return {}
    prior = {}
    for sub in subs or []:
        uid = sub.get("user_id")
        if uid is None:
            continue
        prior[str(uid)] = {"score": sub.get("score"),
                           "rubric_assessment": sub.get("rubric_assessment")}
    return prior


def build_criterion_index(rubric):
    """Map criterion description AND id -> its record; flag ambiguous names."""
    by_key = {}
    ambiguous = set()
    for crit in rubric:
        cid = crit.get("id")
        desc = crit.get("description")
        record = {
            "id": cid,
            "description": desc,
            "points": crit.get("points"),
            "ratings": crit.get("ratings", []) or [],
        }
        if cid is not None:
            by_key[str(cid)] = record
        if desc is not None:
            if desc in by_key and by_key[desc]["id"] != cid:
                ambiguous.add(desc)
            by_key[desc] = record
    return by_key, ambiguous


def resolve_rating(record, spec):
    """Given a per-criterion grade spec, return (points, rating_id).

    Precedence: an explicit "points" wins for the score; a named "rating"
    supplies points when none given and always tries to set rating_id so the
    matching cell highlights in SpeedGrader. If only points are given, match a
    rating with equal points to still highlight the cell.
    """
    points = spec.get("points")
    rating_id = None
    ratings = record["ratings"]

    if spec.get("rating") is not None:
        match = next((r for r in ratings if r.get("description") == spec["rating"]), None)
        if match is None:
            names = [r.get("description") for r in ratings]
            die(f"No rating named {spec['rating']!r} on criterion "
                f"{record['description']!r}", {"available_ratings": names})
        rating_id = match.get("id")
        if points is None:
            points = match.get("points")

    if points is None:
        die(f"Grade for criterion {record['description']!r} needs 'points' or 'rating'")

    if rating_id is None:
        exact = next((r for r in ratings if r.get("points") == points), None)
        if exact is not None:
            rating_id = exact.get("id")

    return points, rating_id


def build_assessment(entry, index, ambiguous):
    """Build the rubric_assessment dict (keyed by criterion id) for one student.

    Returns (user_id, assessment, resolved_summary). Raises via die() on any
    unmatched criterion so a typo can't silently drop a score.
    """
    user_id = entry.get("user_id")
    if user_id is None:
        die("Each grade entry needs a 'user_id'")
    criteria = entry.get("criteria") or {}
    if not criteria:
        die(f"Grade entry for user {user_id} has no 'criteria'")

    assessment = {}
    resolved = []
    total = 0
    for key, spec in criteria.items():
        if key in ambiguous:
            die(f"Criterion description {key!r} is ambiguous (two criteria share "
                "it); key this grade by criterion id instead.")
        record = index.get(str(key)) or index.get(key)
        if record is None:
            die(f"No criterion matching {key!r} on this assignment's rubric",
                {"known_criteria": sorted({v['description'] for v in index.values()
                                           if v.get('description')})})
        if not isinstance(spec, dict):
            spec = {"points": spec}  # allow a bare number shorthand
        points, rating_id = resolve_rating(record, spec)
        cell = {"points": points}
        if rating_id is not None:
            cell["rating_id"] = rating_id
        if spec.get("comments") is not None:
            cell["comments"] = spec["comments"]
        assessment[record["id"]] = cell
        total += points or 0
        resolved.append({"criterion": record["description"], "criterion_id": record["id"],
                         "points": points, "rating_id": rating_id})

    return user_id, assessment, {"user_id": user_id, "criteria": resolved,
                                 "computed_total": total}


def cmd_grade(args, course_id):
    data = canvas_common.load_json_file(args.grades_file, what="Grades file")
    grades = data.get("grades")
    if not isinstance(grades, list) or not grades:
        die("Input must have a non-empty 'grades' array")

    rubric, _settings = fetch_rubric_for_assignment(
        args.course, course_id, args.assignment_id)
    index, ambiguous = build_criterion_index(rubric)

    # Resolve every entry before sending any of them, for the same reason
    # groups.py resolves every member first: a typo in the last entry should
    # abort the batch, not stop it halfway through the roster.
    plans = []
    for entry in grades:
        user_id, assessment, summary = build_assessment(entry, index, ambiguous)
        payload = {"rubric_assessment": assessment}
        if entry.get("comment"):
            payload["comment"] = {"text_comment": entry["comment"]}
        plans.append((user_id, payload, summary))

    if not canvas_common.should_write(args, f"{len(plans)} rubric assessment(s)"):
        print(json.dumps({"dry_run": True, "course_id": course_id,
                          "assignment_id": args.assignment_id,
                          "will_grade": [p[2] for p in plans]}, indent=2))
        return

    prior = fetch_prior_assessments(args.course, course_id, args.assignment_id)

    succeeded, failed = [], None
    for user_id, payload, summary in plans:
        path = f"/courses/{course_id}/assignments/{args.assignment_id}/submissions/{user_id}"
        response, error = canvas_common.canvas_cli(
            ["put", path, "--form", "--json", json.dumps(payload)],
            course=args.course, live=True, override=args.override_mode)
        if error is not None:
            failed = {"user_id": user_id, "detail": error}
            break
        # One log line per student, not one per batch: the writes are per-student
        # PUTs, and an undo wants the same granularity the write had.
        canvas_common.log_action(
            args.course, "rubric-grade", f"{args.assignment_id}/{user_id}",
            before=prior.get(str(user_id)),
            after={"score": (response or {}).get("score"),
                   "rubric_assessment": payload["rubric_assessment"]},
            course_id=course_id)
        succeeded.append({
            "user_id": user_id,
            "score": (response or {}).get("score"),
            "grade": (response or {}).get("grade"),
            "computed_total": summary["computed_total"],
        })

    print(json.dumps({
        "dry_run": False,
        "course_id": course_id,
        "assignment_id": args.assignment_id,
        "graded": succeeded,
        "failed": failed,
        "total": len(plans),
    }, indent=2))
    if failed is not None:
        sys.exit(2)


def main():
    common = canvas_common.global_flags()
    parser = argparse.ArgumentParser(
        description="Create Canvas rubrics and grade with them", parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", parents=[common],
                              help="Create a rubric and optionally attach it to an assignment")
    p_create.add_argument("spec_file", help="Path to a rubric JSON file")
    p_create.add_argument("--assignment-id", type=int, default=None,
                          help="Attach the rubric to this assignment")
    p_create.add_argument("--use-for-grading", action="store_true",
                          help="Make the rubric drive the assignment score (implies attachment)")

    p_grade = sub.add_parser("grade", parents=[common],
                             help="Apply rubric scores to submissions")
    p_grade.add_argument("grades_file", help="Path to a grades JSON file")
    p_grade.add_argument("--assignment-id", type=int, required=True,
                         help="Assignment whose rubric to grade against")

    args = canvas_common.apply_global_defaults(parser.parse_args())
    course_id = canvas_common.resolve_course_id(args.course, args.course_id)

    if args.command == "create":
        cmd_create(args, course_id)
    elif args.command == "grade":
        cmd_grade(args, course_id)


if __name__ == "__main__":
    main()
