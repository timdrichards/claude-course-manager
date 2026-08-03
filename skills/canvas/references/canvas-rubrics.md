# Canvas rubrics: encoding, attaching, and grading through one

Real Canvas rubrics that attach to an assignment, drive the score, and appear
in SpeedGrader — created and graded through the API. Canvas API docs: Rubrics,
Rubric Associations, Rubric Assessments.

**This file is about the wire format, not about rubric quality.** For how to
design a rubric two graders can apply the same way — item structure, point
distribution, what makes an item checkable — read
`${CLAUDE_PLUGIN_ROOT}/skills/grading/references/rubrics.md` first. Write the
rubric there; encode it here. (Two files named `rubrics.md` in one plugin would
be a trap, which is why this one carries the `canvas-` prefix.)

`scripts/rubric.py` handles the two painful halves of the encoding so you
rarely hand-build the payloads: `create` (indexed-hash encoding) and `grade`
(criterion/rating id lookup). Read this file to understand what it does and
when to drop to raw `canvas.py`.

## Why a script (the two things that waste time)

1. **The create endpoint wants an indexed hash, not an array.** Criteria must
   be sent as `rubric[criteria][0][description]`,
   `rubric[criteria][0][ratings][0][points]`, … The numeric index is what ties
   each rating to its criterion. A plain JSON array (`criteria[][...]`) loses
   that correlation and Canvas mis-parses or silently drops ratings. The
   endpoint is also unreliable with a JSON body, so send **form-encoded**
   (`canvas.py ... --form`).
2. **Grading is keyed by opaque ids.** A rubric assessment is
   `rubric_assessment[<criterion_id>][points]`, where `<criterion_id>` is an
   id Canvas assigned at creation (e.g. `_1234`), not the criterion's name.
   You must read the rubric back to learn those ids before you can grade.

`rubric.py` encapsulates both. Everything below also documents the raw calls in
case you need to go off-script.

## Model: rubric vs. association

A **rubric** is a reusable object owned by the course. A **rubric association**
binds a rubric to one assignment and decides how it behaves there:

- `purpose: "grading"` — shows in SpeedGrader and can score. `purpose:
  "bookmark"` — just saved to the course, does nothing on the assignment.
- `use_for_grading: true` — the sum of the criterion points **becomes** the
  submission score. With `false`, the rubric is a scoring guide only and you
  still enter the grade separately.

You almost always want `purpose: "grading"`. Add `use_for_grading: true` when
the rubric should drive the score.

## Create a rubric (and attach it for grading)

Author the rubric as a JSON file — criteria as a normal array; the script does
the index-hash conversion:

```json
{
  "rubric": {
    "title": "HW7 Rubric",
    "free_form_criterion_comments": false,
    "criteria": [
      {"description": "Correctness", "long_description": "Handles all cases", "points": 20,
       "ratings": [
         {"description": "Full marks", "points": 20},
         {"description": "Minor gaps", "points": 12},
         {"description": "Major gaps", "points": 5},
         {"description": "No credit",  "points": 0}
       ]},
      {"description": "Code style", "points": 10,
       "ratings": [
         {"description": "Clean", "points": 10},
         {"description": "Rough", "points": 5},
         {"description": "Messy", "points": 0}
       ]}
    ]
  },
  "association": {
    "assignment_id": 678,
    "use_for_grading": true,
    "hide_score_total": false
  }
}
```

```bash
# Preview the exact form-encoded request without sending it
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rubric.py create hw7-rubric.json --course 326 \
    --assignment-id 678 --use-for-grading --dry-run

# Attach + use-for-grading straight from the JSON's association block
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rubric.py create hw7-rubric.json --course 326 --live

# Or set the association from flags (override/augment the JSON)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rubric.py create hw7-rubric.json --course 326 \
    --assignment-id 678 --use-for-grading --live
```

Without `--live` you get the request and nothing is created; `--dry-run` is the
same preview and wins if both are given.

Output reports the new `rubric.id`, the `association`, and — most usefully —
each **criterion id and rating id** Canvas assigned. Those ids are what you
grade against, though `rubric.py grade` looks them up for you by name so you
rarely need them directly.

Leave off the `association` block (and the flags) to create a standalone,
reusable rubric with no assignment attached.

### Match the assignment's points to the rubric total

When `use_for_grading` is true the rubric total becomes the score, so set the
assignment's `points_possible` equal to the sum of the criteria (30 above) or
the gradebook percentage will be off. Create/adjust the assignment first (see
`assignments.md`), then attach the rubric. The script reports `total_points`
so you can check the two agree.

