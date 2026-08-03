---
name: grading
description: >
  Design rubrics, draft student feedback, score submissions against a rubric with evidence, check
  grader consistency, handle regrade requests, and push approved scores to Canvas. Use when the
  user says "grade these", "help me grade", "write a rubric", "draft feedback for this
  submission", "score this against the rubric", "is my rubric consistent", "check these grades",
  "handle this regrade request", "why did this get marked down", "push these scores to Canvas",
  or hands over submissions, a rubric, or a Gradescope export. Ask what depth of involvement is
  wanted before starting. Do NOT use for writing the assignment itself, which is the assignments
  skill, or for answering student questions about an assignment, which is student-questions.
---

# Grading

Grading is the one thing here that touches individual students' records. A hint that misses costs
a student an afternoon; a score that misses costs them a grade and costs the instructor their
credibility when it is found. So the work is slower and more explicit than the rest of this
plugin, and every score carries the evidence it came from.

## Step 0: Ask how far to go

Do not assume. Involvement in grading ranges from helping shape a rubric to putting numbers in
the gradebook, and the right level is a decision the user makes per batch, not a default.

Use `AskUserQuestion` at the start of any grading task, offering:

1. **Rubric work**: draft or revise a rubric, calibrate it against a few real submissions, check
   it for gaps and overlaps. No student is scored.
2. **Feedback only**: draft comments per submission against the rubric. No scores proposed.
3. **Score with evidence, you approve**: propose a rubric-item-level score for each submission
   with the specific evidence behind each item. Nothing leaves this conversation.
4. **Score and upload**: the above, then push approved scores and comments to Canvas.

