---
name: syllabus
description: >
  Create, review, edit, audit, and roll over a course syllabus, plus the artifacts that travel
  with one: a syllabus quiz and a course-overview deck. Use when the user mentions "syllabus",
  "course policies", "grading breakdown", "late policy", "AI use policy", "time commitment", or
  asks to "draft a syllabus", "review my syllabus", "update the grading breakdown", "add a section
  about", "check the syllabus against Canvas", "does the syllabus match what I'm actually doing",
  "roll the syllabus over to spring", "make a syllabus quiz", or "update the syllabus deck". Also
  use for a single piece: rewriting the late policy, checking a grading scheme, or fixing one
  paragraph. Do NOT use for assignment specs, which is the assignments skill, or for announcing a
  policy change to students, which is course-comms.
---

# Syllabus

A syllabus is the course's contract. It is the document students quote back, the one a grade
dispute is settled against, and the one that goes stale fastest. Most of the work here is not
writing it; it is keeping what it promises and what the course actually does from drifting apart.

## Step 0: Establish the course

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326
```

Load `.infra/course-profile.md`. It carries the term, the schedule, the policies already in
force, and the voice, so a draft can start from what is true rather than from questions already
answered. If the course does not exist yet, course-setup creates it; offer that, but do not block
a draft on it.

Read `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md` before writing any
prose. The profile's own `Voice` section overrides it.

## Where the syllabus lives

**The live LMS page is the source of truth.** Not a local file, not a docx, not last term's copy.
Everything downstream reads it: assignment descriptions quote its sections, the schedule table
determines module contents, the grading breakdown has to match the real rubrics.

That has two consequences worth internalizing:

- **Read it before you reason about it.** Fetch the live page rather than working from the course
  profile's summary or from a previous session's copy. Policies change mid-term, and a syllabus
  edited from a stale copy silently reverts whatever changed in between.
- **Edit surgically.** Prefer targeted replacement of the specific paragraph to regenerating the
  page. A regeneration is how syntax highlighting, embedded images, and last month's careful
  wording all disappear at once.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/pages/<slug> | python3 -c "import json,sys;print(json.load(sys.stdin)['body'])"
```

Read `references/canvas-workflow.md` before any write. It covers the drift check, the
verify-after-write step, publishing, and how a re-render loses things quietly.

If the course has no syllabus page yet, draft in markdown, show it, and only then create the
page. Nothing student-visible gets published without explicit approval.

## What a syllabus contains

`references/section-guide.md` has the full inventory with what belongs in each section and why.
The shape below is the default; adapt it to the course rather than forcing a course into it.

Lead with a **header block** of scannable facts: number, title, instructor, LMS URL, term, mode,
meetings, exams, group work, credits, prerequisites. A student looking for one fact should find
it without reading prose.

Then: description, staff and contact, learning objectives, **time commitment**, course structure,
required materials and technology, assignments with a weights table, policies, schedule, support
resources.

Three sections most templates get wrong and this instructor's courses depend on:

- **Time commitment.** Derive the hours from the institution's credit-hour rule and state them
  plainly, especially for a compressed term. A three-credit course is the same 135 hours whether
  it runs fifteen weeks or six; what changes is the weekly rate, and saying so honestly is what
  lets a student decide before the drop deadline rather than after.
- **The weights table.** Include a formative/summative marker per row, and allow a **0% row** for
  work that is required but ungraded. "Expected, not graded" is a real category and most tables
  cannot express it.
- **Assessment structure that is not lectures and exams.** Content units, sprints, labs, and
  projects can run on parallel tracks with a deliberate offset. The schedule table has to encode
  that offset, since "what is due this week" then spans two different weeks' material.

## Drafting

Ask for what the profile does not already answer: number, title, term, credits, enrollment,
prerequisites, mode, and what is genuinely different about this offering.

Then draft the whole thing and show it. Do not draft section by section asking for approval at
each; it is slower and it produces a document that reads as assembled rather than written.

