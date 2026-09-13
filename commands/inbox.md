---
description: Show what is waiting in the Canvas Inbox for a course, without drafting or sending anything.
argument-hint: [course]
---

Show the Canvas Inbox queue for course **$1** (ask which course if that is empty).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course $1 inbox
```

Report it as a short list: how many threads need a reply, how many a TA already
answered, and how many are already answered by the instructor and could be
swept. For anything needing a reply, give a one-line gist of what is being
asked.

**Read only.** Do not draft replies and do not send anything. If the instructor
wants to work through them, that is `/triage`.
