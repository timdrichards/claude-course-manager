# Course Manager

Eight skills that share one idea: **a course is a folder**, and everything about it lives in that
folder in a shape every skill understands. Setting up a course once means the syllabus skill, the
grading skill, and the Piazza digest all know the same facts about it.

## Installing

This repository is a Claude plugin and doubles as a single-plugin marketplace, so it installs
from the repo itself:

```
/plugin marketplace add timdrichards/claude-course-manager
/plugin install course-manager@claude-course-manager
```

Or clone it and point Claude at the folder. The plugin needs Python 3.9 or newer.
`course_infra.py`, `canvas.py`, `canvas_api.py`, and `prose_check.py` are pure standard library.
Two skills need extra packages:

```bash
pip install piazza-api                # student-questions
pip install requests beautifulsoup4   # gradescope
```

Nothing is configured globally. Everything is per course, in a folder you choose.

## The layout

```
<courses root>/326/
├── .infra/                    tool state
│   ├── course.json            identity, and this course's layout convention
│   ├── course-profile.md      what the course teaches, its policies, its voice
│   ├── piazza/                config.json, credentials, inbox/, drafts/, state/, actions.log
│   ├── canvas/                same shape
│   └── gradescope/            same shape
├── course/                    survives every offering
│   ├── units/  homework/  labs/  code/
│   └── slides/  videos/  reading/  drafts/
└── semesters/
    ├── current -> 2026-07-summer-2
    └── 2026-07-summer-2/      belongs to one run of the course
        ├── students/  grading/  accommodations/     gitignored
        └── announcements/
```

Two splits. Things describing the **course** sit under `.infra` and are read by every skill;
things describing one **service** live in that service's folder. And material that **survives the
next offering** sits under `course/`, while material tied to **one term** sits under
`semesters/<term>/`. The question that decides the second: would this still be true if you taught
the course again next year with different students? A homework spec would. An accommodation letter
would not. That makes rollover a new sibling folder rather than a copy-and-prune.

Folder naming is per course, recorded in `course.json`, and defaults to lowercase with hyphens.
The semester slug is always `YYYY-MM-season[-session]` whatever the naming style, because it has
to sort: Summer Session II is `2026-07-summer-2`, after Session I's `2026-06-summer-1`.

Two levels, deliberately. Things describing the **course** sit directly under `.infra` and are
read by every skill. Things describing one **service** live in that service's folder. A tool added
later reads the same profile instead of reaching into another tool's files.

A registry at `~/.config/claude-courses/registry.json` records where each course lives, which is
what lets every command take `--course 326` instead of a path. It is an index, not a source of
truth: delete it and everything still works from explicit paths.

