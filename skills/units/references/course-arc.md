# The arc

A student who finishes a course should be able to say what it was about in one sentence, name the
few big moves it made, and know what they can now do that they could not do in September. Most
courses cannot survive that test, and the reason is visible in the folder: fifteen units, each
written the week it was taught, each individually competent.

The arc is the structure that prevents it. It is three things: a document that states the course's
argument, a grouping of units into acts, and a set of checks on how the units refer to each other.

---

## The arc document

`course/units/arc.md`, one page, written before the units or reconstructed from them. Ask the
instructor for the first two answers rather than inventing them.

```markdown
# The arc of COMPSCI 326

## The question
One sentence. What does this course answer that a student cannot answer now?

## What a student can do at the end
Three to six capabilities, phrased the way the unit objectives are phrased. This is the
promise the whole sequence is making, and every unit objective should ladder into one of them.

## The acts

### Act 1: <name>  (units 1-4)
The question this act answers, and the capability a student leaves it with.
Why it has to come first.

### Act 2: <name>  (units 5-9)
...

## What this course deliberately does not cover
The topics students will reach for anyway. Naming them here is what stops a unit
from quietly absorbing one.
```

The last section keeps its value all term. A course that has not written down its boundaries grows
a unit on whatever the loudest three students asked about in week six.

---

## Acts

An act is a run of consecutive units that answers one question together. Four or five units is
typical, three acts across a semester is common. Record the act on each unit:

```json
{"number": 9, "title": "Idempotency", "act": "Surviving failure"}
```

and declare the act list in the course config so a typo is visible rather than silent:

```json
"units": {
  "acts": [
    {"name": "The request", "question": "What actually crosses the wire?"},
    {"name": "Surviving failure", "question": "What happens when it does not arrive?"},
    {"name": "Scaling out", "question": "What breaks when there are ten of everything?"}
  ]
}
```

`units.py arc` then reports three things that are otherwise invisible:

- A unit belonging to no act. Either it is part of the story or it is an interruption in it.
- An act whose units are not consecutive. An act interrupted by unrelated material is not an act,
  it is a label.
- An act named in a unit that the course never declared, which is almost always a spelling of an
  act that does exist.

Acts are optional. Half applied acts are worse than none, which is why the checker says so.

---

## Objectives across the course

Objectives live in `unit.json` and appear in the lesson under Before You Start. They carry the arc
because they are the only part of a unit written in the student's terms.

Each one names something observable: implement, trace, compare, predict, debug, measure, justify.
"Understand" and "learn" describe a state nobody can check, and the checker flags them.

Two per unit is a reasonable floor and five a reasonable ceiling. A unit promising seven things
usually delivers two and mentions five.

Across the course, ask three questions the tooling cannot:

1. **Does every objective ladder into the arc document's list of end capabilities?** An objective
   that serves nothing in that list is either a missing capability or a unit that drifted.
2. **Is every end capability delivered by some unit?** A promise in the arc with no unit behind it
   is the gap students find in the final project.
3. **Is anything assessed?** An objective with no exercise, no quiz question, and no assignment
   touching it is a claim the course never tests.

`units.py arc` reports the same objective claimed by two units. Deliberate reinforcement is fine.
An accident means one of the two is doing less than it says.

---

## The thread between neighbours

Two sentences per unit carry the entire sequence, and both are checked:

- The Introduction names the previous unit and says why this one follows it.
- Looking Ahead names the next unit by number or title and states what carries over.

These break for a boring reason. A unit gets inserted, or two get swapped, and the neighbours keep
describing a sequence that no longer exists. The student reads a closing paragraph promising a
topic that never arrives. Run `arc` after any reordering, before anything is published.

---

## Auditing a course that already exists

For a course with units already written, in this order:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/units.py list 326
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/units.py arc 326
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/units.py check 326
```

1. **Read the existing units before changing anything.** Record their real shape into the config
   rather than imposing a preset on eleven units written another way.
2. **Backfill `unit.json` from what is already there.** Number, title, and objectives can usually
   be read out of the lesson. Objectives usually cannot, because most units do not state them, and
   writing them is the single highest value pass over an existing course.
3. **Group the units into acts on paper first**, with the instructor. If the units resist
   grouping, that is the finding, and it is worth more than any individual fix.
4. **Then write `arc.md`,** and let it disagree with the units. The disagreements are the work
   list for the next offering.

Report what the audit found as a short list of what the sequence promises, what it delivers, and
where those two differ. Do not silently renumber, reorder, or rewrite anything. A course is
someone's teaching, and the last three years of muscle memory around it are real.
