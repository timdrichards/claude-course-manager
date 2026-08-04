---
name: units
description: >
  Write and maintain course units: numbered lessons with a fixed section shape, learning
  objectives, prerequisites, and a place in the course's story arc. Each unit is a folder holding
  the lesson, its code, its quiz, its slides, and its Canvas render. Use whenever the user says
  "unit", "knowledge unit", "KU", "module", "lesson", references unit numbering like "Unit 9" or
  "09.md", asks to draft a unit on some topic, asks for a unit's quiz or slides or Canvas page, or
  asks about the shape, order, objectives, prerequisites, or arc of the units in a course. Also use
  to audit an existing sequence: numbering gaps, units that do not reference their neighbours,
  objectives that are never stated, or a course that reads as a pile of lessons rather than one
  argument. Do NOT use for a single assignment spec, which is the assignments skill, or for
  building the deck itself, which this skill plans and hands to lecture-decks.
---

# Units

A unit is the smallest piece of a course a student experiences as complete. It has a number, it
teaches something nameable, and it sits between the unit before it and the unit after it. That
last part is where courses fail. Fifteen individually good units, each written in the week it was
needed, produce a semester that no student can summarize afterwards.

So a unit here is a folder with a contract, and the units together have a second contract with
each other.

```
course/units/
├── arc.md                      the through line: the question, the acts, the payoff
├── 01-http-as-a-contract/
└── 09-idempotency/
    ├── unit.json               number, title, act, objectives, prereqs, status
    ├── unit.md                 the lesson
    ├── code/                   what the lesson tells them to type
    ├── quiz.json               a question bank in upload_quiz.py's shape
    ├── slides.html             the lecture deck
    └── unit.html               the Canvas render
```

