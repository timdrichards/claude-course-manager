# The anatomy of a unit

The default shape is the `knowledge-unit` preset: a concept-first lesson built around one small
program that looks reasonable, is not, and gets repaired in front of the reader. It comes from
courses where it has been used across a full semester of units, and the rhythm inside the Notes
section is the part that no written spec usually captures.

A course can replace all of it. See "A different shape" at the end.

---

## The sections, in order

### Introduction

Two paragraphs. The first opens with the source reading's framing and narrows to what this unit
demonstrates. The second names the previous unit explicitly and states what the student will build
or observe.

> Unit 2 measured how often calls fail. This unit asks what a caller should do about it.

That sentence is doing real work. It is the difference between a course and a folder of lessons,
and `units.py arc` checks for it because it is the first thing that goes missing when a unit gets
written the night before.

### Before You Start

A short list: the source reading with its chapter or section, plus any setup the student does
first. This is also where the unit's learning objectives go, under a line like "By the end of this
unit you can:", because an objective the student never reads orients nobody.

Only list something that has a real link or a real instruction attached. An entry holding a slot
open for a video that does not exist yet is a promise the course breaks in week one.

### References

Technical links the student needs *while working*: language docs, API pages, a tool's manual. Not
the source reading, which belongs above. One Markdown link per line, `[SymbolName](url)` or
`[Short label](url)`.

### Notes, and the three beats

This is the load-bearing pattern. Structure Notes as subsections in this order:

**1. The starting problem.** A fully runnable example, usually under thirty lines, that looks
fine and carries the exact flaw this unit is about. The prose after the code walks the reader
through running it and noticing what is wrong. When the bug is nondeterministic, say so: "run this
a handful of times."

**2. An operational middle beat, only when the topic needs one.** Container management, project
setup, the mechanics of a tool. Present in tooling units, absent from concept units. Default to
leaving it out.

**3. Extending the example.** The *same* code from beat one, modified to fix the flaw. Not a new
example. Same function and variable names wherever the logic did not change, because the
difference between the two blocks is the entire lesson and every gratuitous rename hides it.

**4. Naming the pattern.** Zooms out. Names the concept in **bold** at first use, ties it to the
course's running vocabulary, and contrasts it against a concept from an earlier unit. This is
where the unit earns its position in the sequence rather than standing alone.

All code in Notes is typed by the student from the prose, never handed over as a download. Every
language or library constraint the course imposes applies to every block here.

### Exercise

Three labeled lines, each a bold label with its content inline:

- **Task:** what to build, framed as extending or modifying the Notes code.
- **Starting point:** which exact code block to start from.
- **You'll know it works when:** one observable condition. A specific printed value or status
  code, never "it should work correctly."

The third line is what makes an exercise gradable by the student themselves at midnight, which is
when they are doing it.

### Real World

The same concept applied with exactly one real world tool. Reuse a tool from an earlier unit
rather than introducing a new one, unless the concept genuinely requires it. Give the literal
setup commands, not a description of them, and a working example the student runs and observes.

### Home Exercise

Ungraded, thirty minutes or less, extends the **Real World** section rather than Notes. Same kind
of unambiguous closing condition as the Exercise. It often ends with a small script the student
writes to check their own work.

### Looking Ahead

One paragraph. Names the next unit by number and topic, and states the thread: what shifts, what
carries over. Check the next unit's own Introduction before writing it, so the two do not describe
different sequences.

---

## What the checker enforces, and what it cannot

`units.py check` reads structure. A required section that is missing is a `FAIL`. Sections in the
wrong order, a missing Notes beat, an Exercise with no **Starting point:** line, a code fence with
no language, an objective that appears in `unit.json` and nowhere in the lesson: all `WARN`.

It has no opinion about whether the broken example is well chosen, whether the contrast in beat
four is apt, or whether the exercise is the right size. Those are the questions worth spending
attention on, which is the reason for automating the rest.

Run `prose_check.py` over the finished lesson as well. It goes out under the instructor's name.

---

## A different shape

The section list lives in `.infra/course.json` under `units`, and every check follows it:

```json
"units": {
  "preset": "knowledge-unit",
  "sections": [
    {"heading": "Introduction", "required": true},
    {"heading": "Before You Start", "required": true},
    {"heading": "References", "required": false},
    {"heading": "Notes", "required": true,
     "beats": ["The starting problem", "Extending the example", "Naming the pattern"]},
    {"heading": "Exercise", "required": true,
     "fields": ["Task", "Starting point", "You'll know it works when"]},
    {"heading": "Real World", "required": false},
    {"heading": "Home Exercise", "required": false},
    {"heading": "Looking Ahead", "required": true}
  ],
  "objectives": {"min": 2, "max": 5}
}
```

- `required` decides whether an absent section is a failure or a choice.
- `beats` are the subsection headings inside that section, checked for presence and order.
- `fields` are bold labels checked for presence inside the section body.
- The order of the list is the order the checker expects on the page.

Three presets ship: `knowledge-unit` above, `lecture` for a course whose material is not built
around a runnable example, and `minimal` for a course that wants the folder and the arc without a
prescribed anatomy. Write one with `units.py shape 326 --preset lecture`, then edit the JSON.

Two rules when adapting an existing course. Read several of its units first and record what they
already do rather than what would be tidier. And keep whatever section carries the backward and
forward references, whatever it is called, because the arc checks depend on the course having
somewhere those sentences live.