Skip the question only when the user has already been explicit ("just draft feedback, no
scores"), or when a mode was chosen earlier in the same session and the work is continuous. If
they pick 4, confirm the destination assignment by id before any scoring begins, so nothing is
scored against the wrong column.

Then establish the course and load the profile and rubric:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326
```

Say the course, the assignment, and the mode back in one line before starting.

## What has to be true before scoring anything

Refuse to score, warmly and specifically, when any of these is missing:

- **A rubric.** Not "the assignment spec": an actual rubric with items and point values. Without
  one there is no defensible basis for a number, only an opinion with a decimal point. Offer to
  build one; that is mode 1 and it is often the real task.
- **Points possible**, and how they distribute across rubric items.
- **The submission itself**, in full. Scoring from an excerpt is guessing.

State what is missing and stop. Do not score around a gap.

## Scoring, and what a score has to carry

Score **per rubric item**, never as a single holistic number that gets decomposed afterward. The
total is the sum; it is not the starting point. A holistic number rationalized into items is how
a grader's first impression becomes the grade.

Every rubric item gets three things:

- **The award**: full, partial with the amount, or none.
- **The evidence**: a specific quote, line number, function name, test case, or output from the
  submission. Not "the implementation is incomplete" but "`updateCart` handles the add case at
  line 34 and returns undefined for remove". An item whose evidence cannot be located in the
  submission does not get scored; it gets flagged.
- **The tie to the rubric's own language**: which clause of the item this satisfies or fails.

Read `references/evidence.md` for what counts as evidence, how to handle partial credit
consistently, and what to do about work that is right but not in the way the rubric anticipated.

**Flag rather than score** whenever: the submission does something the rubric does not
anticipate and might deserve credit; the code is correct but takes a forbidden approach; the work
looks substantially similar to another submission; the file is corrupt, empty, or the wrong
thing; or the rubric item is genuinely ambiguous as applied here. Each of these needs a person,
and each is more valuable surfaced than resolved silently.

**Never let a suspected academic honesty issue become a score.** Do not deduct for it, do not
mention it in student-facing feedback, do not name the other student. Say it in the note to the
instructor and stop there. That process belongs to the institution and a wrong accusation is
serious.

## Feedback

Feedback goes to the student; the note goes to the instructor. Keep them separate and never blur
them.

Student-facing feedback:

- Lead with what worked, specifically. On a submission that scored badly this is more important,
  not less, because a wall of deductions teaches nothing.
- For each deduction, say what was expected, what the submission did, and what it would take to
  be right. A student who cannot tell from the feedback what to do differently has been graded
  but not taught.
- Do not include solution code. The assignment may be regraded, resubmitted, or reused next term,
  and a corrected version of their code in a comment is a solution in circulation. Describe the
  fix; do not write it.
- Match the course profile's voice. Feedback that reads like a different person than the lectures
  is unsettling in a way students notice.
- Three to six sentences for a normal submission. Longer only when the work earned it.

## Output format

Per submission, in this order:

```
### <student name or id>: <score>/<total>

| Rubric item | Points | Evidence |
|---|---|---|
| <item> | 4/5 | <specific quote, line, or test> |

**Feedback (student-facing):**
<the comment, ready to post, nothing else in this block>

**Note for you:** <anything needing judgment: flags, ambiguity, close calls, patterns>
```

Only include the sections the chosen mode calls for. Then, across the batch, report: the score
distribution, the rubric items where partial credit was most common, anything several students
got wrong the same way, and every flagged submission listed first.

**Several students failing the same rubric item the same way is a finding about teaching, not
about those students.** Say so. It usually means a lecture gap, an ambiguous spec, or a rubric
item that does not measure what it intends. That is worth more to the user than the grades.

## Consistency

Grading drifts. It drifts across a batch as standards loosen or tighten, and it drifts between
graders.

Before a large batch, calibrate: score three or four submissions spanning the range, show them,
and get the user's corrections. Their corrections are the real rubric. Apply them to the rest and
say what changed.

Re-check the earliest submissions after finishing a batch. Standards set on submission 1 are not
the standards in force by submission 40, and the fix is cheap if it happens before scores are
posted.

For multi-grader consistency and regrade requests, read `references/consistency.md`.

## Uploading to Canvas

Only in mode 4, only after the user has read the scores, and only with the two-switch gate the
Canvas skill describes. Approval here is per batch and it is narrower than it sounds: "these look
right" after reading a summary is not approval to write forty grades. Show the roster-matched
`was -> will be` list and get an explicit yes on that.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 set-grades <assignment_id> \
    --file grades.json --live
```

Matching students to Canvas user ids goes through SIS id or email, never name. Names collide and
are formatted differently in every system, and a name-matched grade batch will eventually put a
score on the wrong person. Any student who cannot be matched is reported and left ungraded rather
than guessed at.

The command prints `was -> will be` per student and counts how many already have a score. An
unexpected overwrite count means a batch is being applied twice or the wrong assignment id was
used; stop and check rather than proceeding.

Canvas applies bulk grades in the background, so the command returning is not proof they landed.
Confirm with `submissions` afterward and report the real state.

**Gradescope is read-only in this plugin.** Its scores can be read for reference, but there is no
confirmed way to write one back and nothing here pretends otherwise. Grades go to Canvas.

## Never, regardless of mode

- Scoring without a rubric.
- A score whose evidence is not in the submission.
- Uploading without the user reading the specific numbers being uploaded.
- Grading during a scheduled or unattended run. A schedule fires with nobody watching, so the
  approval cannot have happened. Scheduled runs prepare and stop.
- Solution code in student-facing feedback.
- Any mention of a suspected honesty issue in anything the student reads.

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

- `references/rubrics.md`: writing a rubric that can actually be applied, point distribution,
  the failure modes of common rubric styles, and calibration.
- `references/evidence.md`: what counts as evidence for each kind of work, partial credit,
  correct-but-unanticipated solutions, and grading code specifically.
- `references/consistency.md`: drift within a batch, multiple graders, regrade requests, and
  fixing a rubric mid-batch without invalidating what is already scored.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md`: voice and
  formatting, shared with every drafting skill in this plugin. The course profile's
  `Voice` section overrides it.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/ai-tells.md`: the tells that
  make writing read as generated, what human writing looks like instead, and the
  famous "AI tells" that are not. Read before rewriting prose to sound more human.