### Raw equivalent (no script)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/rubrics --form --json '{
  "rubric": {"title": "HW7 Rubric", "criteria": {
    "0": {"description": "Correctness", "points": 20,
          "ratings": {"0": {"description": "Full marks", "points": 20},
                      "1": {"description": "No credit", "points": 0}}}
  }},
  "rubric_association": {"association_type": "Assignment", "association_id": 678,
                         "purpose": "grading", "use_for_grading": true}
}' --live
```

Note `--form` and the `"0"`/`"1"` string keys — that is the whole trick.

## Grade with the rubric

`grade` takes a JSON file of per-student, per-criterion scores. Reference each
criterion by its **description** (or its id); the script fetches the
assignment's rubric, resolves names to ids, encodes the assessment, and PUTs
each submission. With `use_for_grading` on, Canvas computes the score.

```json
{
  "grades": [
    {"user_id": 11111, "comment": "Strong solution overall.",
     "criteria": {
        "Correctness": {"points": 18, "comments": "Missed the empty-input case."},
        "Code style":  {"rating": "Clean"}
     }},
    {"user_id": 22222,
     "criteria": {
        "Correctness": {"rating": "Major gaps", "comments": "Off-by-one in the loop."},
        "Code style":  {"points": 5}
     }}
  ]
}
```

```bash
# Always preview a batch first (Safety Rule 3) — shows resolved ids and totals
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rubric.py grade hw7-grades.json --course 326 \
    --assignment-id 678 --dry-run

# Then apply
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rubric.py grade hw7-grades.json --course 326 \
    --assignment-id 678 --live
```

Per-criterion value rules:
- `"points"` sets the score for that criterion.
- `"rating": "<name>"` selects a named rating; it supplies the points when you
  omit `"points"`, and highlights that cell in SpeedGrader.
- Giving `"points"` that exactly equals a rating's value also highlights the
  cell. A bare number (`"Correctness": 18`) is shorthand for `{"points": 18}`.
- `"comments"` attaches a per-criterion comment; the entry-level `"comment"`
  posts one overall submission comment.

The script **fails fast**: an unmatched criterion name, an unknown rating, or a
missing `user_id`/`points` stops the run with a clear error (and lists the
valid names) rather than silently posting a wrong or partial grade. On a mid-
batch API failure it stops and reports who was and wasn't graded. Each write it
does land is appended to the course's `actions.log` with the previous rubric
assessment, which is the only thing an undo can be reconstructed from.

Grading is student-visible. Confirm the plan with the user before applying, and
respect any manual posting policy (`post_manually` on the assignment — see
`submissions-grades.md`; rubric scores stay hidden until posted).

### Raw equivalent (no script)

Read the ids, then PUT the submission:

```bash
# 1. Learn the criterion/rating ids
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignments/678 --param "include[]=rubric" | jq '.rubric'

# 2. Post the assessment (form-encoded, keyed by criterion id)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/assignments/678/submissions/11111 --form --json '{
  "rubric_assessment": {
    "_1234": {"points": 18, "rating_id": "abcd", "comments": "Missed empty input."},
    "_5678": {"points": 10}
  },
  "comment": {"text_comment": "Strong solution overall."}
}' --live
```

The response's `score` reflects the rubric sum when `use_for_grading` is set.

## Reading rubrics and existing assessments

```bash
# The rubric attached to an assignment (criteria + ids), inline on the assignment
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignments/678 --param "include[]=rubric"

# A rubric object directly, with everywhere it is used and its assessments
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/rubrics/<rubric_id> \
    --param "include[]=assessments" --param "style=full"

# Existing rubric scores on submissions
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignments/678/submissions --all \
    --param "include[]=rubric_assessment" --param "include[]=user"
```

## Gotchas

- **Array vs indexed hash.** The single biggest time-sink. `criteria` (and each
  criterion's `ratings`) must be an index-keyed hash on create. `rubric.py`
  and the `--form` + `"0"/"1"` pattern handle it; a JSON array does not.
- **`purpose` must be `"grading"`.** A rubric associated with `purpose:
  "bookmark"` (or none) will not appear for grading no matter what
  `use_for_grading` says. If a rubric "isn't showing up," check the
  association's purpose first.
- **`use_for_grading` overwrites, not merges.** Once on, entering a manual
  grade in the gradebook and later editing the rubric can each clobber the
  other's score. Pick one source of truth per assignment; if the rubric grades,
  grade through the rubric.
- **Criterion ids are per rubric, not stable across rubrics.** Never hardcode
  `_1234` across assignments — always read them back (the script does).
- **Editing a rubric after grading is risky.** Adding/removing criteria or
  changing point values on a rubric that already has assessments can strand or
  rescale existing scores. Prefer getting the rubric right before grading;
  if you must change it mid-stream, warn the user and re-check affected scores.
  The grading skill's `consistency.md` covers the judgment side of that.
- **One rubric per assignment for grading.** An assignment has at most one
  grading association. Attaching a second rubric replaces the first.
- **Free-form comments.** With `free_form_criterion_comments: true`, criteria
  need no ratings and graders type comments per criterion instead of picking a
  level; you still send `points` per criterion when grading.
