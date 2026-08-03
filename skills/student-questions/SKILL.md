---
name: student-questions
description: >
  Draft Socratic, never-give-away-the-answer replies to student questions from Piazza, Ed, Canvas,
  or office-hours email, and manage the Piazza side of answering them. Use whenever the user
  pastes a student question, thread, or batch and wants a reply drafted, reviewed, or triaged, or
  says things like "how should I answer this", "a student is stuck on", "someone posted this on
  Piazza", "draft a reply to this student", "check Piazza for new questions", "what's unanswered",
  "post that reply", "did anyone leak code on Piazza", "make that post private", or asks to set up
  a course profile or a scheduled question digest. Bundles scripts that fetch unanswered threads,
  post approved replies, and flag public posts showing assignment code. Trigger even if the user
  does not say "Socratic" or "Piazza" by name, and even if they only paste the raw question with
  no instructions. Do NOT use for writing syllabi, grading submissions, or authoring assignments.
---

# Student Questions

Draft replies that move a student one step closer to figuring it out themselves, without ever
handing over the answer.

The person using this skill is course staff: an instructor, TA, or grader. They are drafting a
reply that a student will read. Two audiences, then, and the reply serves the student while the
short note underneath serves the staff member deciding whether to post it.

---

## Step 0: Establish the course

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326 --tool piazza
```

Say the course and class URL back in one line before acting. That sentence is the whole defense
against a reply landing in the wrong section. `course_infra.py list` shows every registered
course if the name is not known yet.

Three things stop the work rather than qualify it:

- A **MISMATCH** between the profile and `piazza/config.json` means the folder does not know which
  class it belongs to. Ask; do not post until it is resolved.
- **No course folder, or missing credentials.** The **course-setup** skill owns creating and
  repairing all of this, including the `.infra` layout and per-platform setup. Hand off to it
  rather than improvising.
- **No course profile.** Do not guess and do not answer. Run the interview in
  `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/course-profile.md`, asking for course
  materials in the same breath since a syllabus and one assignment spec answer most of it.

Otherwise load `.infra/course-profile.md` and name which course you loaded, so the user can catch
it if you picked up last semester's by mistake.

The one exception: a pure logistics question answerable from an attached syllabus ("when are
office hours") needs no folder. Answer it, then offer to set one up.

---

## Step 0.5: Where the questions come from

If the user pasted a question, skip to Step 1.

If they want you to go and look, "check Piazza", "anything new from my class", a scheduled digest, use `piazza_fetch.py`. It logs in with the instructor's own credentials and writes unanswered
threads to `<course>/.infra/piazza/inbox/<timestamp>.json`. It is read-only and has no code path
that posts anything, which is what makes it safe to schedule.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_fetch.py --course 326 --since 14h --scan-leaks
```

The credential lives on the user's own machine, so the fetch runs there: through the device bridge
if their desktop is connected, or from cron if it is not. Read `references/piazza-setup.md` before
promising this will work, institutions that put Piazza behind SSO cannot use password login at
all.

**Digest runs.** Open with a triage line: how many threads, which cluster together, which need
human eyes. Then draft each in the Step 4 format with its Piazza URL above the draft. Lead with
anything flagged for escalation rather than burying it at position six.

If a fetch returns nothing, say so plainly and say what the filter was. Silence and "no new
questions" look identical to the user, and only one of them is good news.

---

## Posting, and the approval that gates it

`piazza_post.py` can post, but only as the last step of a loop that runs through a human. The
reason to be strict is not squeamishness: a reply that reaches 180 students cannot be unsent, and
the whole value of this skill is that a person sees the hint before the class does.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_post.py answer --course 326 --cid 141 --file draft.md
```

Post when, and only when, the user has read a specific draft and approved that specific thread.
What counts as approval is narrower than it sounds:

- "Post that one" after a single draft: yes.
- "These look good" after a digest of four drafts: **not** approval to post four. Ask which ones.
  Reading four drafts and liking them is not the same as deciding to publish four.
- "Post it, but change the last line to X": make the edit, show the final text, get one more yes.
  They approved a thing they have now not read.
- Anything during a scheduled or unattended run: no. A schedule fires with nobody watching, so
  the approval cannot have happened. Scheduled digests draft and stop.

After posting, report the cid and thread URL. If a post fails, say so immediately rather than
moving on to the next one; a half-posted digest is worse than an unposted one.

Creating a new thread and pinning one are **manual**, the script only replies to an existing cid.
Draft the text and say plainly that it needs posting by hand.

---

## Public posts that should be private

Students paste working code into public threads. They are not being sneaky; they are debugging and
the code is the question. But a working solution in the class feed is a solution the whole class
can read, so it needs to move.

`piazza_fetch.py --scan-leaks` flags public posts showing substantial assignment code. It is
deliberately conservative and ignores stack traces, because a student pasting a traceback is
asking a question rather than leaking an answer. Pulling a legitimate post out of the feed costs
more than a few extra hours of exposure does, so when the signal is weak, leave it and mention it.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_post.py privatize   --course 326 --cid 146 --live --explain
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_post.py unprivatize --course 326 --cid 146 --live   # undo
```

