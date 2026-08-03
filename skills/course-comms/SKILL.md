---
name: course-comms
description: >
  Draft announcements, emails, and notices to a class or to course staff: deadline changes, exam
  logistics, corrections to an assignment, grade releases, mid-semester check-ins, and end-of-term
  messages. Use when the user says "announce that", "email the class", "let students know",
  "draft an announcement", "the deadline moved", "write to my TAs", "send a reminder about",
  "post a correction", or hands over something that needs to reach students. Also use when
  another skill produces something the whole class needs to hear, such as a spec clarification or
  a pinned answer to a repeated question. Do NOT use for replying to an individual student, which
  is student-questions, or for the assignment or syllabus text itself.
---

# Course Comms

A class announcement is read once, quickly, by people who are already behind. It succeeds if the
person who skimmed it in eight seconds still came away knowing what changed and what they have to
do. Most announcements fail at that not because they are unclear but because the news is in
paragraph three.

## Before drafting

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326
```

Load `.infra/course-profile.md` for voice, staff names, office hours, and policies. Anything that
states a policy or a date has to match the syllabus, and a message contradicting it is what the
class will quote back later.

Confirm the course and section out loud before writing. An announcement is the one artifact here
that cannot be unsent, and a MISMATCH from `verify` means the folder does not know which class it
belongs to.

## Shape

Lead with the change and the action. Everything else is context and belongs underneath.

```
<one sentence: what changed and what to do>

<the details that matter: new date, new location, what is unaffected>

<why, briefly, if it helps them trust it>

<where to ask about it>
```

Rules that hold across message types:

- **The subject line is the message.** "Homework 3 deadline moved to Friday" beats "Homework 3
  update", which beats "Important announcement". A student who reads only subject lines should
  still get the news.
- **Dates carry the day of the week and the timezone.** "Friday, October 9 at 11:59pm ET". A bare
  date gets misread by someone every time, and a bare time gets misread by anyone traveling.
- **Say explicitly what is not changing.** When a deadline moves, the most common follow-up
  question is whether everything else moved too. Answering it costs one clause.
- **One announcement, one topic.** Two pieces of news in one post means half the class absorbs
  one. Send two.
- **No preamble.** "I hope everyone is doing well" delays the news past where people stop
  reading.
- **Short.** Four to eight sentences for most. If it runs long, either it is two announcements or
  the details belong in a linked document.

Follow the profile's voice over these defaults where they conflict. First person singular or
"we", formal or casual, is the instructor's choice and consistency with lecture matters more than
any style rule here.

## Tone, and what students read into it

Students infer a lot about how a course is run from how it writes to them. A few things to hold:

- **Do not apologize excessively, and do not be defensive.** When the course made a mistake, say
  what happened and what is being done, once. A correction that spends three sentences on regret
  reads as less trustworthy than one that spends them on the fix.
- **Do not use a deadline as a disciplinary moment.** "As stated in the syllabus, no late work
  will be accepted, and students who have not started should consider..." lands as hostile to the
  whole class in order to address a few. Say the policy plainly and move on.
- **Bad news early and plainly beats bad news softened.** An exam that has to move, a grading
  delay, a mistake in a spec: students handle these fine when told directly and badly when they
  discover them.
- **Do not thank the class for patience preemptively.** Say what happened.

## Common situations

Read `references/situations.md` for the shape of each: deadline changes, spec corrections, exam
logistics, grade releases, a repeated question that needs a pinned answer, staff-facing messages,
mid-semester check-ins, and the difficult ones like a course-wide grading error or an academic
honesty notice to the whole class.

## Sending

Draft first, always. Show the full text, and let the user read it before anything goes out.

**Canvas announcement**: the default for anything the whole class needs:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 \
    announce --title "Homework 3 deadline moved to Friday" --file body.md --live
```

Writes need `--live` and `"write_mode": "live"` in the course config. Approval is per message: a
user saying two drafts look good has not approved sending two. Ask which.

**`--at <ISO timestamp>`** schedules instead of posting now. Use it for anything written outside
business hours. A 2am announcement gets read at 2am by exactly the students who should be
asleep, and it sets an expectation about response times that nobody wants to keep.

**Piazza**: for anything that belongs in the discussion where students already are, especially a
pinned answer to a repeated question. The student-questions skill owns Piazza posting, but note
that `piazza_post.py` only replies to an existing thread: **creating a new post and pinning it are
manual**. Draft the text, say plainly that it needs to be posted and pinned by hand, and do not
imply a script will do it.

**Email**: for staff, for individuals, and for anything students must not miss. If Gmail is
connected, draft it there and leave it in drafts rather than sending. Class-wide email through
the LMS reaches everyone including those who muted announcements, which is why it should be
reserved for the things that justify it.

**Nothing goes out on a scheduled or unattended run.** A schedule fires with nobody watching, so
the read-and-approve step cannot have happened. Scheduled runs draft and stop.

After sending, report the URL so the user can see it in context. If a send fails, say so
immediately rather than moving to the next item.

## Handing over

```
[the message, ready to post, nothing else in this block]

---
**Note for you:** <where it should go and why> <anything needing a decision before it goes>
<anything checked against the syllabus or profile, or that could not be>
```

Flag in the note whenever: the message states a policy the profile does not cover; it commits the
course to something like a grade release date; it affects students unequally, such as a deadline
change landing during a religious observance or across timezones for remote students; or it is
the kind of message that predictably generates individual requests, so the user can decide in
advance how those will be handled.

Never invent a date, a room number, a policy, or a staff member's availability. Leave a marked
gap instead: `[CHECK: is the exam room confirmed?]`. Course staff fill that in seconds. They
cannot unsend a wrong room number to 200 people.

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

- `references/situations.md`: worked shapes for the recurring message types, including the ones
  that are difficult to write well.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md`: voice and
  formatting, shared with every drafting skill in this plugin. The course profile's
  `Voice` section overrides it.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/ai-tells.md`: the tells that
  make writing read as generated, what human writing looks like instead, and the
  famous "AI tells" that are not. Read before rewriting prose to sound more human.
