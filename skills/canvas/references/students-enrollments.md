# Students, Enrollments, Sections

## Listing students

`canvas_api.py --course 326 roster` is the readable version: active and invited
students with email and enrollments, already paginated. Drop to `canvas.py`
when you need particular includes or the enrollment rows themselves.

Two endpoints, subtly different:

```bash
# /users: one row per user, cleaner for rosters
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/users --all \
    --param "enrollment_type[]=student" --param "include[]=email"

# /enrollments: one row per enrollment (a user in two sections appears twice),
# includes grades and section ids
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/enrollments --all \
    --param "type[]=StudentEnrollment" --param "include[]=avatar_url"
```

Useful `include[]` values on /users: `email`, `enrollments`, `avatar_url`,
`test_student`. Useful params: `search_term=<name or partial email>` (min 2
chars), `enrollment_state[]=active|invited|completed`.

Notes:
- `email` may be null if the token lacks permission to read it; the login id
  (`login_id`, usually the campus NetID) often serves instead with
  `include[]=email` or admin-scope tokens.
- Exclude the Test Student: it has enrollment type `StudentViewEnrollment`
  and only shows up when explicitly included, but double check when counting.
- `enrollment_type[]` on /users uses lowercase (`student`, `teacher`, `ta`,
  `observer`, `designer`); `type[]` on /enrollments uses the class names
  (`StudentEnrollment`, `TeacherEnrollment`, `TaEnrollment`, ...). Mixing
  these up silently returns everything or nothing.

## Identity: which id to match on

Three identifiers travel with a student and they are not interchangeable:

- `id` — the Canvas user id. This is what grade writes, override payloads, and
  group memberships take. It is not the SIS id and not the login id.
- `sis_user_id` — the institution's own identifier, the one that matches a
  registrar export or a Gradescope roster.
- `login_id` — what the student types to sign in, usually the campus NetID and
  often the same string as their email.

**Match students across platforms by SIS id or email, never by name.** Names
collide, change, and are formatted differently in every system, and a
name-matched grade batch eventually lands on the wrong person. Every script in
this plugin that reads a CSV follows this rule through one shared function in
`canvas_common.py`, which tries the named column, then email, then SID against
`sis_user_id`, then login id — and reports a row it cannot resolve
unambiguously rather than guessing.

## Activity and grade snapshot fields

The `/enrollments` response (not `/users`) also carries, per enrollment:

- `last_activity_at` — ISO 8601 UTC timestamp of the student's last recorded
  activity in the course. This is the cheap, single-call signal for
  "who's been active in the last N days" — see the course-reports skill's
  `activity-report.md`.
- `total_activity_time` — cumulative seconds of activity, **lifetime in the
  course, not windowed**. Don't compute an activity *rate* from this without
  also knowing the enrollment's start date; it can't tell you whether a
  student was active yesterday or three months ago.
- `grades.current_score` / `grades.final_score` / `unposted_current_score` —
  documented in full in `submissions-grades.md`'s "Enrollment-level grades"
  section; not duplicated here.

## Individual users

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /users/<id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /users/sis_user_id:<netid>          # SIS id lookup
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /users/<id>/profile                 # bio, pronouns
```

SIS ids work in paths generally, with the `sis_user_id:` / `sis_course_id:`
prefix — e.g. `/courses/sis_course_id:HIST-101-FALL26`.

## Sections

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/sections --all --param "include[]=students"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /sections/<id>
```

Section ids are what assignment overrides and gradebook filters key on.

## Enrolling and removing (needs sufficient permission)

```bash
# Add a TA
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/enrollments --json '{
  "enrollment": {"user_id": 11111, "type": "TaEnrollment", "enrollment_state": "active"}
}' --live

# Enroll into a specific section instead
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /sections/<section_id>/enrollments --json '{
  "enrollment": {"user_id": 11111, "type": "StudentEnrollment", "enrollment_state": "active"}
}' --live

# Remove: needs the ENROLLMENT id (from /enrollments), not the user id
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    delete /courses/:course/enrollments/<enrollment_id> \
    --param task=conclude --live      # conclude|delete|deactivate
```

`conclude` keeps grades visible (end of semester); `delete` erases the
enrollment record; `deactivate` hides the student but preserves everything
and is reversible. Prefer `conclude` or `deactivate`; confirm before `delete`.

At SIS-managed institutions, enrollments usually sync from the registrar;
manual enrollment changes may be overwritten by the next SIS sync or blocked
outright. Warn the user.

## Custom gradebook columns (notes, flags)

For per-student metadata that only teachers see:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/custom_gradebook_columns --all
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/custom_gradebook_columns/<col>/data/<user_id> \
    --json '{"column_data": {"content": "Extension approved through 9/21"}}' --live
```

A note like that one is student data about an accommodation. It lives in
Canvas, not on disk, so the gitignore rule does not apply — but the judgment
about who sees it does.
