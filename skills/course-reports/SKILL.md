---
name: course-reports
description: >
  Compute end-of-term grades and report on student activity and risk, from Canvas data. Use when
  the user says "who's falling behind", "at-risk students", "who hasn't submitted", "compute final
  grades", "end of term grades", "final grade report", "grade audit", "letter grades", "weighted
  totals", "activity report", "how is the class doing", "who should I check on", or asks for a
  status report on the class as a whole. Also use at the end of a term, before grades are
  submitted, to audit what Canvas will report. Do NOT use for scoring an individual submission,
  which is grading, for writing the message to a struggling student, which is course-comms, or for
  raw Canvas reads and writes, which is canvas.
---

# Course Reports

Two reports, one shape: pull the whole course's state in a handful of calls, compute something the
Canvas gradebook will not, and write a standalone HTML document plus a JSON snapshot that the next
run can diff against.

- **The grade report**: weighted totals, letter grades, and the audit that catches what bites at
  submission time: ungraded work, boundary cases, weights that do not add up, and
  missing-versus-excused confusion.
- **The activity report**: who is disengaging, who has missing work, who dropped ten points since
  last week, plus a todo list for the instructor derived from the same pull.

Both read grades and identities for the entire roster. That is the most sensitive data this plugin
touches, and it lands on the user's disk. Read "Writing student data to disk" below before the
first run.

## Before anything

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 whoami
```

Say the course name and term back in one line. A grade report computed against the wrong section
is worse than no report, because it looks right.

Every Canvas call these reports make goes through the canvas skill's tooling, `canvas.py` for
REST and GraphQL, the reference files there for what each endpoint returns. Read
`${CLAUDE_PLUGIN_ROOT}/skills/canvas/references/submissions-grades.md` before the grade report and
`.../students-enrollments.md` before the activity report. Nothing here writes to Canvas.

## There is no script here, by design

Every other capability in this plugin that repeats a mechanical operation across many objects has
a script. These two do not, and that is deliberate: the weighting scheme and the letter bands are
course-specific, so the interesting part is not the fetching, it is the arithmetic that encodes
one course's rules. Code that guessed those rules would be wrong in a way nobody would notice
until final grades were submitted.

So: fetch with `canvas.py`, compute in context, write the HTML and JSON with the Write tool, read
prior snapshots with the Read tool. A report snapshot is one JSON object written once per run,
already fully computed, it earns no script.

The consequence is that the arithmetic is not covered by the test suite. State the formula you
used in the report's methodology section, every time, so it can be checked by a human who knows
the course.

## Computing a grade, and the rules that are easy to get wrong

The full procedure is in `references/grade-report.md`. Four rules carry most of the risk:

- **Excused work shrinks the group; it is not a zero.** Exclude `excused` submissions from both
  the numerator and the denominator. Counting an excusal as zero is the single most damaging
  arithmetic error available here, and it lands hardest on the students who most needed the
  excusal.
- **Exclude assignments with `omit_from_final_grade: true`.** Canvas does; a hand recompute that
  forgets to will disagree with the gradebook and the gradebook will be right.
- **Normalize by the weights of groups that actually have gradeable work.** Otherwise a group with
  nothing graded yet counts as 0% and every mid-semester grade reads far too low.
- **Read the letter bands from the course's `grading_standard_id`** rather than hardcoding a
  scale. Schemes vary by institution, department, and country. If no standard is attached, confirm
  the bands with the user or the syllabus, and say in the report where they came from.

Report Canvas's own `current_score`/`final_score` as the source of truth **and** an independent
recompute as the audit. Where they disagree, name the assignment responsible. A recompute that
merely agrees with Canvas has still earned its keep, because the disagreements are the findings.

## At-risk flagging

`references/activity-report.md` has the thresholds and the data pull. The judgment part:

- A student is "of concern" if **any** threshold trips, and the report lists **every** reason that
  fired, never just the first. "Inactive 6d, missing ×3" is a different conversation from either
  one alone.
- Thresholds are defaults, not findings. Any of them can be overridden per run, and whichever were
  overridden get named in the methodology section.
- The output is a list for a human to act on, not a verdict. Nothing here emails a student, flags
  an academic concern, or writes anything into Canvas. When the user wants to reach out, hand the
  list to course-comms.

## Writing student data to disk

Both reports write real student records, names, emails, grades, at-risk flags, to
`./.canvas-cache/<course_id>/reports/`. In the US these are FERPA-protected education records; in
the UK and EU they are personal data under GDPR. The user is the data controller for whatever
lands on their machine.

Before writing the first report in a project, check that `.gitignore` excludes `.canvas-cache/`,
and if it does not, **add the entry yourself and tell the user you did.** That is a must, not a
suggestion. Never upload, email, paste, or otherwise transmit a report or snapshot anywhere
without the user asking for that specific transmission.

The full rule, including what to do when a request would move student data somewhere new, is in
the plugin README under "Student data on disk". Read it once.

## Output

A single self-contained `<!doctype html>` document, inline `style="..."` throughout, charts as
hand-authored inline `<svg>`, no libraries and no build step. Alongside it, a `.json` snapshot with
the same basename so the pair is trivially found together and the next run can diff against it.

Open it when it is written: try `open <path>` (macOS), fall back to `xdg-open <path>` (Linux), and
if neither exists print the absolute path and say so.

Report back in conversation with the headline numbers and the flags, not just a file path. A
report nobody opens has not told anyone anything.

## Before handing it over

Everything drafted here goes out under the instructor's name, so it has to read as theirs and not
as machine output. This step is required, not advisory.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prose_check.py draft.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prose_check.py --text "the paragraph"
```

Fix everything labelled `FIX`. Fix `STRONG` findings too, unless there is a reason to keep one,
and then say the reason out loud rather than leaving it silent. `REVIEW` findings are judgment.

Then do the part no checker does: read it as the instructor would say it, cut anything they would
not, and stop at the last real sentence instead of summarizing. Generated text almost always ends
by reaching for a summary or for uplift, and deleting that ending is the highest-yield edit
available.

Read `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/ai-tells.md` before rewriting anything
to sound more human. Several famous "AI tells" are not tells at all, and stripping out hedges and
transitions produces prose that is worse and no less synthetic.

## References

- `references/grade-report.md`: the data pull, weighted and points-based computation, letter
  mapping, the audit checks, report structure, and the snapshot format.
- `references/activity-report.md`: window parsing, the five-call data pull, at-risk thresholds,
  the daily and planning-window todos, report structure, and the snapshot format.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/ai-tells.md`: the tells that
  make writing read as generated, what human writing looks like instead, and the
  famous "AI tells" that are not. Read before rewriting prose to sound more human.
