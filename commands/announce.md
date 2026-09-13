---
description: Draft a Canvas announcement for a course, show it for approval, then post or schedule it.
argument-hint: [course] [what it is about]
---

Draft a Canvas announcement for course **$1** about: **$2**

Use the `course-comms` skill for the writing and the `canvas` skill for posting.
Read the course's own `CLAUDE.md` for house style before drafting; a course that
has one usually has rules an announcement must follow.

Ground every claim in live Canvas state rather than memory. If the draft asserts
a date, a deadline, or that something is open, **check it** first, and pull the
most recent announcement as a style reference so this one does not drift from
the voice students already know.

**Show the full text and wait for approval.** An announcement notifies everyone
the moment it posts and cannot be unpublished, only deleted.

On approval, post or schedule it:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course $1 \
    announce --title "..." --file body.md --at <ISO8601> --live
```

Then verify from a fresh read, not the response: the schedule time, that the
body survived intact, and that no markup was stripped. If the announcement was
already posted and needs an edit afterwards, say so visibly in the text rather
than changing it silently under readers who have seen it.