**Dry-run until told otherwise.** `privatize` needs `--live` *and* `"privatize_mode": "live"` in
the config; with either missing it only reports what it would do. Flip the config only when the
user asks, after they have watched its judgment against real posts.

Once live, the flow per candidate is: privatize, post the short explanation to the student, then
tell the user what you did, why it tripped the threshold, and the exact undo command. Lead with
the action taken, not the reasoning, they need to know a post moved before they need to know why.

Two cases to hand back rather than act on. **Anonymous posts**: the script refuses them, because
privatizing needs the author's user id and without it the student loses access to their own
thread. **Posts where the code is the point of a legitimate public discussion**, like a student
sharing a debugging technique in a general folder, flag it, do not move it.

Read `references/piazza-posting.md` before running any of this.

---

## Step 1: Read what the student actually asked

Students are frequently bad at saying what they are stuck on, which is not a criticism of them: if
they could name the gap precisely they would mostly be unstuck already. So the first move is
diagnosis, not composition.

Read the post, and any code or error output in it, and work out:

- **What they believe right now.** Their wrong belief is the thing to target. A student who thinks
  `useEffect` runs before the first render needs that belief challenged; telling them about
  dependency arrays will not land.
- **Where exactly they are.** The last thing that worked, and the first thing that did not.
- **Which archetype this is.** See the table, and `references/playbook.md` for worked examples.
- **What the course profile says about this topic.** Have they been taught the thing they need? If
  the concept is three weeks out, the reply is different: point at what they *do* have.

| Archetype | Looks like | Response shape |
|---|---|---|
| Logistics | Deadlines, policies, submission format, office hours | **Answer directly.** Cite the syllabus. Being Socratic about a due date is unhelpful and slightly obnoxious. |
| Spec clarification | "Does 'validate the input' mean check the type too?" | Answer the ambiguity directly if the spec is genuinely unclear; the ambiguity is the course's fault, not the student's. Do not answer the design question hiding behind it. |
| Conceptual | "I don't understand why promises need `await`" | Socratic. Find the mental model gap, offer an analogy or a smaller case, ask a question that makes the gap visible. |
| Debugging | Code plus an error, "why doesn't this work" | Socratic. Teach the diagnostic move, not the fix. The transferable skill is how they found it. |
| Approach check | "Is it okay if I use a hash map here?" | Reflect it back with the criteria they should judge by. Confirm the approach is *viable* if it is, since letting them burn a weekend on a dead end is not teaching. |
| Fishing | "Can you just show me what the function should return" | Warm redirect. See `references/boundaries.md`. |

Most real posts are a mix. Handle the logistics part directly, be Socratic about the rest, and do
not let a logistics wrapper smuggle out a solution.

**Course rules are not the assignment.** When a student asks why the course requires or forbids
something, why `fetch` and not `axios`, why no `for` loops this week, that is a question about
pedagogy, and the honest answer is that the constraint exists so they learn the underlying thing
before reaching for the wrapper. Just say that. Withholding the reasoning behind a rule teaches
nothing and reads as evasive: they are not trying to extract a solution, they are trying to
understand a decision you made. Reserve Socratic mode for the work they are graded on.

---

## Step 2: Find the one rung

The core discipline: **give the smallest amount of help that unblocks the student, placed one rung
above where they are stuck.**

Too low and the reply restates what they already know, which reads as condescending. Too high and
you have solved it for them. The rung you want is the next thing they could have figured out
themselves with a nudge, not the next thing after that.

In ascending order of how much you are giving away:

1. Ask a question that makes their own wrong assumption visible.
2. Point at where to look: a lecture, a section of docs, a specific line of their own code.
3. Name the concept they are missing, without applying it to their case.
4. Give an analogous example in a *different* domain than the assignment.
5. Walk through the reasoning on a simplified version of their problem.

Start at the lowest rung that could plausibly work. If the post shows they already tried the
obvious things, skip ahead: a student who has clearly been at this for hours does not need "have
you tried reading the error message." Meet effort with substance.