**Every number must come from something real.** Weights come from the actual assignment plan.
Rubric point totals in the syllabus come from the live rubric objects, never invented alongside
them. Dates come from the academic calendar. When a number is not yet known, mark it
`[CHECK: ...]` rather than guessing, and list every marker at the end of the draft.

## Reviewing and auditing

Two different jobs, and the second is the one that finds real problems.

**Internal consistency** asks whether the document contradicts itself: weights summing to 100,
the late policy stated once and identically everywhere, every cross-referenced section existing,
dates matching the schedule table, no em-dashes.

**Audit against the live course** asks whether the document is still true: do the assignment
counts match, do the weights match the real gradebook groups, does the quiz length match, is the
LMS late-policy configuration what the text promises. This is where syllabi actually fail, and it
cannot be done by reading the syllabus alone.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 assignments --json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /courses/:course/late_policy
```

Read `references/audit.md` for both checklists and the exact comparisons. Report findings grouped
as **Structural**, **Policy completeness**, **Grading integrity**, **Drift from the live course**,
and **Clarity**, each with the quoted text, the concern, and a suggested fix. End with a verdict:
ready, needs minor fixes, or needs major revision.

**Lead with drift.** A syllabus that is merely inelegant costs nothing; a syllabus that promises
a two-day late cutoff while the LMS is configured with none costs a grade dispute.

## Rolling over to a new term

A new offering is a new page, not an edited one. The old one is the record of what students were
actually told, and grade disputes reach back.

Read `references/rollover.md`. The short version: everything dated changes, every platform id
changes, and the danger is not what gets missed but what gets silently carried forward. Anything
that cannot be verified for the new term gets flagged rather than copied.

## The syllabus quiz

A short quiz over the syllabus, worth few points, that makes students read the thing they will
otherwise quote incorrectly in week six. Target the sections that generate the most email: late
work, AI use, communication, submission mechanics, grading weights.

Write it as a JSON bank and hand it to the existing uploader, which creates a Classic Quiz and
its questions:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/upload_quiz.py syllabus-quiz.json --course 326 --live
```

Classic Quizzes only. Read `references/syllabus-quiz.md` for the bank schema, question design,
and why every answer must be checkable against a specific sentence in the syllabus.

## The companion deck

Many courses ship a short overview deck alongside the syllabus. It is a second copy of the same
facts, which means it drifts, and a deck that contradicts the syllabus is worse than no deck.

Generate or update it **from the syllabus**, never in parallel with it. Read
`references/overview-deck.md`, which covers the course's own deck pipeline when one exists, the
fallback, and the specific numbers that go stale first.

## Always

- Never invent a policy, date, or number. Mark the gap.
- Never publish or edit a student-visible page without showing the exact change and getting a yes.
- When a policy changes mid-term, say plainly that it is a change and from when. A policy that
  did not exist last week cannot be applied to last week's submissions, and the syllabus edit is
  only half the job; the other half is course-comms telling the class.
- Update the course profile's policy sections to match whatever the syllabus now says. Grading,
  assignments, and student-questions answer policy questions from the profile, and a profile that
  disagrees with the syllabus produces confident wrong answers to students.

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

- `references/section-guide.md`: every section, what belongs in it, and the ones that are easy
  to get wrong. Read when drafting or adding a section.
- `references/canvas-workflow.md`: fetching, editing, verifying, and publishing a live syllabus
  page without losing content. Read before any write.
- `references/audit.md`: the internal consistency checklist and the live-course drift audit.
- `references/rollover.md`: producing next term's syllabus from this term's.
- `references/syllabus-quiz.md`: the quiz bank schema and how to write questions worth asking.
- `references/overview-deck.md`: keeping the companion deck in sync with the syllabus.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md`: voice and formatting,
  shared with every drafting skill in this plugin.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/ai-tells.md`: the tells that
  make writing read as generated, what human writing looks like instead, and the
  famous "AI tells" that are not. Read before rewriting prose to sound more human.