## Step 0: establish the course

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/units.py shape 326
```

Load `.infra/course-profile.md` for the term, the voice, the stack this course actually teaches,
and what students have already covered. A unit that uses a concept from three weeks out is not a
lesson, it is a wall. Read
`${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md` before writing prose; the
profile's `Voice` section overrides it.

## The shape belongs to the course, not to this skill

`units.py shape` prints the section contract recorded in `.infra/course.json`. A course that has
never set one gets the `knowledge-unit` preset: a concept-first lesson built around a runnable
example that starts broken and gets repaired. Two other presets exist, and any course can edit the
list into something neither of them resembles.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/units.py shape 326 --preset knowledge-unit
```

Set it once, early, with the instructor looking at it. Every later check reads their version.
`references/unit-anatomy.md` has each section, what belongs in it, and the three beats inside the
Notes section that carry the teaching.

## A course that already has units

Most do, in a folder someone named, under filenames someone chose. Adopt it rather than converting
it. Nothing gets renamed or moved.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/units.py adopt 426 --path "Reference Units"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/units.py adopt 426 --path "Reference Units" --write
```

The first form is a preview and writes nothing. Adoption reads the folder, works out what the
course calls its lessons and its other files, records that, and writes one metadata file per unit
with the number and the title taken from each lesson's own heading. It never overwrites metadata
that already exists. A repo with no `.infra/` gets a `.units.json` at its root rather than being
made to become a course-manager course first.

Read three of the existing units in full before proposing any shape, and record what they already
do. An instructor with eleven units in one style is not helped by a twelfth in another.

Objectives come out of adoption empty, because no tool can infer them. Filling them in is the next
piece of work and the one that makes everything downstream worth running.

## Before writing a single unit

Four reads, and skipping them is what produces a unit that stands alone:

1. `arc.md`, for where this unit sits in the course's argument.
2. Unit N-1 in full. Its Looking Ahead has already promised something about this unit.
3. Unit N+1, if it exists, so this unit's own closing does not misdescribe it.
4. The source reading this unit is anchored to, named in Before You Start.

## Creating one

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/units.py new 326 --number 9 --title "Idempotency" \
    --act "Surviving failure" --prereq 7 --prereq 8 \
    --objective "Explain why a retry can double charge" \
    --objective "Implement an idempotency key against a repeated request"
```

That writes the folder, `unit.json`, and a skeleton with this course's sections in order. It also
sets unit 8's `next` pointer, so the sequence knows about the new arrival.

Objectives are the argument of the whole thing, so write them before the prose. Each one is
something a student does where someone can watch: implement, trace, compare, predict, debug.
Nobody can check whether a student understands. The skeleton puts them under Before You Start,
which is where the student sees them, and the checker holds the two copies together.

## Writing the lesson

`references/unit-anatomy.md` is the working reference, and `references/worked-example.md` is a
full annotated unit to write against. The parts that matter most:

- The Introduction names the previous unit explicitly and says why this one follows it.
- Notes moves through a small broken example, the same example repaired, then the concept named
  in bold and contrasted against an earlier unit. Same variable names across the two code blocks,
  because the diff is the lesson.
- The Exercise gives a Task, a Starting point, and an observable success condition. A specific
  printed value, not "it should work."
- Looking Ahead names the next unit by number and topic, and says what carries over.

Every code block declares a language, every example runs, and code that a hundred students will
type gets tested before it ships.

## Checking it

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/units.py check 326 9
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/units.py arc 326
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prose_check.py course/units/09-idempotency/unit.md
```

`check` reads one unit against the course's contract: required sections, their order, the Notes
beats, the labeled exercise lines, unlabeled code fences, objectives that appear in the metadata
and nowhere a student can see.

`arc` reads the units against each other, and it is the one worth running most often. Numbering
gaps, a prerequisite that points forward, an act whose units are not consecutive, a Looking Ahead
that promises a unit that no longer follows. None of that is visible from inside a unit, which is
why it survives a term. `references/course-arc.md` covers the acts, the objective inventory, and
how to audit a sequence that already exists.

Fix every `FAIL`. Read every `WARN` and decide, because some of them are the course being
deliberately unusual. `NOTE` is information.

## The rest of the unit

Produce these when asked, or when the sibling units already have one.

| Artifact | Built by |
|---|---|
| `unit.html` | `render_html.py`, then the canvas skill posts it |
| `quiz.json` | this skill, then `upload_quiz.py` uploads it |
| `slides.html` | the lecture-decks skill, from the unit |
| a deep dive on one tool | this skill, on explicit request only |

`references/unit-artifacts.md` has the quiz schema, what a unit deck should and should not carry,
and when a supplementary document earns its place. `references/canvas-render.md` covers the
Markdown to Canvas pipeline, which exists because Canvas strips every `<style>`, `<link>`, and
`<script>` from a page body.

## Publishing

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_html.py course/units/09-idempotency
```

The renderer verifies its own output and refuses to call a file good if it still holds a tag
Canvas removes. Hand the HTML to the canvas skill's page workflow rather than posting it here, and
record the resulting page in `unit.json` under `canvas` so the next run updates rather than
duplicates. Set `status` to `published` at the same time.

Nothing goes to students until the instructor has seen the exact change.

## Always

- Never invent a course fact: a date, a reading, a tool version, a point value. Mark the gap
  `[CHECK: ...]` and list the markers when handing the unit over.
- A unit that does not name its neighbours is a handout. The two sentences that tie it backward
  and forward are the cheapest structure in the course and the first thing lost under deadline.
- Reuse the course's own examples. A student who met `fetchUser` in unit 3 should meet
  `fetchUser` again in unit 9.
- One new real world tool per unit at most. Reach for a tool from an earlier unit first.
- When the instructor asks for a unit on a topic that duplicates an existing unit's objectives,
  say so before writing it.

## References

- `references/unit-anatomy.md`: every section, the Notes beats, the exercise shape, and how to
  configure a course whose units look nothing like the preset.
- `references/worked-example.md`: one full unit, annotated, when a concrete model beats a
  description of one.
- `references/course-arc.md`: acts, objectives across a whole course, the `arc.md` document, and
  auditing a sequence that already exists.
- `references/unit-folder.md`: the folder, the `unit.json` fields, and every `units.py` command.
- `references/unit-artifacts.md`: the quiz bank, the unit deck, and supplementary documents.
- `references/canvas-render.md`: Markdown to inline styled HTML, and the handoff to Canvas.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md`: voice and formatting,
  shared with every drafting skill here.