## Getting started

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py set-root ~/courses
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 \
    --name "COMPSCI 326" --title "Web Programming" --term "Fall 2026" \
    --institution "UMass Amherst"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 --tool canvas \
    --base-url https://umass.instructure.com --course-id 123456
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326
```

Then fill in the credentials files it created and build a course profile. Or just say "set up
COMPSCI 326 for the fall" and the course-setup skill walks through it.

## Skills

| Skill | What it does |
|---|---|
| **course-setup** | Creates and inspects courses, connects platforms, builds and maintains the course profile. Everything else reads what this writes. |
| **syllabus** | Drafts, reviews, and edits the syllabus as a live LMS page; audits it against what the course actually does; rolls it into a new term; builds the syllabus quiz and the companion overview deck. |
| **assignments** | Writes and reviews assignment specs, scopes them honestly, and catches ambiguity before students find it. |
| **student-questions** | Socratic replies to student questions, plus fetching unanswered Piazza threads, posting approved replies, and flagging public posts that leak assignment code. |
| **grading** | Rubric design, feedback drafting, evidence-backed scoring, grader consistency, regrade requests, and pushing approved scores to Canvas. Asks how far to go before starting. |
| **course-comms** | Announcements, deadline changes, corrections, exam logistics, and staff messages. |
| **course-reports** | End-of-term grade computation and auditing, and student activity / at-risk reporting. Documented workflows, no script: the weighting and the letter bands are course-specific. |
| **canvas** | The whole Canvas API surface: roster and enrollments, assignments and overrides, quizzes, pages, modules and files, rubrics, groups, discussions and announcements, submissions, grades, and CSV grade imports. |

## Scripts

All under `scripts/`. The clients take `--course <name-or-path>`; `course_infra.py` takes the course as a positional argument.

| Script | Purpose |
|---|---|
| `prose_check.py` | Flags writing that reads as machine-generated. Runs before anything drafted is handed over. |
| `course_infra.py` | Owns the layout and the registry. `init`, `verify`, `layout`, `list`, `register`, `unregister`, `set-root`, `path`. |
| `canvas_api.py` | The curated Canvas client. Roster, assignments, submissions, grades, announcements, `whoami`, `undo`. |
| `canvas.py` | The general Canvas client: `get`/`post`/`put`/`delete`/`graphql` against any endpoint, with auth, pagination, rate-limit backoff, and the write gate. Every other Canvas script goes through it. |
| `canvas_common.py` | Shared helpers for those scripts: the write gate, CSV loading, and the one roster-matching function they all use. |
| `sync_grades.py` | Imports a Gradescope (or any) CSV into a Canvas assignment, matched by email or SID, with a preview and a mismatch report. |
| `mark_late.py` | Marks genuinely-late imported work against each student's effective due date. Never auto-penalizes an accommodated student. |
| `late_penalties.py` | Applies a percent-per-day penalty or a semester late-day budget to already-graded work. |
| `rubric.py` | Creates Canvas rubrics from JSON and grades submissions by criterion name. |
| `upload_quiz.py` | Bulk-creates a Classic Quiz and all its questions from a JSON file. |
| `groups.py` | Creates group sets and populates teams from a roster mapping. |
| `download_submissions.py` | Downloads every submission for an assignment into per-student folders. Local only. |
| `cache_pages.py` | Caches Canvas page bodies locally. Local only. |
| `piazza_fetch.py` | Pulls unanswered Piazza threads. Read-only, safe to schedule. |
| `piazza_post.py` | Posts approved replies; privatizes public posts that leak code. |
| `gradescope_fetch.py` | Reads a Gradescope course: assignments, roster, scores, submissions. Read-only. |

## Platforms, honestly

**Canvas** has a real, documented API. It is stable, it paginates properly, and it returns useful
errors. Anything that must actually land goes here, including grades that came from somewhere
else.

**Piazza** has no public API. The client uses the unofficial `piazza-api` package against
Piazza's internal endpoints, so it can break. If your school logs into Piazza through SSO you may
have no Piazza password, and there is no workaround.

**Gradescope** has no public API either, and Gradescope says so. The client scrapes their web app,
where the HTML parsing has broken about once a quarter while login and URLs stayed stable for six
years. Every selector fails loudly rather than returning nothing, because a gradebook full of
silent nulls is worse than a stack trace.

**Gradescope cannot be written to.** No maintained client implements score writing, Gradescope
documents no import path, and its data model computes scores from rubric selections rather than
point values. Rather than ship an endpoint that plausibly does nothing, this plugin has no
Gradescope write path at all. Grades go to Canvas. If you want Gradescope writes, open its
grading UI with DevTools, grade one question, capture the real request, and add it honestly.

**Google Workspace** (Drive, Calendar, Gmail) comes from account-level connectors, not from this
plugin. Nothing here needs configuring; if they are connected, the skills can use them.

## Two switches on every write

Writing to Canvas, and privatizing a Piazza post, both need the command flag (`--live`) **and**
the course's config set to `"live"`. Either one missing means the command prints what it would do
and stops.

The flag is easy to type by accident. The config file is a decision you made once, after watching
the thing do the right thing on real data. Every write appends to that tool's `actions.log` with
the previous value, so `canvas_api.py --course 326 undo` can always tell you how to reverse it.

Nothing posts, announces, or grades during a scheduled or unattended run. A schedule fires with
nobody watching, so the approval cannot have happened. Scheduled runs draft and stop.

## Writing that reads as yours

Everything this plugin drafts goes out under your name. A syllabus, an announcement, a line of
feedback on a student's work. If it reads as machine output, students discount it, and an
instructor who asks students to disclose their AI use has just failed their own standard.

So every skill that drafts prose runs a check before handing anything over:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prose_check.py draft.md
```

