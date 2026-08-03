# Building and maintaining a course profile

The profile is the difference between a reply that sounds like a competent stranger and a reply
that sounds like course staff. It is worth ten minutes up front and it pays for itself on the
first question you answer.

## Ask for materials first

Before asking a single interview question, ask for documents. One syllabus and one assignment
spec answer most of what follows, and reading them is faster and more accurate than an interview.
Ask for, in rough priority order:

1. The syllabus (policies, schedule, grading, AI use policy)
2. The assignment specs students are currently working on, and the next one or two coming up
3. Whatever the course uses for lecture material: slides, notes, a schedule with topics per week
4. Starter code or repo structure, if the assignments have one
5. Any existing Piazza threads the instructor considers good model answers, which is the single
   most useful artifact for matching voice

If they can only give you one thing, take the current assignment spec. It constrains the answers
that matter most.

## The interview

Ask in batches, not one at a time, and skip anything the documents already answered. Use
`AskUserQuestion` where the answers are naturally multiple-choice, plain text where they are not.

**Identity and level**
- Course number, title, institution, term
- Who takes this: year, major, what they are assumed to already know
- Enrollment, since a 300-person course and a 25-person seminar want different reply norms

**What is being taught right now**
- Where in the semester the course is, and what topic the current week covers
- What has been covered already, which is the single most useful fact for calibrating a hint,
  because a hint that uses a concept from three weeks out is not a hint
- What is deliberately *not* taught, or taught later, which is often where students go looking
  for shortcuts (the class that has not done recursion yet, the class where you must not use a
  library that trivializes the assignment)

**The current assignment**
- What it asks, and specifically what skill it is testing. This is the crux: you can only
  protect the answer if you know what the answer is *for*. If the assignment tests whether they
  can choose a data structure, the choice is off limits even though it would be a fine hint in a
  course where that was assumed knowledge.
- Required and forbidden tools, libraries, language features
- Common wrong turns the instructor already knows about, which lets you recognize a wrong turn
  from two lines of a student's post

**Rules and boundaries**
- Collaboration policy and AI use policy, since students ask about these constantly and getting
  them wrong is a real problem
- Late policy, extension policy, regrade policy, in enough detail to answer directly
- Anything the instructor considers a hard line: topics where no hint is acceptable, or the
  reverse, things they are happy to just tell students

**Voice and logistics**
- Office hours and how to reach staff, since a good fraction of replies end by pointing there
- How the instructor writes: formal or casual, first person singular or "we", any habits
  (one syllabus in hand may already show this; ask if not)
- Anything they never want said to students

## The profile template

Write to `<course>/.infra/course-profile.md`, then also deliver it with `SendUserFile` so the
user has a copy independent of any one machine. It lives one level above the per-service folders
because it is course knowledge, not Piazza knowledge: every skill in this plugin reads the same
file. Keep it factual and skimmable; it gets read on every future question.

**Include a URL for every platform the course uses.** `course_infra.py verify` cross-checks each
one against that tool's `config.json`, and that check is what catches a folder that has drifted
onto the wrong course. A platform whose URL is missing from the profile gets no mismatch check at
all, which means a folder copied from last term will happily write into last term's class.

```markdown
# Course Profile: <COURSE NUMBER> <Title> (<Term>)

## Basics
- Institution, credits, enrollment
- Audience and assumed background
- Staff and office hours
- Where students ask questions (Piazza, Ed, Canvas, email)

## Platforms  (each line is cross-checked against .infra/<tool>/config.json)
- Piazza: https://piazza.com/class/<id>
- Canvas: https://<school>.instructure.com/courses/<id>
- Gradescope: https://www.gradescope.com/courses/<id>

## Schedule and coverage
- Current week and topic (UPDATE THIS as the term moves)
- Covered so far: <ordered list of topics, most recent last>
- Coming up, not yet safe to assume: <topics>
- Never covered in this course: <topics students may reach for anyway>

## Current assignment(s)
### <Name> — due <date>
- What it asks students to build
- **Skill under test:** <the thing the student must produce themselves>
- **Off limits in hints:** <the specific things that would give it away>
- Required / forbidden tools
- Known common mistakes
- Starter code and repo layout

## Policies
- Late work, extensions
- Collaboration
- AI use
- Regrades
- Submission mechanics

## Voice
- Tone, person, formatting habits
- Phrases to use / never use
- Model replies: <paste 1-2 real ones if available>

## Escalate to a human when
- <instructor's own list, plus the defaults in SKILL.md>

## Gaps
- <anything unknown, so future replies flag it instead of inventing it>
```

The `Gaps` section is load-bearing. An honest record of what the profile does not know is what
keeps a reply from confidently inventing a policy.

## Keeping it current

A stale profile is dangerous in a specific way: it is confidently wrong rather than obviously
empty. The `Current week` and `Current assignment` sections go stale within days.

When a question implies the course has moved on from what the profile says, say so in the note
and ask. When the user mentions a new assignment, offer to update the profile and re-deliver it.
Update in place rather than starting over, so the accumulated detail about voice and common
mistakes is not lost.
