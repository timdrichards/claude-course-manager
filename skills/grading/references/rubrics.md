# Rubrics

A rubric is not a description of the assignment. It is the thing that makes two graders, or the
same grader on a Tuesday and a Friday, arrive at the same number. Most rubrics that feel
inadequate during grading were written as descriptions.

## The test a rubric has to pass

Take any item and ask: **could two people who both read the submission carefully disagree about
whether it is satisfied?** If yes, the item is not done. Rewrite until the disagreement is about
facts in the submission rather than about what the item means.

"Code is well organized" fails this test badly. "Each function does one thing, and no function
exceeds roughly 30 lines" is arguable but bounded. "Cart state updates go through the reducer
rather than mutating state directly" is checkable.

The instinct to keep items vague usually comes from wanting room for judgment. That room is real,
but it belongs in a separate holistic item worth a small number of points, not smeared across
every item.

## Structure

Aim for four to eight items on a normal assignment. Fewer, and each item carries too much to
award partially with any consistency. More, and grading becomes a checklist exercise that takes
longer than it is worth and produces feedback nobody reads.

Each item needs:

- **A name** that says what is being measured, in the course's own vocabulary.
- **Point value.** Points should follow what the assignment is actually teaching. If the
  assignment exists to teach state management and 60% of the points are for input validation,
  the rubric is measuring the wrong thing, and students will optimize for what it measures.
- **Levels.** Either full/partial/none with the partial condition stated, or explicit bands. Do
  not leave partial credit undefined and decide in the moment; that is where drift lives.
- **What evidence looks like.** One line: which file, which function, which test, which output.

## Point distribution

Two failures, both common.

**Everything weighted equally.** A rubric where correctness and code style are both worth 20
points tells students those matter equally. If that is not true, the rubric is lying and the
grades will reflect the lie.

**All-or-nothing on large items.** A 30-point item with no partial credit means a submission that
is 90% right and one that is empty score the same. That is a cliff rather than a standard, and it
generates most regrade requests. Any item worth more than roughly 15% of the total needs defined
partial credit.

Reserve a small band, 5 to 10%, for something holistic if the user wants room for judgment. Name
it honestly: "overall quality" is fine as one small item and terrible as a hidden multiplier on
everything else.

## Rubric styles and how each fails

**Checklist** (present/absent per requirement). Fast, consistent, and defensible. Fails on
anything where quality matters more than presence: a submission can check every box and be bad.
Right for early assignments and for specs with hard requirements.

**Levels / bands** (exemplary, proficient, developing, missing). Handles quality. Fails when the
band descriptions are adjectives rather than observable conditions, which is most of the time.
Only use bands whose descriptions could be read aloud to a student who would then agree which
band they are in.

**Points-off from a perfect score.** Matches how many graders actually think, and it is honest
about that. Fails when the deduction list is not written down in advance, at which point the
deductions accumulate differently for the first and fortieth submission. Write the deduction
schedule before grading, and treat it as the rubric.

**Autograder plus manual.** The autograder handles correctness, a human handles design. Fails
when the split is not explained to students, who then cannot tell why they lost points. Also
fails when the autograder's partial credit does not match the rubric's, which is worth checking
before a batch rather than after.

## Calibration

A rubric is a hypothesis until it has met real submissions.

Before grading a batch, apply the rubric to three or four submissions chosen to span the range:
one that looks strong, one weak, one confusing. Show the item-by-item results to the user and ask
where they disagree.

Their disagreements are the actual rubric. Write them down as amendments to the item text, not as
remembered adjustments. What was learned in calibration is exactly what will be forgotten by
submission 20.

Calibration also surfaces rubric bugs while they are still cheap: items that no submission
triggers, items every submission fails the same way, and items that turn out to overlap so that
one flaw costs points twice. Read on.

## Double jeopardy

The most common real defect in a working rubric: one mistake losing points under two items. A
submission with a broken reducer loses points for "correct state updates" and again for "app
works end to end", because the broken reducer is why the app does not work.

Decide in advance which item owns a given failure, and say so in the item text. The rule of thumb
is that the item measuring the specific skill owns it, and the integration item is only about
failures that are not attributable to a specific item.

Left unfixed, this makes the bottom of the distribution much harsher than intended, and it is
invisible until a student compares two graded submissions.

## Rubrics students can see

If the rubric goes out with the assignment, and it usually should, then students will optimize
for it. That is not gaming; that is the rubric doing its job. It does mean anything left out is
effectively declared unimportant.

It also means the rubric has to be written in language students already have. An item referring
to a concept from three weeks out is not a standard, it is a trap.

Publishing the rubric is also the strongest defense against regrade requests, because it converts
"why did I lose points" into "which item, and what did the submission do", which is answerable.
