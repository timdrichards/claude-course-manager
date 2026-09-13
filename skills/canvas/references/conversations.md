# Conversations (the Canvas Inbox)

Every command below is `canvas_api.py`, the curated client. Confirm the course
with `verify` and `whoami` first, the same as any other Canvas work.

Canvas Conversations is the messaging system behind the Inbox. It is separate
from announcements and from discussions: a conversation is private to its
participants, and there is **no real unsend**.

`canvas_api.py` wraps the tedious parts: building the triage queue, working out
who spoke last, and verifying a send actually landed. Use it rather than
hand-rolling these calls. Writes go through the same two-switch gate and audit
trail as every other write in this skill, so a reply is a dry run until `--live`
and is reversible from the log afterwards.

## Why "who spoke last" is the whole game

A thread needs action if and only if **someone other than you sent the last
message**. Unread status does not tell you this: a thread can be read and still
unanswered, or unread and already handled by a TA. Every triage pass starts by
partitioning the inbox on the last message's author.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course <course> inbox            # triage queue, oldest first
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course <course> inbox --scope unread
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course <course> thread <conversation_id>
```

`inbox` marks each thread `NEEDS REPLY` (a student spoke last), `STAFF REPLIED`
(a TA or co-teacher spoke last, so summarize rather than re-answer), or
`ANSWERED` (you spoke last, nothing new).

## Reading

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course <course> inbox --json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course <course> thread <id> --json
```

- **Always filter by course** (`filter[]=course_<id>`) when the token owns more
  than one course, or you will triage someone else's students.
- The list endpoint returns only a preview. Message bodies need the per-thread
  `GET /conversations/<id>`, which returns `messages` newest-first; sort by
  `created_at` before reading.
- Bodies are HTML. Strip tags and unescape entities before quoting one back.

## Replying

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course <course> reply <id> --file draft.txt --archive --live
```

Raw equivalent: `POST /conversations/<id>/add_message` with a `body`.

- **`add_message` is not idempotent.** A repeated call posts the message twice.
  Never retry a send that looked like it failed; re-fetch the thread and count
  the messages instead. `reply` does this for you, and refuses with a nonzero exit if the count did not move by exactly one.
- Bodies are plain text in practice. Markdown is not rendered, so `**bold**`
  reaches the student as literal asterisks. Use blank lines and indentation.
- Long code or command sequences survive fine as indented plain text.

## Starting a new conversation

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course <course> \
  post /conversations --live --json '{
  "recipients": ["12345"],
  "subject": "Your Sprint 1 feedback",
  "body": "...",
  "context_code": "course_123",
  "force_new": true
}'
```

- `recipients` must be a **real JSON array of id strings**, not a `recipients[]`
  form key.
- **`force_new: true` unless you specifically want to continue an existing
  thread.** Without it Canvas may append your message onto an unrelated
  pre-existing conversation with that person, which is how a routine note lands
  in the middle of someone's private accommodation thread.
- **Multiple recipients need `group_conversation: true`**, or Canvas silently
  splits the send into one private conversation per recipient, each of which can
  match into an unrelated existing thread. This has happened in the wild and
  produced duplicate messages in students' private threads.
- There is **no unsend**. `DELETE` on a conversation or message removes it from
  *your* copy only; the recipient keeps theirs. The only real remedy for a
  mistaken send is a follow-up message in the same thread.

## Archiving

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course <course> archive <id> --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course <course> archive <id> --undo --live     # back to the inbox
```

Archiving is reversible (`"read"` puts it back) and affects only your view.
A new reply pulls the thread back into the inbox, so archiving a handled thread
is safe and is what keeps the queue meaningful.

## The triage workflow

This is an **interactive, one-at-a-time** loop. It exists because batching
drafts produces generic replies, and because each message usually needs a fact
checked in Canvas before the answer is worth sending.

**Before the loop:** run `inbox`, then say how many threads there are
and how they partition. Do not start drafting yet.

**Per thread, in oldest-first order:**

1. **What was asked.** Summarize every question in the thread, including ones
   buried in a second or third message. Students routinely append an unrelated
   question after the one in the subject line.
2. **Check the claim against Canvas.** This is the step that earns the whole
   process. A student's account of their own situation is a report of a symptom
   plus a guess at the cause, and the guess is often wrong. Before drafting,
   verify the thing they are describing: the submission state, the score, the
   due date that actually applies to them, whether the file is really missing.
   Real examples this has caught: a student certain he had submitted had not
   (he had submitted a different item), and a student's self-diagnosis of *why*
   his grade was missing was wrong even though the grade really was missing.
3. **Analysis.** What is actually going on, what the student has right and
   wrong, and anything that needs an instructor decision rather than an answer
   (a waiver, an exception, a policy call). **Surface the decision, do not make
   it.**
4. **Draft the reply.** Show the full text. Do not send.
5. **Iterate** until the user approves.
6. **Send, then archive**, in that order, verifying the send.
7. Move to the next thread.

**For a thread a TA or co-teacher already answered:** summarize their reply and
say whether a follow-up is needed, rather than answering again over the top of
them. Re-answering undermines the staff member and confuses the student.

**At the end:** archive every remaining thread that you have already answered
and that has no new reply (`sweep --live`). Then report the inbox is empty,
verified by re-reading it rather than by counting what you did.

## Patterns worth reporting, not just answering

A triage pass is the highest-signal read on a course you will get. Watch for:

- **The same question from three different students.** That is a defect in the
  assignment text, the tooling, or the course design, not three coincidences.
  Say so, and propose the fix to the artifact rather than answering it a fourth
  time.
- **A student catching a real error.** Verify it immediately and fix the
  artifact, not just the thread. One student writing in usually means several
  noticed and said nothing.
- **Disproportionate time cost.** "I spent four hours on this" from a competent
  student is a report about your setup instructions.
- **Threads addressed to all staff that no staff answered.** Worth knowing
  separately from the content.

## Recording what happened

When a thread produces a decision that outlives it (a waived penalty, an
accommodation, a student's circumstances, a promised follow-up), write it to the
course's student-notes file with a real timestamp from `date`, not from memory.
Triage is where most of that context is generated, and it is worthless if it
only exists in an archived thread nobody rereads. Treat that file as PII under
Safety Rule 7.
