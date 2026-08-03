# Quizzes

The single most important fact: **Canvas has two quiz engines with two
different APIs**, and they are not interchangeable.

| | Classic Quizzes | New Quizzes |
|---|---|---|
| REST base | `/api/v1/courses/:id/quizzes` | `/api/quiz/v1/courses/:id/quizzes` |
| API maturity | Full CRUD, question banks, submissions, statistics | Limited: quiz CRUD and items, weaker reporting |
| Underlying object | Its own Quiz object plus a shadow assignment | An assignment with `submission_types: ["external_tool"]` (LTI) |
| Student answer export via API | Yes (submission questions, quiz reports) | Mostly no; use the UI or Reports LTI |
| Status | Deprecated by Instructure but still widely used | The replacement |

## Default to Classic Quizzes

**When creating a quiz, always recommend and default to Classic Quizzes**, and
say why: Classic Quizzes has a complete REST API this plugin can drive
end-to-end — create the quiz and questions, read submissions, and export
per-student, per-question answer data. New Quizzes does **not** have a
completed API: there is no public endpoint to download student quiz
submissions or answer data, so anything built on New Quizzes cannot later be
graded, audited, or exported programmatically.

So, unless the user explicitly asks for New Quizzes:

- Create every new quiz as a Classic Quiz (`/api/v1/courses/:id/quizzes`).
- If the user just says "quiz," proceed with Classic — no need to stop and ask
  which engine — but mention in your response that you used Classic and why.
- If the user explicitly wants New Quizzes, tell them the answer-export
  limitation first and confirm they still want it before proceeding; if they
  need programmatic access to submissions, steer them back to Classic.

Determining which engine an **existing** quiz uses still matters (for reads and
edits): a New Quiz appears in `/courses/:course/assignments` with
`is_quiz_lti_assignment: true` (or `external_tool` submission type), while a
Classic Quiz appears in `/courses/:course/quizzes`.

## Classic Quizzes

### List / read

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/quizzes --all
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/quizzes/<id>
```

### Create

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/quizzes --json '{
  "quiz": {
    "title": "Week 5 Reading Quiz",
    "description": "<p>Covers chapters 7 and 8.</p>",
    "quiz_type": "assignment",
    "time_limit": 20,
    "shuffle_answers": true,
    "allowed_attempts": 1,
    "scoring_policy": "keep_highest",
    "due_at": "2026-09-18T23:59:00-04:00",
    "published": false
  }
}' --live
```

`quiz_type`: `assignment` (graded), `practice_quiz`, `graded_survey`, `survey`.

### Questions

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/quizzes/<qid>/questions --json '{
  "question": {
    "question_name": "Q1",
    "question_text": "<p>What does HTTP status 422 mean?</p>",
    "question_type": "multiple_choice_question",
    "points_possible": 2,
    "answers": [
      {"answer_text": "Unprocessable entity", "answer_weight": 100},
      {"answer_text": "Unauthorized", "answer_weight": 0},
      {"answer_text": "Not found", "answer_weight": 0}
    ]
  }
}' --live
```

Question types include `multiple_choice_question`, `true_false_question`,
`short_answer_question` (fill in the blank), `essay_question`,
`matching_question`, `multiple_answers_question`, `numerical_question`,
`fill_in_multiple_blanks_question`, `multiple_dropdowns_question`,
`calculated_question`, `file_upload_question`, `text_only_question`.
Correct answers get `answer_weight: 100`, wrong ones `0`.

Essay questions land in the gradebook as `pending_review`, not `graded`, until
someone reads them — which is why a grading queue counted on
`workflow_state=submitted` alone misses them (`submissions-grades.md`).

After adding or editing questions on a published quiz, Canvas requires
"saving" the quiz again for students to see changes: PUT the quiz with
`"quiz": {"notify_of_update": false}` to bump it.

### Bulk-creating from a JSON file

For creating a quiz plus a full set of questions in one go — from a question
bank you wrote by hand, exported from another tool, or generated upstream —
use `upload_quiz.py` instead of composing individual `canvas.py post` calls:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/upload_quiz.py NN-quiz.json --course 326 --dry-run
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/upload_quiz.py NN-quiz.json --course 326 --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/upload_quiz.py NN-quiz.json --course 326 --publish --live
```

Expected input shape — this is the authoritative schema (top-level `quiz`
object matching the Create payload above, `questions` array matching the
Questions payload above):

```json
{
  "quiz": {"title": "...", "description": "...", "quiz_type": "practice_quiz"},
  "questions": [
    {"question_name": "Q1", "question_text": "...", "question_type": "multiple_choice_question",
     "points_possible": 1, "answers": [{"answer_text": "...", "answer_weight": 100}]}
  ]
}
```

The script stops on the first failed question request rather than skipping
and continuing, and reports which questions succeeded before the failure.
New quizzes default to unpublished (Safety Rule 2) unless the input JSON
sets `"published": true` or `--publish` is passed. Publishing happens inside
the same create call, so `--publish` is gated by the same `--live` switch —
there is no way to publish without it. The created quiz is appended to the
course's `actions.log` so an undo knows what to delete.

### Question groups (randomization)

Random selection from a pool uses question groups:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/quizzes/<qid>/groups --json '{
  "quiz_groups": [{"name": "Pool A", "pick_count": 5, "question_points": 2}]
}' --live
```

Then create questions with `quiz_group_id` set, or link a question bank
(`assessment_question_bank_id`). Caveat: the Question Banks themselves have
almost no public API; banks must generally be built in the UI or by creating
questions directly in groups.

### Submissions and answer data

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/quizzes/<qid>/submissions --all
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/quizzes/<qid>/statistics
```

Per-question answer breakdowns come from `/statistics` (aggregate) or the
quiz reports endpoint (`student_analysis` CSV):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/quizzes/<qid>/reports \
    --json '{"quiz_report": {"report_type": "student_analysis"}}' --live
# Poll the returned id until file.url appears, then download that URL.
```

The student_analysis CSV is the most complete per-student per-question export
Classic Quizzes offers. It is also a file full of student answers — see
"Student data on disk" in the plugin README before saving it anywhere.

## New Quizzes

Base path differs and is NOT under `/api/v1`. `canvas.py` handles this because
the path already starts with `/api/`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /api/quiz/v1/courses/:course/quizzes --all
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /api/quiz/v1/courses/:course/quizzes --json '{
  "quiz": {
    "title": "Week 5 Quiz",
    "points_possible": 10,
    "due_at": "2026-09-18T23:59:00-04:00",
    "quiz_settings": {"shuffle_answers": true, "session_time_limit_in_seconds": 1200}
  }
}' --live
```

Items (questions) go through `/api/quiz/v1/courses/:course/quizzes/<id>/items`
with a substantially different, more nested payload (`entry.interaction_type_slug`
such as `choice`, `essay`, `numeric`; `scoring_data` for the key). Fetch one
existing item first and mirror its shape rather than guessing.

Hard limitations to tell the user about up front:
- No public API for per-student answer data or item analysis; exports happen
  through the New Quizzes UI.
- Grades flow to the gradebook through the shadow assignment; grade changes
  go through the normal Submissions API against that assignment id.
- Some settings (accommodations/moderation) are UI only.

Because of the missing submission/answer-export API, **do not create New
Quizzes by default** — see "Default to Classic Quizzes" above. Only build one
here when the user explicitly asks for New Quizzes after being told they
cannot download student submissions or answer data through the API.

New Quizzes paths are the least-exercised part of this plugin. Treat a
surprising response here as more likely to be an undocumented quirk than
elsewhere, and say so rather than asserting.
