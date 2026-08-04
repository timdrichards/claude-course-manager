# The course folder layout

A course folder without a convention drifts within a single term. The evidence is two courses
taught by the same person in the same summer: four folders matched, and the rest did not.
`Unit Drafts` in one, `Reference Units` in the other. Nothing was wrong with either name. There
was just no answer to "where does this go," so each course answered separately.

```
<courses root>/326/
├── .infra/                    tool state, credentials, per-service config
├── course/                    survives every offering
│   ├── units/
│   ├── homework/
│   ├── labs/
│   ├── code/
│   ├── slides/
│   ├── videos/
│   ├── reading/
│   └── drafts/
└── semesters/
    ├── current -> 2026-07-summer-2
    └── 2026-07-summer-2/      belongs to exactly one run of the course
        ├── students/          gitignored
        ├── grading/           gitignored
        ├── accommodations/    gitignored
        └── announcements/
```

---

## The split, and the question that decides it

**Would this still be true if you taught the course again next year with different students?**

Yes, so it goes in `course/`: a homework spec, a lecture deck, a rubric, an autograder, a worked
example.

No, so it goes under `semesters/<term>/`: a student's accommodation letter, a grading pass, this
term's announcements, notes on who is struggling.

That boundary is the whole reason the layout exists. Rollover becomes creating a sibling folder
rather than copying everything and pruning what is stale, and the pruning step is where last
term's student records get carried into a new course by accident.

`semesters/current` is a symlink to the active term, so nothing downstream needs editing when the
term rolls. On a filesystem without symlinks the real folders are still created and the link is
skipped.

---

## Naming

Recorded per course in `.infra/course.json`, asked once, honored afterward.

| Style | Looks like |
|---|---|
| `kebab` (default) | `unit-drafts`, `reference-units` |
| `snake` | `unit_drafts` |
| `title` | `Unit Drafts` |
| `as-is` | whatever was typed |

Kebab is the default because it needs no shell quoting, survives a move between a case-insensitive
macOS filesystem and a case-sensitive Linux one, and reads cleanly in a URL or a git path.

**The semester slug is always kebab, whatever the style.** It is a sortable identifier rather than
a display name, and `Semesters/2026 09 Fall` sorts badly and quotes worse. The format is
`YYYY-MM-season[-session]`, where the month is when classes actually begin, so Summer Session II
becomes `2026-07-summer-2` and sorts after Session I's `2026-06-summer-1`.

---

## Creating and changing it

```bash
# Created automatically by init, alongside .infra
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 \
    --name "COMPSCI 326" --term "Fall 2026"

# Choose a naming style and adjust the folder set
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 \
    --naming kebab --add-folder scripts --add-folder assets --skip-folder reading

# Build or repair the layout for a course that already exists
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py layout 326

# Roll into a new term: creates the sibling, moves `current`
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py layout 326 --term "Spring 2027"

# .infra only, no material folders
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 --no-layout
```

`--add-folder` and `--skip-folder` are repeatable. A folder whose name matches a known per-term
folder lands under the semester; everything else lands under `course/`.

**Nothing is ever deleted.** Removing a folder from the configuration stops it being created; it
does not touch material already there. `verify` reports folders that are configured but missing
from disk, and folders present on disk that the configuration does not list, so drift in either
direction is visible.

---

## Student records and version control

`students/`, `grading/`, and `accommodations/` are added to the course's `.gitignore` when the
layout is created. This is a must rather than a suggestion: in the US these are FERPA-protected
education records, and in the UK and EU they are personal data under GDPR, with the instructor as
the data controller for whatever lands on their machine.

The rules append rather than overwrite, so an instructor's own entries survive, and a rerun does
not duplicate them. `announcements/` is deliberately not excluded, since what was said to the
whole class is not a private record.

Adding a per-term folder that will hold student data means adding a gitignore line for it. The
plugin's wider rules on student data at rest are in the README.

---

## Asking, rather than imposing

The default set is a starting point and not every course wants all of it. When setting up a new
course, show the defaults and ask two things:

- **What else does this course need?** Common additions: `scripts` for course tooling, `assets`
  for images and diagrams, `exams`, `projects`, `teams`, `research`.
- **What does it not need?** A course with no lab section does not need `labs`; a course with no
  assigned reading does not need `reading`.

Ask once, at creation. Record the answer in `.infra/course.json` and stop asking.

For a course that already has material, do not restructure it without being asked. Read what is
there, record that as the configuration, and say what does not match the convention. An
instructor with three years of muscle memory for `Homework/` is not helped by a silent rename.

---

## Where the other pieces live

- **`.infra/`** is tool state: credentials, per-service config, fetch inboxes, audit logs. It is
  not course material and it is not for hand-editing except for the credentials files.
- **`course/units/`** has a shape of its own: one folder per unit, plus `arc.md` for the course's
  through line. The units skill owns it, and `units.py` builds and checks it.
- **The syllabus** lives on the LMS, not in the folder. Keep a copy under `course/` if you like,
  and treat the live page as the source of truth.
- **`.canvas-cache/`** is written by the Canvas scripts in whatever directory they run from, and
  holds downloaded submissions and reports. Sensitive; see the README.
