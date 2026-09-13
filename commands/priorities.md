---
description: What needs doing for a course in the next week, split into prepare and review.
argument-hint: [course] [horizon, default 7 days]
---

What needs attention for course **$1** over the next **${2:-7 days}**.

Check live state; do not answer from notes or from a tracker alone, both of which
go stale. Pull, at minimum:

- Every module's `unlock_at` and publish state, since an unpublished module with
  an unlock date opens nothing.
- Everything due or unlocking in the window, with its publish state.
- Anything already overdue that is still unanswered: ungraded submissions past
  their deadline, and the Canvas Inbox queue.
- If the course folder has a `TRACKING.md`, fold in its open items for this
  course, but verify anything it claims about Canvas state.

Answer in three short sections: **do first** (anything that breaks if it slips,
with the date it breaks on), **prepare** (things needed for a specific day next
week), and **review** (student work and signals worth reading, not just
grading).

Be specific about dates and name the artifact. Keep it brief; this is a list to
act on, not a report.
