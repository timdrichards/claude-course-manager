# Consistency, drift, and regrades

Grading is a measurement, and the thing being measured is supposed to be the submission rather
than the order it happened to be in.

## Drift within a batch

Standards move as a batch progresses. Early submissions are graded against the rubric as written;
later ones are graded against the submissions already seen. Both directions happen: a grader who
sees several weak submissions starts giving credit for less, and one who sees several strong ones
starts expecting more.

Countermeasures that work:

- **Calibrate first.** Score three or four spanning the range, get corrections, and treat those
  corrections as amendments to the rubric text.
- **Re-check the first few at the end.** Rescore the earliest submissions after finishing and
  compare. Any change is drift, and it is cheap to fix before scores are posted and free to
  ignore only if nobody checks.
- **Grade item-by-item across submissions when the batch is large.** Scoring one rubric item for
  all forty submissions, then the next, holds the standard steadier than scoring all items for
  one submission at a time. It costs a second pass over the work and is worth it above roughly
  thirty submissions.
- **Never grade a batch in an order that correlates with anything.** Alphabetical is fine.
  Submission time is not: it sorts the procrastinators together, and the standard applied to that
  block will differ.

## Multiple graders

The two failure modes are different graders applying different standards, and different graders
applying the same standard to different work.

Before the batch: everyone grades the same three submissions independently, then compares. The
discussion that follows is the calibration, and its output is amendments to the rubric text.
Where two graders disagree, the item was ambiguous; fix the item rather than settling the
instance.

During: each rubric item wants the same owner across the whole batch where the split allows it.
Splitting by item rather than by student eliminates between-grader variance on that item
entirely.

After: compare score distributions per grader. A grader consistently a point and a half below the
others is not necessarily wrong, but the class should not be graded on who they drew. Adjust by
regrading a sample against the rubric, never by applying a flat correction, which just moves the
inconsistency somewhere less visible.

When asked to check grader consistency, report: mean and spread per grader, the rubric items with
the widest between-grader variance, and specific submission pairs that were scored differently
for the same observable feature. The last one is the most convincing and the most actionable.

## Fixing a rubric mid-batch

It will happen: submission 12 reveals the rubric is wrong. An item is ambiguous, a case was not
anticipated, an item double-counts.

Fix it, and then **regrade the first eleven against the fixed rubric.** A rubric change applied
only going forward means two standards in one batch, which is worse than either standard alone
and impossible to defend when a student compares notes with a friend.

If regrading the earlier ones is genuinely impractical, then the change only applies where it can
only help students, and the user needs to know that is the compromise being made. Say it
explicitly rather than letting it be a silent property of the batch.

Record what changed and why. That record is the answer to the regrade requests this will
generate, and it is what makes the rubric better next term instead of wrong again.

## Regrade requests

A regrade request is a claim that the grading was wrong. Evaluate the claim, not the student's
tone, and not how much they need the points.

The structure:

1. **Read the request and identify which rubric item is in dispute.** Requests are often written
   as "I lost too many points"; the useful version is "which item, and what does the submission
   actually do".
2. **Re-examine that item against the submission from scratch.** Do not start from the original
   score and look for reasons to keep it; that is where anchoring wins. Score the item as though
   for the first time.
3. **Compare to how the same item was scored for others.** This is the part that matters most and
   gets skipped. If this submission was scored differently from comparable ones, the request is
   valid regardless of what the rubric says in isolation, because consistency is the promise.
4. **Answer with the item and the evidence.** "Item 3 asks for the update to go through the
   reducer; line 34 mutates state directly" ends the conversation. "The grader used their
   judgment" starts a longer one.

Outcomes, all legitimate: the score changes; the score stands with an explanation; or the request
reveals a rubric flaw affecting everyone, which is no longer one student's regrade but a batch
correction.

**The third outcome is the one to watch for and the easiest to miss.** If this student's
complaint is right, and the rubric item that produced it applied to the whole class, then fixing
it for the one student who asked is the worst available outcome: it rewards complaining and
leaves the error in place for everyone who did not. Flag it as a class-wide issue and let the
instructor decide.

Never adjust a score to end a conversation. A grade changed under pressure rather than on the
merits is unfair to every student who accepted theirs, and it teaches the wrong lesson about how
grades work.

## Distress, accommodations, and pressure

Some regrade requests are not about the rubric. A student in distress, a request that mentions a
personal situation, an accommodations question, a message that reads as desperate. Route these
to the instructor immediately and warmly, and do not attempt to resolve them as a grading matter.

Pressure tactics ("I'll lose my scholarship", "my TA said this was fine", "everyone did it this
way") get the same treatment as the underlying claim: evaluate the claim on the evidence, answer
warmly, and do not let the pressure move the number. If a TA did say it was fine, that is worth
knowing and worth checking, and it is a question for the instructor rather than a reason to
regrade on the spot.
