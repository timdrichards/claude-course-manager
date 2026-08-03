# Reviewing and auditing a syllabus

Two jobs. The first asks whether the document contradicts itself. The second asks whether it is
still true. Do both, and lead the report with the second, because a syllabus that is merely
inelegant costs nothing and a syllabus that is wrong costs a grade dispute.

---

# Part 1: Internal consistency

Read the document as a hostile reader looking for a loophole, because in week eleven someone will.

## Grading integrity

- **Weights sum to exactly 100.** Verify the arithmetic; do not trust a stated total.
- **Every graded category in the text appears in the weights table**, and vice versa. A category
  described in prose but missing from the table has no defined weight.
- **Counts match reality.** "6 weekly quizzes" against a schedule table with five.
- **Drops are reflected in the math.** If the lowest of ten is dropped, the weighting has to
  describe nine contributing, and the table should say so.
- **Auto-graded work carries a disclaimer** that autograder output is provisional and the
  instructor may adjust.
- **Sub-row weights sum to their category weight** where a category is broken out per instance.
- **Rubric totals quoted in the syllabus match the real rubric objects.** These are two copies of
  one fact. The live rubric wins; the syllabus gets corrected.

## Policy completeness

Each of these either appears or is deliberately absent: late work, extensions, AI use, academic
honesty, collaboration, regrades, accommodations, incompletes, submission mechanics,
communication, grading scale.

- **The late policy names every graded category by name.** The most common defect. Text that says
  "assignments may be turned in late" in a course that also has labs, sprints, and quizzes leaves
  three categories undefined, and the gap is only discovered when a student submits one late.
- **Categories with hard deadlines say so and say why.**
- **The AI policy states permitted use, prohibited use, and the disclosure requirement**, with
  concrete examples rather than abstractions.
- **The disclosure burden is proportionate.** A requirement nobody can enforce is worse than a
  lighter one that gets followed.
- **Accommodations point at the actual office and process**, and note the registration window
  against the term length in a compressed term.

## Structural

- Heading hierarchy is shallow and consistent.
- Every cross-referenced section exists under the name used to reference it.
- The schedule table's weeks, dates, and content align with the prose.
- Dates are internally consistent: a term start in prose matching the first row of the schedule.
- Facts stated in more than one place agree. Any fact stated twice is a fact that will drift; the
  fix is usually to state it once and reference it.

## Clarity and style

- No em-dashes. En-dashes in number ranges are fine.
- No passive voice in policy language.
- No invented specifics: a room, a time, a phone number, a name that cannot be verified.
- Nothing addressed to the instructor rather than to students. Draft notes leak.

---

# Part 2: Drift from the live course

The audit that finds real problems. The syllabus was true when written; the course moved.

Confirm the course first, then pull the live state:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326 --tool canvas
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 assignments --json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /courses/:course/assignment_groups \
    --all --param "include[]=assignments"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /courses/:course/late_policy
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /courses/:course/quizzes --all
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /courses/:course/modules --all
```

## What to compare

**Assignment counts.** The syllabus says four homeworks, six quizzes, five sprints. Count the
real published assignments per group. A count that is short usually means unbuilt work; a count
that is over usually means the syllabus was never updated when something was added.

**Category weights.** If the course uses weighted assignment groups, compare each group's
`group_weight` against the syllabus table row by row. These drift silently and they change every
student's grade.

**Assignment group membership.** An assignment created without an explicit group lands in the
default group. In a weighted course that quietly changes the math while every individual number
still looks right.

**The late policy configuration.** Compare `/late_policy` against the text.
`late_submission_deduction` is the percentage, `late_submission_interval` is per day or per hour,
`late_submission_minimum_percent` is the floor. **A floor is not a cutoff.** A syllabus promising
"zero after two days" against a policy configured with a 50% floor and no cutoff is a real
contradiction that surfaces as a grade nobody can defend. This exact mismatch is common.

Also check `missing_submission_deduction_enabled`, since a course that auto-zeroes missing work
should say so.

**Quiz mechanics.** Compare stated question count, time limit, attempts, and scoring policy
against the real quiz objects. A syllabus saying "approximately twenty questions" against quizzes
that deliver twelve is a promise nobody meant to make.

**Due dates and the weekly cadence.** Spot-check that the schedule table's weeks match real
`due_at` values. Remember that `due_at` on an assignment with overrides can report an override's
date rather than the base date; verify against a control student's `cached_due_date` before
concluding the syllabus is wrong.

**Tool and technology names.** Grep the syllabus for every tool it names and confirm the course
still uses it. This is where the Prisma-to-MongoDB class of drift lives, and it hides in learning
objectives and assignment descriptions rather than in the obvious places.

**Content unit titles.** Compare the schedule table's unit names against the live pages and
modules. Renamed units leave the syllabus behind.

**Participation mechanics.** If the syllabus describes six participation tasks, count the real
discussions and reflections. Counts here drift more than anywhere else because the work is small.

**Term dates.** The last day of class, the final deliverable date, and the first week's start.

---

## Reporting

Group findings as **Drift from the live course**, **Grading integrity**, **Policy completeness**,
**Structural**, **Clarity**. Drift goes first.

Per finding: quote the syllabus text, state the live value, say which is right or that the user
must decide, and give the specific fix.

```
**Late policy cutoff.** The syllabus says "Zero after two days." Canvas's late policy is
configured with a 50% floor and no cutoff, so a submission three days late currently scores
50%, not 0. Either change the Canvas configuration or change the sentence. These cannot both
stand.
```

End with a verdict: ready, needs minor fixes, or needs major revision. A single drift finding
that changes grades is enough for major revision on its own.

**Do not fix anything during an audit.** Report, get direction, then edit. An audit that silently
corrects things gives the instructor no chance to notice that the course, rather than the
syllabus, is what went wrong.

---

## After the audit

Two follow-ups that are easy to skip:

- **A policy change mid-term needs an announcement**, not just a syllabus edit. Hand it to
  course-comms. A rule students were never told about cannot be applied to work already
  submitted, and a policy that did not exist last week does not apply retroactively.
- **Update the course profile** so grading, assignments, and student-questions answer policy
  questions consistently with whatever the syllabus now says.
