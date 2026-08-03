# Groups and group sets

Courses that put students in teams — project groups, lab partners, discussion
sections — express that in Canvas as **groups** inside a **group category** (a
"group set"). `scripts/groups.py` creates group sets and populates teams; group
assignments (one submission per team) are a normal assignment with a
`group_category_id`, documented at the bottom.

Canvas API docs: Group Categories, Groups, Group Memberships.

## Model

- A **group category** (group set) belongs to the course, e.g. "Project Teams".
- **Groups** (teams) live inside one category. A student can be in one group
  per category.
- A **group assignment** references a category; every member of a team shares
  one submission and (optionally) one grade.

## Create a group set

```bash
# N empty, named groups ("Project Teams 1".."Project Teams 6") to fill yourself
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/groups.py create --course 326 \
    --name "Project Teams" --groups 6 --live

# N groups, Canvas randomly distributes all current students
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/groups.py create --course 326 \
    --name "Project Teams" --auto 6 --live

# Self-signup: students pick their own team (restricted = only within their section)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/groups.py create --course 326 \
    --name "Study Groups" --self-signup enabled --group-limit 4 --live
```

The script refuses to create a second set with a name that already exists
(populate the existing one with `assign` instead). `create` payloads to
`/courses/:course/group_categories` are **flat** (not nested under a key) —
a gotcha if you hand-roll it (`gotchas.md` #2).

## Populate teams from a mapping

The common case: you already have teams in a spreadsheet. Put them in a JSON
file and let the script create groups and set memberships. Members may be
Canvas user ids or emails (resolved against the roster):

```json
{
  "group_set": "Project Teams",
  "self_signup": null,
  "group_limit": null,
  "teams": {
    "Team Alpha": [11111, "grace@example.edu"],
    "Team Beta":  [33333, 44444]
  }
}
```

```bash
# Preview: shows which groups exist, who will be added/removed
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/groups.py assign teams.json --course 326 --dry-run

# Apply (additive: adds missing members, never removes)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/groups.py assign teams.json --course 326 --live

# Make Canvas match the file exactly, removing members not listed
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/groups.py assign teams.json --course 326 --sync --live
```

Behavior worth knowing:
- **Every member is resolved before any write.** One unrecognized email/id
  aborts the whole run with a report, so a typo can't half-populate teams.
- **Additive by default.** Existing members not in the file are left alone
  unless you pass `--sync`. `--sync` removes them — preview first. It is the
  one command here that takes a student off a team, and a removal is not
  recoverable from Canvas's UI history; every team it touches gets an
  `actions.log` line recording the membership as it was.
- The group set and any missing named groups are created on demand, so `assign`
  alone is enough; you don't have to `create` first.

### Raw calls (no script)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/group_categories --json '{"name": "Project Teams"}' --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /group_categories/<cat_id>/groups --json '{"name": "Team Alpha"}' --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /groups/<group_id>/memberships --json '{"user_id": 11111}' --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /groups/<group_id>/users --all                       # current members
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    delete /groups/<group_id>/users/<user_id> --live         # remove a member
```

Auto-distribute unassigned students into existing groups:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /group_categories/<cat_id>/assign_unassigned_members \
    --json '{"sync": true}' --live
```

## Group assignments (one submission per team)

Not a separate object — an assignment with a `group_category_id`. Create it via
`assignments.md`, adding:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/assignments --json '{
  "assignment": {
    "name": "Project Milestone 1",
    "points_possible": 100,
    "group_category_id": 4567,
    "grade_group_students_individually": false,
    "submission_types": ["online_upload"],
    "published": false
  }
}' --live
```

- `grade_group_students_individually: false` (the default) means grading one
  member's submission applies the score to the whole team. Set it `true` to
  score each member separately.
- One teammate's upload is the team's submission; the others see it as
  submitted.
- A rubric attaches and grades exactly as in `canvas-rubrics.md`; with
  individual grading off, the rubric score fans out to the team.

## Gotchas

- **One group per category.** Adding a student to a second team in the same set
  moves them; it doesn't duplicate. To reorganize, `--sync` from a corrected
  file.
- **Self-signup vs assigned.** With `self_signup` enabled you generally don't
  pre-populate; students choose. Setting memberships *and* self-signup together
  is allowed but confusing — pick one model per set.
- **Sections and SIS.** `--self-signup restricted` limits signup to a student's
  own section; useful for section-based teams. Group membership itself is not
  SIS-synced, so it won't be overwritten the way enrollments can be
  (`gotchas.md` #11).
- **Deleting a set** deletes its groups and their shared submissions on any
  group assignment — treat like any destructive action (Safety Rule 1).
