---
description: Audit a week's Canvas module before it opens to students.
argument-hint: [course] [week]
---

Audit **week $2** of course **$1** before it releases.

The failure this exists to prevent: a module with `unlock_at` set but
`published: false`. **`unlock_at` gates a published module; it does not publish
anything.** Nothing appears, and nobody finds out until students ask.

Check, against live Canvas rather than notes:

1. **The module is published, and every item inside it is too.** Read each
   object's own endpoint, not the module item list's cached `published` field.
2. `unlock_at` is what the syllabus says, in the right timezone.
3. Every assignment, quiz, and discussion has the due date the syllabus claims,
   read with `override_assignment_dates=false` for the true base date, and with
   per-student `cached_due_date` where overrides exist.
4. Each item is in the correct assignment group, so the weighting is right.
5. Quizzes have a real question pool and non-null `points_possible`; a
   `graded_survey` needs it set explicitly or it is silently worth zero.
6. Links in the week's pages resolve, including in-page anchors.
7. Prose matches metadata: dates and week numbers written in assignment text
   drift from the real `due_at` after any repacing.

Report what is wrong and what it would take to fix, **fix nothing without
asking**, and say plainly if everything checks out.
