---
name: canvas
description: >
  Read and write a Canvas course through its REST and GraphQL APIs: roster and enrollments,
  assignments, due dates, extensions and overrides, quizzes, pages, modules, files, rubrics,
  groups, announcements, submissions, grades, and CSV grade imports. Use when the user says
  "check Canvas", "who's in my class", "pull the roster", "what's ungraded", "how many
  submitted", "post this to Canvas", "push these grades to Canvas", "import the Gradescope
  scores", "mark the late submissions", "create the assignment in Canvas", "make a quiz", "set up
  project teams", "give this student an extension", "publish that page", or names a Canvas
  object, a due date, or an instructure.com URL. Also use when another skill needs Canvas data,
  such as grading needing a roster. Do NOT use for drafting content: assignments, course-comms,
  and grading write it and hand it here to post; course-reports owns end-of-term grades and
  at-risk reporting.
---

# Canvas

Canvas is the only platform in this plugin with a real, documented API. It returns useful errors,
it paginates honestly, and it does not break when someone redesigns a page. That makes it the
place where anything that must actually land should go, and it makes it the destination for
grades that came from anywhere else.

This skill is the whole Canvas surface: the generic HTTP client, a set of wrapper scripts for the
jobs that are painful by hand, and a reference file per domain carrying the endpoints, payload
shapes, and quirks that otherwise cost an afternoon.

## Before anything

Confirm the course, the same as every other skill in this plugin:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326 --tool canvas
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 whoami
```

`whoami` proves the token works and prints which Canvas account, which instance, and which course
id and name it reaches. Say the course name and term back in one line before doing anything. If
`verify` reports a MISMATCH between the profile and `canvas/config.json`, stop and resolve it;
that is the state in which an announcement reaches the wrong section.

If Canvas is not set up for this course, hand off to the course-setup skill rather than
improvising a config.

## The two clients

**`canvas_api.py`** is the curated client for the operations that come up constantly. It prints
tables rather than JSON and it reads current state before it writes:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 roster
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 assignments
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 submissions <assignment_id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 announcements
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 \
    announce --title "Exam room change" --file body.md --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 \
    set-grade <assignment_id> --user <canvas_user_id> --score 17 --comment-file feedback.md --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 \
    set-grades <assignment_id> --file grades.json --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 \
    create-assignment --file spec.json --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 undo
```

Add `--json` when the output feeds another step rather than a person.

**`canvas.py`** is everything else, the full REST surface plus GraphQL, for any endpoint the
curated client does not wrap:

```bash
# Read (use --all for any list; Canvas defaults to 10 items per page)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignments --all
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/users --all --param "enrollment_type[]=student"

# Create / update (JSON body; nested structure mirrors Canvas docs)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/assignments/123 --json '{"assignment": {"published": true}}' --live

# Delete (destructive; see Safety below)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    delete /courses/:course/assignments/123 --live

# GraphQL (best for bulk submission/grade reads; mutations go through the same gate)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 graphql '<query>' \
    --vars '{"courseId": "123456"}'
```

Notes on `canvas.py`:

