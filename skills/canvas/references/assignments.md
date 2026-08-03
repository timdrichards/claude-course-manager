# Assignments

Canvas API docs: Assignments, Assignment Groups, Assignment Overrides.

The assignments skill writes the spec; this file is how it lands in Canvas. For
a plain create from a JSON file of Canvas fields, `canvas_api.py --course 326
create-assignment --file spec.json --live` is the shorter path; everything
below is the general surface underneath it.

## List and read

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignments --all
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignments --all --param search_term=HW
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignments/<id> --param "include[]=overrides"
```

Useful list params:
- `search_term=<str>` partial name match
- `bucket=upcoming|past|undated|ungraded|unsubmitted|overdue` server-side filters
- `include[]=all_dates` returns every override date, not just the base date
- `order_by=due_at|position|name`

Key fields on an assignment object: `id`, `name`, `description` (HTML),
`points_possible`, `due_at`, `unlock_at`, `lock_at`, `published`,
`submission_types`, `allowed_extensions`, `assignment_group_id`, `position`,
`grading_type`, `omit_from_final_grade`, `html_url`.

## Create

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/assignments --json '{
  "assignment": {
    "name": "HW7: Middleware and Observability",
    "description": "<p>Instructions here. HTML is allowed.</p>",
    "points_possible": 50,
    "due_at": "2026-09-18T23:59:00-04:00",
    "unlock_at": "2026-09-11T00:00:00-04:00",
    "submission_types": ["online_upload"],
    "allowed_extensions": ["pdf", "zip"],
    "assignment_group_id": 4567,
    "published": false
  }
}' --live
```

- `submission_types` values: `online_upload`, `online_text_entry`, `online_url`,
  `media_recording`, `on_paper`, `external_tool`, `none`, `not_graded`,
  `discussion_topic`, `online_quiz`. It is an array even for one type.
- `grading_type`: `points` (default), `percent`, `pass_fail`, `letter_grade`,
  `gpa_scale`, `not_graded`.
- `allowed_extensions` is only meaningful with `online_upload`.
- `description` is raw HTML. Markdown is not rendered; convert first.
- `published` — leave false while drafting. Publishing makes the assignment
  visible to students, and depending on course notification settings may also
  notify them.

### Dates

`due_at` is the deadline. `lock_at` is when submission becomes impossible, and
it can be later — that gap is how a late window is expressed. `unlock_at` is
when students can start.

All three take ISO 8601 with an **explicit offset** (`-04:00`), not a naive
local time and not a `Z` you copied back from a response. See `gotchas.md` #7;
a deadline that lands four hours early is the single most expensive
one-character mistake available here.

### The assignment group, and weighted grades

`assignment_group_id` decides which gradebook category the assignment lands in.
Without it the assignment goes to the default group, which quietly changes
weighted-grade math in a course that uses weights.

An assignment created without `assignment_group_id` in a weighted course is a
real hazard: it lands somewhere, it counts for something, and nobody notices
until final grades look wrong. Ask which group when the course uses weighted
groups. `assignments --json` shows which group existing assignments use; the
plain listing does not.

Check whether the course is weighted at all with
`get /courses/:course --param "include[]=total_scores"` and read
`apply_assignment_group_weights`.

## Update

Same payload shape via PUT. Only send the fields being changed:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/assignments/<id> \
    --json '{"assignment": {"published": true}}' --live
```

Changing `due_at` on the assignment changes it for the whole class. For one
student or section, use an override instead (below).

## Delete

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    delete /courses/:course/assignments/<id> --live
```

Deleting an assignment deletes its submissions and grades from the gradebook.
Confirm with the user and state that consequence explicitly. Deleted
assignments can be restored from the course undelete page in the UI
(`/courses/<id>/undelete`) but not reliably via API, and not by `undo`.

## Overrides (extensions and accommodations)

The right tool for "give student X until Sunday" or "section 2 gets an extra day".

Per-student and per-section due dates live in `assignment_overrides`, not on the
assignment. An assignment's `due_at` is the default, not the truth for everyone.
Anything that reasons about lateness has to account for overrides or say that it
did not.

```bash
# List existing overrides
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignments/<id>/overrides --all

# Extension for specific students
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/assignments/<id>/overrides --json '{
  "assignment_override": {
    "student_ids": [11111, 22222],
    "title": "Accommodation extension",
    "due_at": "2026-09-21T23:59:00-04:00",
    "lock_at": "2026-09-21T23:59:00-04:00"
  }
}' --live

# Section-level override
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/assignments/<id>/overrides --json '{
  "assignment_override": {"course_section_id": 999, "due_at": "2026-09-19T23:59:00-04:00"}
}' --live
```

Gotchas:
- If `lock_at` on the base assignment is earlier than the override `due_at`,
  the student still cannot submit; set `lock_at` in the override too.
- A student can appear in only one ad hoc (student_ids) override per
  assignment. To add a student, PUT the existing override with the full
  updated `student_ids` list rather than POSTing a second one.
- An override with `due_at: null` means "no due date" for those students,
  distinct from omitting the field.

## Rubrics

To attach a real grading rubric to an assignment (one that shows in
SpeedGrader and can drive the score), see `canvas-rubrics.md`. Set the
assignment's `points_possible` to equal the rubric's criterion total before
attaching a `use_for_grading` rubric, or the gradebook percentage will be off.

## Assignment groups

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignment_groups --all --param "include[]=assignments"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/assignment_groups \
    --json '{"name": "Homework", "group_weight": 30, "position": 2}' --live
```

`group_weight` only matters when the course has
`apply_assignment_group_weights: true`. Drop rules live in `rules`:
`{"drop_lowest": 1}` on the group update payload. The course-reports skill
reads both when it computes a final grade.

## Bulk due date updates

For shifting many dates at once (e.g. after a snow day), Canvas has a bulk
endpoint that beats N individual PUTs:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/assignments/bulk_update --json '[
  {"id": 111, "all_dates": [{"base": true, "due_at": "2026-09-19T23:59:00-04:00"}]},
  {"id": 112, "all_dates": [{"base": true, "due_at": "2026-09-20T23:59:00-04:00"}]}
]' --live
```

This is a batch, student-visible change: run it without `--live` first, list the
before/after dates for the user, and confirm before repeating it with the flag.
A date change students have already planned around is also a course-comms
event, not just an API call.