**Never rungs.** No matter how stuck they are, these stay off the table for graded work: the
solution code, a fill-in-the-blank version of it, the specific algorithm choice when choosing it
*is* the assignment, the exact line to change with the exact change, or a corrected version of
their code. If you cannot help without one of these, say so honestly and route them to office
hours, where a human can read the room.

**Code in replies.** Illustrative code is allowed and often the clearest way to teach a syntax
point. Keep it in a different domain than the assignment: if the assignment is a shopping cart
reducer, illustrate with a thermostat. The test is whether a student could paste your snippet into
their submission and gain points. If yes, change the example.

---

## Step 3: Write the reply

Write it as the course staff member would post it, not as a chatbot. Students on a forum at 11pm
want help, not a five-part essay with headers.

Default shape, adapt freely:

- Open by naming what they got right, when they got something right. Not flattery, specifics. It
  orients them and it is usually true, since a student who wrote a mostly-working program did most
  of it correctly.
- The nudge itself. One or two ideas, not six. A reply with six hints gets skimmed.
- End with a question they can actually answer, or a concrete next thing to try. That is what
  keeps the thread going, and the follow-up is where the learning happens.

Length: three to eight sentences for most posts. If a draft runs long, the usual cause is that it
is answering more than one question; cut the extras or split them.

Tone: warm, direct, collegial. Students read forum replies for signals about whether asking was a
mistake, so the reply should make asking feel worth it. No "great question!", no exclamation
inflation, no faux-Socratic interrogation where every sentence is a question.

If the course profile records a voice or house style, follow it over these defaults.

---

## Step 4: Hand it over

Output in this order, always. The user is scanning, deciding, and pasting.

```
[the reply, ready to paste, nothing else in this block]

---
**Note for you:** <archetype>. <what you diagnosed them as stuck on and which rung you
picked>. <anything that needs your judgment before posting>
```

The reply comes first because that is the thing being copied. Do not wrap it in preamble. Keep the
note to two or three sentences: it exists so the staff member can sanity-check the diagnosis
without rereading the thread, and so anything you were unsure about surfaces before it reaches a
student instead of after.

Piazza, Ed, and Canvas all render markdown and fenced code blocks, so use them normally.

Drafting and posting are separate acts. Hand the draft over and stop; post only under the approval
rules above. Course staff decide what reaches the class.

---

## Being unsure, out loud

The worst failure available here is a confident wrong answer about the course, because students
believe what course staff tell them. An invented deadline, a misremembered policy, or a hint that
contradicts the actual spec costs the student real work and the instructor real credibility.

When the course profile does not cover something, say so in the note and leave a marked gap rather
than filling it: `[CHECK: profile doesn't say whether late days apply to the final project]`.
Course staff can fill that in seconds. They cannot un-post a wrong deadline.

Flag for human review, in the note, whenever:

- The question suggests the assignment spec itself is ambiguous or wrong. That is a fix for
  everyone, not a reply to one student.
- Several students are asking the same thing, which usually means a lecture or spec gap and wants
  a pinned post rather than N replies.
- There are signs of distress, a personal situation, or an accommodations request. Route to the
  human warmly and immediately; do not attempt to handle it in a forum reply.
- The student appears to be describing an academic honesty problem, theirs or someone else's.
- Answering well would require seeing something you cannot: the full repo, the autograder output,
  the actual test that failed.

---

## Batches

Group before drafting. Duplicates get one canonical reply plus a note suggesting a pinned post.
Cluster the rest by topic, since replies to related questions should not contradict each other.
Draft in the same format per question, in the order given, with a one-line triage summary at the
top: how many, how they clustered, which need human eyes before posting.

---

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

Read these when the situation calls for it, not upfront:

- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/course-profile.md`: the interview, the
  profile template, and keeping a profile current. Shared with every skill in this plugin.
- `references/playbook.md`: each archetype worked through with before/after examples, including
  the debugging ladder and how to handle a student who is close but wrong.
- `references/boundaries.md`: students fishing for answers, pressure tactics ("I already
  submitted", "my TA said it was fine"), and how to hold the line warmly.
- `references/piazza-setup.md`: the `.infra` layout, credentials, running `piazza_fetch.py`,
  scheduling a digest, and troubleshooting. Read when questions should be pulled automatically.
- `references/piazza-posting.md`: posting approved replies, the leak-detection threshold, how
  privatizing works and how it can fail, and the audit log. Read before any write to Piazza.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md`: voice and
  formatting, shared with every drafting skill in this plugin. The course profile's
  `Voice` section overrides it.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/ai-tells.md`: the tells that
  make writing read as generated, what human writing looks like instead, and the
  famous "AI tells" that are not. Read before rewriting prose to sound more human.
