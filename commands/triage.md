---
description: Triage the Canvas Inbox for a course, one message at a time, drafting each reply for approval before it sends.
argument-hint: [course]
---

Run a full message triage for course **$1** (ask which course if that is empty).

Use the `canvas` skill, `${CLAUDE_PLUGIN_ROOT}/skills/canvas/references/conversations.md`, which owns this process.
If the course folder has `course/procedures/TRIAGE_PROMPT.md`, read that too: it
carries anything course-specific, including the email half, which the Canvas
tooling does not touch.

Confirm the course first with `course_infra.py verify` and `canvas_api.py whoami`,
then build the queue:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course $1 inbox
```

Report how many threads there are and how they partition before drafting
anything. Then work **oldest first, strictly one at a time**:

1. **What was asked**, including questions buried in a second or third message.
2. **Check the claim against Canvas before drafting.** A student's account of
   their own situation is a symptom plus a guess at the cause, and the guess is
   often wrong. Verify the submission state, the score, the due date that
   actually applies to them.
3. **Analysis**, including anything that is a decision for the instructor rather
   than an answer. Surface it, do not make it.
4. **Draft the reply in full.** Do not send.
5. Iterate until the instructor approves.
6. Send and archive together, then move on:
   `canvas_api.py --course $1 reply <id> --file draft.md --archive --live`

For a thread a TA already answered, summarize their reply and say whether a
follow-up is needed rather than answering over the top of them.

At the end, `sweep --live` the threads already answered with no new reply,
confirm the inbox is empty by re-reading it, write up anything durable in the
course's student-notes file, and report **patterns** worth acting on: the same
question from three students is a defect in an assignment or the tooling, not a
coincidence.
