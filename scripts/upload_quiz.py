#!/usr/bin/env python3
"""upload_quiz.py: create a Classic Quiz and its questions from a JSON file.

Reads a quiz bank JSON file (schema below, and in references/quizzes.md) and
drives canvas.py to create the quiz, then each question in order. The input is
plain JSON, so it can come from anywhere: hand-authored, exported from another
tool, or generated upstream. Never talks to Canvas directly -- every
request is delegated to canvas.py, the same way a human would call it, so
auth/pagination/retry logic lives in exactly one place.

Creating the quiz is a write, so it is gated like every other write here: it
needs --live, and against a course folder that folder's canvas/config.json must
also say "write_mode": "live". Publishing is part of the same create call, so
--publish is gated by the same switch -- there is no way to publish without
--live. Without --live you get the request that would have been sent, and
--dry-run is the same preview and wins if both are given. The created quiz is
appended to the course's actions.log so an undo knows what to delete.

Usage:
  upload_quiz.py NN-quiz.json --course 326
  upload_quiz.py NN-quiz.json --course 326 --dry-run
  upload_quiz.py NN-quiz.json --course 326 --live
  upload_quiz.py NN-quiz.json --course 326 --publish --live
  upload_quiz.py NN-quiz.json --course-id 12345 --live      # no course folder

Input shape:
  {
    "quiz": {"title": "...", "description": "...", "quiz_type": "practice_quiz"},
    "questions": [
      {"question_name": "Q1", "question_text": "...", "question_type": "...",
       "points_possible": 1, "answers": [{"answer_text": "...", "answer_weight": 100}]}
    ]
  }

Behavior: stops on the first failed request rather than skipping and
continuing -- a half-created quiz is worse than a half-cached page set, so
partial progress is reported, not silently papered over. New quizzes default
to unpublished (Safety Rule 2 in SKILL.md) unless the input JSON
sets "published" explicitly or --publish is given.

Output: JSON summary on stdout. Errors: JSON on stderr, nonzero exit code.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canvas_common  # noqa: E402

die = canvas_common.die


def load_quiz_bank(path):
    data = canvas_common.load_json_file(path, what="Quiz bank file")
    if "quiz" not in data or "questions" not in data:
        die("Quiz bank file must have top-level 'quiz' and 'questions' keys")
    if not isinstance(data["questions"], list) or not data["questions"]:
        die("'questions' must be a non-empty array")
    return data


def call_canvas(method, path, payload, args, live):
    """One canvas.py write. When the gate said no, --dry-run makes canvas.py echo
    the request on stdout instead of leaving stdout empty for us to fail to parse."""
    cli = [method, path, "--json", json.dumps(payload)]
    if not live:
        cli.append("--dry-run")
    return canvas_common.canvas_cli(cli, course=args.course, live=live,
                                    override=args.override_mode)


def main():
    common = canvas_common.global_flags()
    parser = argparse.ArgumentParser(
        description="Create a Classic Quiz and its questions from a JSON file",
        parents=[common])
    parser.add_argument("quiz_bank_file", help="Path to a quiz bank JSON file")
    parser.add_argument("--publish", action="store_true",
                        help="Publish the quiz (default: unpublished, per Safety Rule 2)")
    args = canvas_common.apply_global_defaults(parser.parse_args())
    course_id = canvas_common.resolve_course_id(args.course, args.course_id)

    bank = load_quiz_bank(args.quiz_bank_file)
    quiz_payload = dict(bank["quiz"])
    if args.publish:
        quiz_payload["published"] = True
    elif "published" not in quiz_payload:
        quiz_payload["published"] = False

    # Publishing rides along on the create call, so there is no second gate for
    # it: the one below covers both, and a quiz cannot become visible to students
    # without --live having been passed.
    live = canvas_common.should_write(
        args, "the quiz" + (" (published)" if quiz_payload.get("published") else ""))

    quiz_path = f"/courses/{course_id}/quizzes"
    quiz_response, error = call_canvas("post", quiz_path, {"quiz": quiz_payload},
                                       args, live)
    if error is not None:
        die("Failed to create quiz", error)

    if not live:
        print(json.dumps({
            "dry_run": True,
            "course_id": course_id,
            "quiz": quiz_payload,
            "request": quiz_response,
            "questions_planned": len(bank["questions"]),
        }, indent=2))
        return

    quiz_id = quiz_response.get("id")
    if not quiz_id:
        die("canvas.py did not return a quiz id", quiz_response)

    questions_path = f"/courses/{course_id}/quizzes/{quiz_id}/questions"
    succeeded, failed = [], None
    for index, question in enumerate(bank["questions"]):
        response, error = call_canvas("post", questions_path, {"question": question},
                                      args, live=True)
        if error is not None:
            failed = {"index": index, "question_name": question.get("question_name"),
                      "detail": error}
            break
        succeeded.append({
            "index": index,
            "question_name": question.get("question_name"),
            "id": response.get("id"),
        })

    # One log line for the quiz, not one per question: the questions live inside
    # the quiz, so deleting the quiz reverses all of it. There is no before-value
    # -- the quiz did not exist -- and inventing one would be worse than None.
    canvas_common.log_action(
        args.course, "quiz-create", quiz_id, before=None,
        after={"title": quiz_response.get("title"),
               "published": quiz_response.get("published"),
               "html_url": quiz_response.get("html_url"),
               "questions_created": len(succeeded)},
        course_id=course_id)

    print(json.dumps({
        "dry_run": False,
        "course_id": course_id,
        "quiz": {
            "id": quiz_id,
            "title": quiz_response.get("title"),
            "html_url": quiz_response.get("html_url"),
            "published": quiz_response.get("published"),
        },
        "questions_succeeded": succeeded,
        "questions_failed": failed,
        "questions_total": len(bank["questions"]),
    }, indent=2))

    if failed is not None:
        sys.exit(2)


if __name__ == "__main__":
    main()