- `:course` in a path is substituted with the course id. It is **not** substituted in `--param`
  values; interpolate the numeric id yourself there (`references/gotchas.md` #16).
- `--param` is repeatable; use `k[]=v` bracket names for Canvas array params.
- Bodies are sent as JSON by default, which every modern Canvas endpoint accepts. If an endpoint
  misbehaves with JSON, retry with `--form` (bracket encoding). Rubric creation needs it.
- `--dry-run` prints the request instead of sending it, on reads as well as writes.
- Output is JSON on stdout; pipe to `jq` or a file for large results. Errors are JSON on stderr
  with a nonzero exit code.
- Pagination, rate-limit backoff, and retries on 5xx are handled. A 300-person roster comes back
  whole rather than as the first hundred, which matters because a silently truncated roster looks
  exactly like a small class.

Configuration comes from the course folder: `base_url`, `course_id`, and `write_mode` from
`<course>/.infra/canvas/config.json`, and the token from that folder's credentials file. The
environment variables `CANVAS_BASE_URL`, `CANVAS_API_TOKEN`, and `CANVAS_COURSE_ID` still work as
a fallback for CI or someone with no course folder, but there is then no config file to gate a
write and no `actions.log` to record one, so the course folder is the documented path.

## Wrapper scripts

Each of these exists because doing the job by hand is many calls and one silent failure mode.
They all take `--course`, all route their Canvas traffic through `canvas.py`, and all preview by
default.

| Script | What it does | Reference |
|---|---|---|
| `sync_grades.py` | Import a Gradescope (or any) CSV into an assignment, matched by email/SID, with a preview and mismatch report | `references/grade-sync.md` |
| `mark_late.py` | Compare submission times to each student's *effective* due date, mark genuinely-late work, never auto-penalize an accommodated student | `references/late-policy.md` |
| `late_penalties.py` | Apply your own late policy: percent-per-day, or a semester late-day budget | `references/late-policy.md` |
| `rubric.py` | Create a rubric from JSON; grade submissions by criterion name | `references/canvas-rubrics.md` |
| `upload_quiz.py` | Bulk-create a Classic Quiz and all its questions from a JSON file | `references/quizzes.md` |
| `groups.py` | Create group sets and populate teams from a roster mapping | `references/groups.md` |
| `download_submissions.py` | Pull every submission for an assignment to per-student folders | `references/submissions-grades.md` |
| `cache_pages.py` | Keep a local cache of course pages | `references/pages.md` |

The first six write to Canvas and take `--live` and `--override-mode`. The last two only write to
local disk, so they have neither, and `download_submissions.py` is the one that creates a folder
full of student work, which is its own kind of care.

## Writing, and the gate on it

Every write needs two switches: `--live` on the command, and `"write_mode": "live"` in the
course's `.infra/canvas/config.json`. With either missing, the command prints exactly what it
would send and stops. `--override-mode` allows a considered one-off against a course still set to
dry-run.

Two switches rather than one, for the same reason Piazza's privatize has two. The flag is easy to
type by accident. The config file is a decision the user made once, deliberately, after watching
the thing do the right thing on real data. Flip the config only when they ask.

Beyond the switches, **write only what the user has read and approved.** The rules are the same
as posting to Piazza and they are narrower than they sound:

- "Post that" after a single drafted announcement: yes.
- "These look good" after four drafts: not approval to post four. Ask which.
- "Post it, but change the date": make the edit, show the final text, get one more yes. They
  approved something they have now not read.
- Anything during a scheduled or unattended run: no. A schedule fires with nobody watching, so
  the approval cannot have happened. Scheduled runs draft and stop.

Report what happened after every write: the object id and its URL, so the user can look at it in
context. If a write fails, say so immediately rather than continuing down a list; a half-applied
batch is worse than an unapplied one.

**Undo.** Every write through a course folder appends to `<course>/.infra/canvas/actions.log`.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 undo
```

That prints the last recorded write and, where it can, the exact command that reverses it. It can
when the write recorded a previous value, which the curated grade commands and the wrapper
scripts do, since they read current state before changing it. A raw `canvas.py` write logs what
was sent, not what was there before, so `undo` shows you the entry and leaves the reversal to you;
read the object first if you want that safety net.

Some things cannot be reversed at all: a submission that had no score before cannot be un-graded
through the API, an announcement's notification cannot be recalled, and a delete is not restorable
by API. The output says so instead of pretending.

## Domain routing

Read the matching reference before working in a domain. Each file has the endpoints, payload
shapes, and the quirks that waste time when unknown.

| Task involves | Read first |
|---|---|
| Assignments, due dates, extensions, assignment groups | `references/assignments.md` |
| Rubrics on a Canvas assignment: creating one, or grading a submission through it | `references/canvas-rubrics.md` (encoding only, rubric *design* is `${CLAUDE_PLUGIN_ROOT}/skills/grading/references/rubrics.md`) |
| Quizzes of any kind | `references/quizzes.md` (**always default to Classic Quizzes**, New Quizzes cannot export student submissions or answers via API) |
| Wiki pages, front page, generating and uploading authored page content, the local page cache | `references/pages.md` |
| Discussions or announcements | `references/discussions-announcements.md` |
| Students, rosters, sections, enrollments, matching a student across platforms | `references/students-enrollments.md` |
| Submissions, grades, gradebook, comments, posting policy; bulk-downloading submission files | `references/submissions-grades.md` |
| Importing Gradescope (or other CSV) grades into an assignment | `references/grade-sync.md` |
| Marking late imports, making Canvas's late policy match the syllabus, applying your own penalty or a late-day budget, accommodation-aware lateness | `references/late-policy.md` |
| Group sets and teams (project teams, lab groups); group assignments | `references/groups.md` |
| Modules, module items, files, folders | `references/modules-files.md` |
| A 404 that might be a permission problem; what a TA or Designer token can do; first run against an unfamiliar Canvas instance | `references/permissions.md` |
| Anything surprising or broken | `references/gotchas.md` |
| End-of-term grade computation, weighting, letter grades, at-risk and activity reporting | the **course-reports** skill, which builds on the reads here |

`references/gotchas.md` is short; skim it once per session regardless of domain.

## Safety rules

This skill writes to live courses that real students see. The reference files cite these by
number.

1. **Confirm before destructive or student-visible actions.** Deleting anything, posting an
   announcement, publishing content, or changing a grade requires showing the user exactly what
   will happen and getting explicit confirmation first. A run without `--live` is how you show it.
2. **Default new content to unpublished** (`"published": false`) unless the user explicitly says
   to publish. Announcements are the exception: they are live on creation, which is precisely why
   they need confirmation.
3. **Never bulk-modify without a preview.** For any operation touching more than one object
   (batch due date changes, bulk grading), first list what will be affected, show the user, then
   proceed.
4. **Prefer assignment overrides over editing the assignment** when a change applies to one
   student or section. Editing the assignment's own due date changes it for everyone. **Never
   auto-penalize a student who has an accommodation.** When a late-work or grade action would
   affect an accommodated student, a per-student override, or an arrangement recorded in the
   course profile or an accommodations file, compute their *effective* deadline and surface the
   situation for the user to decide individually. Accommodations are individual by nature; a
   blanket rule is the wrong tool. `mark_late.py` enforces this by routing them to
   `needs_review`; preserve it in any hand-rolled flow.
5. **Treat the token as a secret.** Never print it, never write it anywhere but the course's
   credentials file, never include it in output. It carries the user's full instructor permissions
   across every course their account touches.
6. **An existing page requires an explicit overwrite-or-merge decision from the user, every time,
   no exceptions.** Before writing generated content to a page whose slug already exists, ask in
   conversation, not a tool permission prompt, whether to overwrite or merge with the live
   content (`references/pages.md`). This check fires per page and cannot be pre-waived by a
   general instruction to work autonomously; that kind of instruction authorizes skipping routine
   check-ins, not silently discarding existing course content.
7. **Locally written student data is a student record.** See below.

## Student data on disk

Two capabilities here write real student data to local files: `download_submissions.py` (uploaded
files, typed text, code, under `.canvas-cache/<course_id>/submissions/`) and any roster or grade
CSV you save alongside them. The course-reports skill writes more of it.

In the US these are FERPA-protected education records; in the UK and EU they are personal data
under GDPR. Before writing the first such file in a project, check that `.gitignore` excludes
`.canvas-cache/` and, if it does not, **add the entry yourself and say that you did.** Never
transmit any of it anywhere without the user asking for that specific transmission.

The full rule is in the plugin README under "Student data on disk". Read it once; it governs
everything this plugin writes to disk, not just Canvas downloads.

## Division of labor

This skill is the hands, not the judgment.

- **course-comms** writes announcement text; canvas posts it. An announcement drafted and posted
  in one motion has skipped the read-and-approve step.
- **grading** decides what a score should be and what the feedback says; canvas writes them.
- **assignments** writes the spec; canvas creates the assignment.
- **course-reports** computes final grades and at-risk lists from data read here; canvas does not
  do the arithmetic.
- **course-setup** owns the course folder and the credentials; canvas assumes they exist.

## Errors worth recognizing

`canvas.py` explains these inline, but knowing them saves a round of guessing.

- **401**: the token is missing, wrong, or expired.
- **403**: a permission problem on this action, a **concluded course** (read-only through the
  API), or rate limiting, which Canvas signals as a 403 whose body mentions a rate limit. The
  client retries that last case for you.
- **404**: Canvas returns 404 for objects your token is not allowed to see, **not 403**. So a 404
  is a wrong id *or* a permission problem and the two are indistinguishable from the response.
  Never conclude "it does not exist" from a 404 alone; check the token's role first
  (`references/permissions.md`).
- **422**: Canvas rejected the values, and the detail usually names the field.

A refused write is different from a preview: no `--live` prints the request and exits normally,
while a write blocked by `write_mode` exits nonzero on purpose.

## Scope, and what is not done

Honest about the edges, so nobody assumes coverage that is not there:

- **Verified against Canvas Cloud only.** Self-hosted instances can lag the API by a release or
  more, and the New Quizzes paths are the least exercised part of this skill anywhere.
- **Exercised at roughly 30–200 students.** Larger courses should work: bulk reads use GraphQL
  and writes use batch endpoints where they exist, but rate-limit behavior on multi-thousand
  rosters is unmeasured. Marking late submissions is one request per student because Canvas has no
  bulk endpoint for late status.
- **The write paths have no end-to-end test.** The pure logic that decides grades is covered; the
  code that assembles a payload and posts it is covered by its helpers plus preview inspection.
- **The mock server in `tests/` is not Canvas.** It pins the behavior this plugin *expects*; it
  cannot catch Canvas changing its own semantics. Real quirks still surface only in real use,
  which is what `references/gotchas.md` is for, add to it when one does.
- **File upload leaves the client** at step 2 of Canvas's three-step dance, so that one write has
  no audit line (`references/modules-files.md`).
- **Gradescope is read-only** in this plugin. Grades go to Canvas.
