# The unit folder

A unit is a folder because a unit is more than a document. The lesson, the code the lesson tells a
student to type, the quiz that checks it, the deck that opens the class, and the render that goes
to Canvas all belong to the same thing, and keeping them together is what makes a unit possible to
revise, publish, or hand to a TA in one move.

```
course/units/
├── arc.md                      the course's through line
├── 01-http-as-a-contract/
├── 02-status-codes/
└── 09-idempotency/
    ├── unit.json               metadata, and the only machine readable file
    ├── unit.md                 the lesson
    ├── code/                   runnable examples
    ├── quiz.json               question bank
    ├── slides.html             lecture deck
    └── unit.html               generated from unit.md
```

Folder names are `NN-slug`, zero padded so they sort, with the slug in the course's own naming
style from `.infra/course.json`. `course/units/` is durable material: it survives every offering,
which is the reason it is not under `semesters/`.

**That is the default, not a requirement.** A course that already keeps its units somewhere else,
under other filenames, says so in its config and nothing gets renamed:

```json
"units": {
  "path": "Reference Units",
  "files": {"lesson": "{n}.md", "meta": "unit.json"},
  "artifacts": {"{n}-quiz.json": "optional", "{n}.html": "optional", "images": "optional"}
}
```

`{n}` is the zero padded unit number, `{number}` the bare one, `{slug}` the folder slug minus its
number. `path` is used exactly as written, relative to the course root. `units.py adopt` fills all
of this in by reading the folder, so it rarely needs writing by hand.

A repo that is not a course-manager course keeps the same config in `.units.json` at its root, and
everything works the same way. No `.infra/`, no registry entry, no layout.

---

## unit.json

```json
{
  "number": 9,
  "title": "Idempotency",
  "act": "Surviving failure",
  "summary": "A retried write stops charging twice.",
  "objectives": [
    "Explain why a retry can double charge",
    "Implement an idempotency key against a repeated request"
  ],
  "prereqs": [7, 8],
  "next": 10,
  "reading": "Chapter 5, sections 1 to 3",
  "status": "draft",
  "canvas": {"page_url": "", "page_id": null}
}
```

| Field | What it is for |
|---|---|
| `number` | Position in the sequence. Unique across the course. |
| `title` | Matched against the lesson's first heading, which Canvas uses as the page title. |
| `act` | Which act of the arc this belongs to. Optional, but all or nothing across a course. |
| `summary` | One sentence for a schedule, a syllabus row, or a listing. |
| `objectives` | What a student can do afterwards. Also written into the lesson. |
| `prereqs` | Units this one stands on. Checked to exist and to come earlier. |
| `next` | The unit that follows. Set automatically when the next unit is created. |
| `reading` | The source reading, echoed in Before You Start. |
| `status` | `draft`, `ready`, or `published`. |
| `canvas` | Where this unit lives on Canvas once posted, so a later run updates it. |

Metadata is JSON rather than front matter in the Markdown for two reasons. The Python here is
standard library only, and there is no YAML parser in it. And front matter leaks into a naive
render, which is how a page ships to students with `objectives:` printed at the top.

---

## The commands

```bash
# What exists, with acts, objectives, status, and which artifacts are present
units.py list 326
units.py list 326 --json

# Take over a folder of units that already exists. Preview, then write.
units.py adopt 426 --path "Reference Units"
units.py adopt 426 --path "Reference Units" --write

# Create one. Repeat --objective and --prereq as needed.
units.py new 326 --number 9 --title "Idempotency" --act "Surviving failure" \
    --prereq 7 --objective "Implement an idempotency key"

# One unit, or every unit, against the course's section contract
units.py check 326 9
units.py check 326

# The units against each other
units.py arc 326

# Show the section contract; --preset writes one into .infra/course.json
units.py shape 326
units.py shape 326 --preset lecture

# Where a unit lives, for piping into another command
units.py path 326 9
```

Every command takes a course name or a path, the same as the rest of the plugin. `check` and `arc`
exit 1 when anything is a `FAIL`, so they work in a pre-publish step.

### What `adopt` does

Reads the folder and writes down what it finds. It works out the lesson filename by what most units
share, so a setup folder holding several documents does not set the convention for the course. It
lists the other per-unit files as optional artifacts, ignoring one-offs that only one unit has. Then
it writes a metadata file per unit, with the number from the folder and the title from the lesson's
own first heading, chaining `next` down the sequence.

It writes nothing without `--write`, renames nothing ever, and skips any unit that already has
metadata. Objectives come out empty, which is the honest answer: nothing can infer them from prose.

### What `new` does

Creates the folder, writes `unit.json`, and writes a skeleton `unit.md` holding this course's
sections in order, with the objectives already placed under Before You Start. It creates `code/`
when the course's config lists it. It refuses to overwrite anything, refuses a number that already
exists, and sets the previous unit's `next` pointer when that unit has not set one itself.

The skeleton's empty sections are reported by `check` as `empty-section` until they are written,
so a half finished unit is visible rather than quietly publishable.

---

## Finding levels

| Level | Meaning |
|---|---|
| `FAIL` | Structurally broken. A missing required section, a duplicate unit number, a prerequisite pointing forward or at nothing. Fix before publishing. |
| `WARN` | Almost always wrong, occasionally the course being deliberately unusual. Read and decide. |
| `NOTE` | Information. A repeated objective, a missing arc document, an unfamiliar objective verb. |

The checker never rewrites a file. It reports and explains, for the same reason `prose_check.py`
does: the judgment about a course belongs to the person teaching it.

---

## Status and publishing

`status` moves `draft` to `ready` to `published`, by hand or when a run posts the page. Setting it
is what lets `list` answer "what is actually live for students right now", which is the question
that comes up at 8am on the day of class.

The Canvas fields get filled by the publishing pass, so the next render updates the existing page
instead of creating a second one with the same title. Details in `canvas-render.md`, beside this
file.

---

## Adding an artifact kind

The `artifacts` map in the units config decides what `list` reports and what `check` insists on:

```json
"artifacts": {"code": "optional", "quiz.json": "required", "handout.pdf": "optional"}
```

`required` makes an absent file a `FAIL` on every unit, which is a strong statement. Use it for the
one or two things this course genuinely never ships without.
