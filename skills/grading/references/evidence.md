# Evidence

Every point awarded or withheld points at something in the submission. This is what separates
grading from impression, and it is what makes a regrade request a two-minute conversation instead
of an argument.

## What counts

Evidence is something a third person could locate in the submission and verify.

**Counts**: a quoted line with its number; a function or variable name; a specific test that
fails and its output; a missing file; a commit that shows the work was done after the deadline;
an actual measured behavior ("clicking add twice adds one item").

**Does not count**: "the implementation is incomplete"; "shows a misunderstanding of state";
"could be cleaner"; "does not fully meet the requirement". These are conclusions. They may be
correct, but as written they cannot be checked, and a student cannot act on them.

The test: rewrite the justification as a sentence a student could disagree with by pointing at
their own code. If there is nothing to point at, keep looking or flag the item.

## When the evidence is not there

Sometimes an item cannot be evaluated: the relevant file is missing, the code does not run, the
submission is a screenshot, the work is in a place nobody looked.

Do not score it as zero by default, and do not score it as full by charity. Flag it and say what
is missing. "No `cart.js` in the submission; if it was submitted elsewhere this item is
unscored" is useful. A silent zero on a student who submitted correctly to the wrong place is the
kind of error that surfaces three weeks later as a distressed email.

## Partial credit

Partial credit is where consistency dies, because the amount is decided in the moment forty
separate times.

Decide the partial levels **before** the batch and write them into the item. For a 6-point item,
"6 if all three cases handled, 4 if two, 2 if one, 0 if none" is applicable by anyone. "Partial
credit for a partial implementation" is not.

Two rules that prevent most drift:

- **Partial credit follows what was demonstrated, not effort.** A submission with 200 lines of
  wrong code and one with 20 lines of wrong code have demonstrated the same thing. Effort is
  worth acknowledging in feedback; it is not worth points unless the rubric says so, and if it
  is, say so in the rubric.
- **A near-miss on the concept beats a mechanically complete miss.** A student who structured the
  solution correctly and had an off-by-one is closer to the learning goal than one who produced
  the right output by special-casing every input. When the rubric measures understanding, score
  understanding.

## Correct, but not the way the rubric expected

This happens on every interesting assignment, and it is the case most worth getting right.

A submission solves the problem with an approach the rubric did not anticipate. The rubric's
items do not map onto it. The temptation is to deduct for the mismatch.

Do not resolve this silently. Flag it, describe what they did, and say whether it meets the
learning goal the item exists to measure. Three outcomes are common, and the user picks:

- **It meets the goal by another route.** Full credit, and the rubric gets an amendment for next
  time.
- **It sidesteps the goal.** A student who avoided the data structure the assignment was about by
  using a library that trivializes it has not demonstrated the skill, even if the output is
  right. That is a real deduction, and the feedback should explain the goal rather than assert
  the rule.
- **It violates an explicit constraint.** The spec forbade it. Deduct as specified, and check
  whether the constraint was stated clearly enough, because if several students hit this the spec
  is the problem.

Never deduct merely because an approach is unfamiliar. "Not how we did it in lecture" is not a
defect unless the assignment said so.

## Grading code specifically

**Run it if it can be run.** Reading code and predicting its behavior is much less reliable than
executing it, and the difference shows up exactly on the submissions where the score matters. A
grade based on reading should say so.

**Distinguish "does not compile" from "does not work".** They are different failures and often
different rubric items. A submission that fails to build may be one typo away; find out before
scoring, because a syntax error costing 40 points is rarely what anyone intended.

**Check whether the tests were run.** If the assignment shipped tests and the submission fails
them all, the likely story is that they never ran them, and that is worth saying in feedback:
it is the transferable lesson, and it is more useful than the deduction.

**Style is only gradeable if it was taught and specified.** Deducting for formatting the course
never discussed is arbitrary. If the course has a linter or a style guide, cite the specific
rule.

**Read for the concept before reading for defects.** Establish what they were trying to do, then
evaluate whether it works. Reversing this order produces feedback that catalogs symptoms and
misses that the student had one wrong idea generating all of them. Naming that idea is the single
most useful thing feedback can do.

## Grading writing and design work

The same rule applies, adapted: quote the sentence, name the section, point at the specific claim
that lacks support. "The argument is underdeveloped" is a conclusion; "section 3 asserts that
caching solves this without addressing the invalidation problem raised in section 2" is evidence.

For design work, evidence is the specific decision and its stated or implied justification, not
the aesthetic outcome.

## Recording evidence

Keep it short enough to be read. A rubric-item justification is one sentence with a locator, not
a paragraph. The instructor is scanning forty of these to check the grading, and a wall of prose
per item means the check does not happen.

The evidence a student sees and the evidence the instructor sees are usually the same thing, and
should be. The exception is anything the instructor needs and the student should not see:
comparisons to other submissions, honesty concerns, and uncertainty about the grading itself.
Those go in the note.
