# Rolling a syllabus into a new term

A new offering gets a new page. The old one is the record of what students were actually told,
and grade disputes and accreditation review both reach backward.

The risk in a rollover is not what gets missed. It is what gets **silently carried forward**: a
date that still parses, a platform id that still resolves, a policy that was a one-term
experiment. Everything that cannot be verified for the new term gets flagged rather than copied.

---

## Order of operations

**1. Decide whether this is a new folder or a new term inside the existing one.**

A course whose material carries forward wants a **new term inside the same folder**. The layout
already separates the two: `course/` stays exactly as it is, a sibling appears under `semesters/`,
and `current` moves to point at it. Last term's students, grading, and accommodations stay
untouched where they are.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py layout 326 --term "Spring 2027"
```

A course being rebuilt from scratch, or one where the old folder should be frozen as a record,
wants a **new course folder**:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326-s27 \
    --name "COMPSCI 326" --title "Web Programming" --term "Spring 2027" \
    --institution "UMass Amherst"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326-s27 --tool canvas \
    --base-url https://umamherst.instructure.com --course-id <new id>
```

Either way, do not edit last term's syllabus page in place. That page is the record of what
students were actually told.

**2. Fetch last term's syllabus from the live page**, not from a local copy. Mid-term edits are
exactly the changes worth carrying, and they are the ones a stale local copy lacks.

**3. Start the new profile from the old one**, updating rather than rewriting. The accumulated
notes about voice, common student mistakes, and what confused people last time are the most
valuable thing in it.

**4. Draft the new syllabus, then audit it against the new course** before publishing.

---

## Everything that must change

Work this list explicitly. Each item is a real failure someone has shipped.

**Dates.** Term start and end, every schedule table row, every deadline, the final deliverable,
the drop deadline if referenced. A date from last term still parses as a valid date, so nothing
errors; it is just wrong.

**Platform identifiers.** LMS course id, base URL if the institution moved, forum class id,
autograder course id, repository organization. **Every one of these changes between terms**, and
a stale id is how work lands in last semester's section. `course_infra.py verify` cross-checks
each against the profile and reports a MISMATCH; run it before anything is published.

**Term-shaped policy.** A policy tuned to a six-week summer session is wrong for a fifteen-week
fall. The time-commitment section in particular must be re-derived: the total hours are fixed by
credits, but the weekly rate is a function of the calendar. The advice that follows from it
changes too, since "do not pair this with another course" is honest advice for a compressed term
and needlessly alarming for a normal one.

**Staff.** Instructor, TAs, emails, office hours. TAs change every term and a syllabus naming
last term's is a small failure that reads badly.

**Enrollment-dependent choices.** Group sizes, discussion mechanics, and office-hour format that
worked at seventeen students may not at two hundred.

**Tool versions and stack.** Every tool the syllabus names, checked against what the course will
actually use. Last term's mid-term switch may or may not carry forward.

**Textbook edition and access link.** Institutional access arrangements lapse.

**Institutional boilerplate.** Accommodations processes, honesty policy links, and support
resources change. Phone numbers and office names go stale quietly.

---

## Everything that must be reconsidered rather than copied

These carried forward correctly last term and still deserve a decision:

- **Mid-term policy changes.** Anything added in response to a problem last term. It should
  usually stay, but now it can be written into the syllabus from day one instead of patched in at
  week three. Note in the profile that it now applies from the start.
- **Weights.** They encode what the course was teaching. If the assignment plan changed, they
  should.
- **Anything that was an experiment.** A new deliverable, a new participation format, a new
  grading split. Ask whether it worked before it becomes permanent by inertia.
- **The schedule's shape.** Number of units, what runs in parallel, where the offset falls.
- **Learning objectives.** The section most likely to be stale, because nothing breaks when it is.

---

## What carries forward cleanly

Course description and pedagogical stance. Prerequisites. The structure of policies, even where
the numbers change. Communication conventions. Support resources, once verified. The section
ordering and house style.

---

## Flagging rather than guessing

Anything that cannot be verified for the new term gets `[CHECK: ...]` in the draft and a line in
the summary. A rollover typically ends with ten to twenty markers; that is a healthy sign that
the copy was not blind.

List every marker at the end of the draft, grouped by what the instructor needs to look up:
academic calendar, staff assignments, platform setup, enrollment.

---

## Retiring the old term

Once the new syllabus is published, `unregister` the old course so `list` stays readable. The
folder stays exactly where it is with its `actions.log`, its student notes, and its record of
what was actually told to whom. Nothing is deleted.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py unregister "COMPSCI 326"
```
