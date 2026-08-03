---
name: course-setup
description: >
  Set up, register, inspect, and maintain the course folders that every other course skill
  reads from. Use when the user says "set up a new course", "add Canvas to 326", "connect
  Gradescope", "what courses do I have", "check my course setup", "where do my courses live",
  "my Piazza credentials aren't working", "build a course profile", "update the course profile",
  "start a new semester", or "roll 326 over to spring". Also use whenever another course skill
  reports that a course folder, profile, or credential is missing, and at the start of any task
  that touches Canvas, Piazza, or Gradescope, to confirm which course is being worked in. Do NOT
  use for drafting syllabi, answering student questions, or grading; those have their own skills.
---

# Course Setup

Own the shared substrate: which courses exist, where they live, which platforms each one is
connected to, and what the course profile says. Every other skill in this plugin reads what this
one writes.

## The layout

A course is a folder with three parts: tool state, material that outlives the term, and material
that does not.

```
<courses root>/326/
├── .infra/                    tool state, never hand-edited except credentials
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

Two splits, both deliberate. Things describing the **course** sit directly under `.infra` and are
read by every skill; things describing one **service** live in that service's folder. And material
that **survives the next offering** sits under `course/`, while material tied to **one term** sits
under `semesters/<term>/`.

The question that decides the second split: would this still be true if you taught the course
again next year with different students? A homework spec would. An accommodation letter would not.
Getting it right makes rollover a new sibling folder rather than a copy-and-prune, and pruning is
where last term's student records get carried forward by accident.

Folder naming is per course and recorded in `course.json`, defaulting to lowercase with hyphens.
The semester slug is always `YYYY-MM-season[-session]` regardless of naming style, because it has
to sort. Read `references/layout.md` before creating or changing any of this.

`scripts/course_infra.py` owns all of it; never scatter state anywhere else.

Courses do not all have to live in one place. A registry at `~/.config/claude-courses/registry.json`
records where each one is, which is what lets every script take `--course 326` instead of a path.
The registry is an index, never the source of truth: delete it and everything still works from
explicit paths.

All scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/`. Run them with `python3`.

## Establishing which course, every time

Before any task that reads or writes course data, confirm the course. This is one command and it
is the whole defense against work landing in the wrong section:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326
```

`verify` prints the course identity, which platforms are configured, each one's class id,
whether credentials are present and readable only by the owner, the write mode, and the last
write to each service. Say the course and term back in one line before acting.

Deal with what it reports before doing anything else:

- A **MISMATCH** means the profile and a tool's config name different classes. Stop. This is
  exactly the state a folder copied from last term is in, and it is how an announcement meant for
  one section reaches another. Ask which is right; do not write anything until it is resolved.
- **Missing credentials** or a **world-readable credentials file** is worth one plain sentence and
  the exact command to fix it, not a lecture.
- **No profile** means most skills cannot do their job well. Offer to build one now.

## Creating a course

Ask for the identity first: number, title, institution, term. Then pick where courses live, if it
has not been set:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py set-root ~/courses
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 \
    --name "COMPSCI 326" --title "Web Programming" \
    --term "Fall 2026" --institution "UMass Amherst"
```

`init` only adds what is missing and never overwrites, so it is safe on a folder that already
holds course material. Point it at an existing folder to adopt it rather than starting fresh.

**Then ask about the folders, once.** `init` creates a default set, and the defaults are a
starting point rather than a prescription. Show them and ask two questions:

- What else does this course need? Common additions are `scripts` for course tooling, `assets` for
  images and diagrams, and `exams`, `projects`, or `teams`.
- What does it not need? A course with no lab section does not need `labs`.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 \
    --add-folder scripts --add-folder assets --skip-folder reading
```

Both flags repeat. The answer is recorded in `course.json`, so this is asked at creation and not
again. Offer the naming style only if the user brings it up or the course already uses something
other than the default; `--naming` takes `kebab`, `snake`, `title`, or `as-is`.

**For a folder that already holds material, do not restructure it.** Read what is there, record it
as the configuration, and say plainly what does not match the convention. An instructor with three
years of muscle memory for `Homework/` is not helped by a silent rename. `references/layout.md`
covers the whole thing.

Then add each platform the course uses. Read `references/platforms.md` for where to find each id
and token, what SSO does to each one, and what to tell the user about the risk of each credential:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 --tool canvas \
    --base-url https://umass.instructure.com --course-id 123456
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 --tool piazza \
    --course-url https://piazza.com/class/<id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 --tool gradescope \
    --course-id 753413
```

Each creates a `credentials` file at mode 600 with the right keys and a comment explaining them.
Tell the user which files need filling in and stop there. Never ask for a password or token in
chat, and never write one into a file yourself: they belong in a file the user edits, or in
environment variables.

After the credentials are in, run `verify` again and report what turned green.

## The course profile

The profile is the difference between output that sounds like a competent stranger and output
that sounds like the person teaching the course. Every other skill reads it. It lives at
`.infra/course-profile.md`.

Build one by running the interview in `references/course-profile.md`. Ask for documents before
asking questions: one syllabus and one assignment spec answer most of it, and reading them is
faster and more accurate than an interview. Record every platform id in the profile, since
`verify` cross-checks those against each tool's config and that check is what catches drift.

Deliver a copy with `SendUserFile` as well as writing it into the folder, so it survives
independently of any one machine.

**Keeping it current matters more than getting it perfect.** A stale profile is dangerous in a
specific way: confidently wrong rather than obviously empty. The current-week and current-
assignment sections go stale within days. When something implies the course has moved on, say so
and offer to update. Update in place so accumulated detail about voice and common mistakes is not
lost.

## Checking on things

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py list        # every registered course
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326  # one course, all platforms
```

When the user asks a broad question like "check my course setup", run `list`, then `verify` on
each course, and report as a short table: course, term, platforms connected, and any problems.
Lead with problems. A setup with nothing wrong deserves one line, not a status report.

## Starting a new term

A new offering is a new folder, not an edited one. The old one is the record of what actually
happened last time, and the profile's accumulated notes on common student mistakes are worth
keeping intact.

Create the new course, copy over the syllabus and materials the user wants carried forward, then
build the new profile by starting from the old one and updating: term, schedule, current
assignments, platform ids. Every platform id changes between terms, and stale ids are the single
most likely way to write into last semester's class. Run `verify` before anything is posted.

Offer to `unregister` the old course so `list` stays readable. The folder stays where it is;
only the index entry goes.

## When something is wrong

Read `references/troubleshooting.md` for credential failures, SSO, permission errors, corrupt
state, and how to reset each platform's state without losing course data.

## References

- `references/course-profile.md`: the interview, the profile template, and how to keep a profile
  current. Read when building or revising a profile.
- `references/layout.md`: the course folder layout, the durable/per-term split, naming styles,
  and how student-record folders get gitignored. Read before creating or changing a layout.
- `references/platforms.md`: per-platform setup: where each id lives, how to make a Canvas token,
  what SSO breaks, and what each credential can do if it leaks. Read when connecting a platform.
- `references/troubleshooting.md`: what each failure means and what to do about it. Read when
  `verify` reports a problem or a script fails.
- `references/house-style.md`: voice and formatting rules shared by every skill in this plugin
  that drafts something a student will read. A course profile's `Voice` section overrides it.
- `references/ai-tells.md`: how to keep drafted prose from reading as machine output,
  and `scripts/prose_check.py`, the check that enforces it. Read before drafting.