The tells come from Wikipedia's *Signs of AI writing*, maintained by the editors who clean up
after it. Findings come in three grades. `FIX` is the character set and the artifacts: em dashes,
curly quotes, stray emoji, chatbot citation markers, assistant residue. `STRONG` is the shapes
that survive paraphrasing: negative parallelism, canned significance, trailing "-ing" clauses that
interpret the sentence they hang off, the `Despite these challenges` formula, summary sentences,
opinions attributed to unnamed experts. `REVIEW` is density: how many words from the documented
overuse list, how many three-item series, how much boldface, whether every heading is in Title
Case.

The checker also looks for signs of *human* writing, and says so when it finds none. Plain
copulas, plain verbs, definite claims, ordinary hedges. Prose with nothing plain in it usually was
not spoken first.

Two things it deliberately does not do. It does not rewrite, because the guide's own warning is
that treating the signs as the problem "could just make detection harder"; the problem is prose
with no particular person behind it, and the tells are just how that surfaces. And it does not
flag the famous non-tells: perfect grammar, formal register, hedging, transition words, the Oxford
comma. Those are either listed as ineffective indicators or absent from the guide entirely, and
stripping them makes writing worse without making it more human.

`skills/course-setup/references/ai-tells.md` is the full account.

## Student data on disk

The write gate protects the course from this plugin. This section is the other direction: what
this plugin writes onto your machine, and what that obliges.

Several capabilities put real student records on local disk, under `.canvas-cache/<course_id>/`
in whatever directory you run them from:

- **Downloaded submissions**: `download_submissions.py` writes each student's uploaded files,
  typed text, and code under `.../submissions/<assignment_id>/`.
- **Reports and snapshots**: the course-reports skill writes names, emails, grades, activity
  timestamps, and at-risk flags under `.../reports/`.
- **Anything you save alongside them**: a Gradescope CSV export, a roster, an accommodations
  file. An accommodations file is the most sensitive of the lot: it records which students have
  accommodations.

This is not merely good practice. In the US these are FERPA-protected education records; in the
UK and EU they are personal data under GDPR. **You are the data controller** for whatever lands
on your machine, and your institution may impose stricter rules about where student data may be
stored. Those govern.

Three rules, and the first is a must rather than a suggestion:

1. **`.canvas-cache/` must be gitignored.** Before writing the first such file in a project, the
   skills check whether `.gitignore` already excludes it and, if not, add the entry and tell you
   they did. Do not rely on `.infra/.gitignore` for this, that one covers credentials and tool
   state inside the course folder, not a cache written into your working directory. The same care
   applies to any directory you redirect a download to with `--out`.
2. **Nothing is transmitted without a specific request.** No uploading, emailing, pasting, or
   syncing a report, snapshot, or downloaded submission anywhere outside the local filesystem
   unless you asked for that particular transmission. When a request would move student data
   somewhere new, a shared drive, a cloud sync folder, an email, an external service, the skill
   says plainly that it is student data and confirms first, even when the transmission is
   otherwise routine.
3. **Delete what you no longer need.** A submissions folder from a graded assignment three months
   ago is a liability with no remaining use.

Unlike the token, none of this is secret in the sense of granting access to anything. It is worse
than that: it is other people's records, and they did not choose to have them on your laptop.

## Credentials

Each platform's credentials live in `<course>/.infra/<tool>/credentials`, created at mode 600.
`verify` complains if the permissions loosen or a key is blank. Environment variables work as an
override for someone teaching several courses on one account.

A Canvas token carries your full instructor permissions across **every** course your account
touches, not just this one. Canvas has no per-course tokens. Give it an expiry date and delete it
in Canvas when you stop using it.

## Dependencies

```bash
pip install piazza-api                # student-questions
pip install requests beautifulsoup4   # gradescope
```

`course_infra.py` and every Canvas script are pure standard library, no third-party packages.

## Adding a platform

`course_infra.py` reads its whole notion of a tool from the `TOOLS` dict at the top of the file:
config keys, credential keys, and the regex that finds the platform's id in a course profile. Add
an entry and `init`, `verify`, and the credential loader pick it up with nothing else changed.
Write the client as a script next to the others, and have it call `resolve`, `load_config`,
`require_credentials`, and `log_action` so it behaves like the rest.
