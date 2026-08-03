# Sections

The inventory, in the order students read it. Not every course needs every section, and a course
that has no exams should say so rather than omit the line.

The ordering principle: **facts a student is looking up come before prose a student reads once.**
Someone opening the syllabus in week four wants the late policy, not the course description.

---

## Header block

A scannable list of the facts that get looked up, before any prose. One line each:

Number, title, instructor, LMS URL, semester, mode (in person / online / hybrid, synchronous or
asynchronous), scheduled meetings, exams, group work, credits, prerequisites.

State the empty ones explicitly. "Exams: There are no exams in this course" and "Scheduled
Meetings: There are no scheduled meetings for this course. It is online and asynchronous" both
answer a question that otherwise becomes an email. Prerequisites should say what a student from
another institution does: usually an override request.

---

## Description

What the course is about and why it is shaped the way it is. Two or three paragraphs.

The second paragraph is the one worth writing carefully: the course's pedagogical stance, in
plain language. "This course is concept-first and experiential. You will build and break real
systems before we put names to the patterns you discover" tells a student how to approach the
work in a way that a topic list cannot.

If the course counts toward a major requirement or elective, say which.

---

## Staff and contact

Instructor, email, office hours and how they work, TAs and their emails.

"By appointment, via Google Meet" is a real answer for an asynchronous course and better than an
invented weekly slot nobody attends.

---

## Learning objectives

Bulleted, each starting with a verb, each naming something a student could demonstrate. Six to
ten. These are the most-skipped section by students and the most-scrutinized by accreditation
review, so they need to be true rather than aspirational.

**They go stale in a specific way.** When the course changes a tool mid-term, the objective that
names the old tool is easy to miss. A real instance: a course switched its database from Prisma
to MongoDB and corrected the description, the homework, and the sprint text, but the objective
still said "Prisma-backed database" months later, and so did the overview deck. Check objectives
against the current unit plan on every audit.

---

## Time commitment

Often omitted, and one of the most useful sections in a compressed term.

Derive it rather than asserting it. The institutional credit-hour rule gives a total: at UMass,
45 hours per credit per semester, so a three-credit course is about 135 hours and a four-credit
course about 180. **That total is fixed and does not shrink when the calendar does.** What
changes is the weekly rate.

Then state the weekly number, what it means per day, and the honest advice that follows. A
six-week session running a full course at two and a half times the normal weekly pace should say
so, should say that the work does not compress into a weekend burst when each day builds on the
one before, and should advise against pairing it with another demanding course or full-time work.
Invite the student to email before the term begins if the timing is a problem.

This section exists so a student can decide before the drop deadline instead of discovering it in
week three. Write it to be believed, not to be reassuring.

---

## Course structure

How learning is organized: what the unit of content is, how units relate, what a typical week
looks like, and which platform holds what.

Name the content unit explicitly if it is not a lecture. "Knowledge Unit," "module," "sprint,"
and "lab" all mean different things at different institutions, so define the term the first time
it appears and use it consistently afterward.

Give each platform a one-line role: the LMS is where everything is found and where grades are
posted; the autograder is where code is submitted; the repository host is where team work lives.
Say how they sync and whether the sync is manual, because a student seeing a grade in one and not
the other will otherwise email about it.

---

## Required materials and technology

Textbook if there is one, with how to access it free through the institution when that applies.

**Hardware requirements belong here and most templates have no slot for them.** If the course
needs a machine that can run a container stack, say so concretely: operating systems supported,
minimum RAM, free disk, and the explicit statement that a Chromebook or tablet is not sufficient.
Then say what a student without one should do and by when. This is an access issue and burying it
costs a student their enrollment.

Say what students should install now and what they should wait to install as part of a setup
unit. Premature installation generates support load.

---

## Assignments and weights

A table with one row per graded category and, where useful, sub-rows per instance.

Columns worth having: category, brief description, **assessment type**, count, weight.

**Use a formative / summative / combined marker.** Define it once above the table: formative work
builds understanding and carries little or no grade weight, summative work measures it, combined
does both. It tells students where the stakes are, and it gives grading a principled reason to
treat early work more gently than late work.

**Allow a 0% row.** Work that is expected but ungraded is a real category. Say plainly that it is
not submitted, does not count toward the grade, and is expected anyway, along with why.

Weights must sum to 100 and must match the LMS assignment groups. If the course uses weighted
groups, the syllabus table and the LMS group weights are two copies of one fact and will drift.

---

## Policies

Each policy gets a heading and a direct statement. Ordered by how often students need them.

**Late work.** The rule, the arithmetic, and the cutoff. State which categories it applies to by
name; a rule that says "assignments" when the course has homework, labs, sprints, and quizzes is
not a rule. Where a category has a hard deadline with no late allowance, say why, since a reason
is what makes it read as considered rather than punitive.

The late policy is the single most common source of drift, in two directions: text that names
only some categories, and an LMS late-policy configuration that does not match the text. Audit
both.

**Extensions.** How to ask, how far in advance, what qualifies. Note that granted extensions are
implemented as real per-student LMS overrides rather than verbal agreements, so the deadline is
tracked rather than remembered.

**AI use.** The most-read policy in a computing course. Say what is permitted, what is not, and
what disclosure is required, with concrete examples of each. "Use it like documentation: look up
a syntax detail, get a plain-language explanation of something you read" is checkable. "Do not
ask it to write your code, generate solutions, or debug your submission end to end" is checkable.
Then state the disclosure requirement and that undisclosed use is an honesty violation.

Keep the disclosure burden proportionate. A brief note on what it was used for is enforceable; a
full transcript requirement is not, and an unenforced policy teaches that policies are optional.

**Academic honesty and collaboration.** What collaboration is encouraged, what is prohibited, and
where the institution's policy lives. In a team-based course, say how individual accountability
works inside group work.

**Grading and regrades.** The scale, whether there is a curve, how to request a regrade and by
when. State the scale as explicit bands.

**Accommodations.** Point to the disability services office and the process. In a compressed
term, note the registration window relative to term length, since a two-week window is half of a
six-week course.

**Exemptions and incompletes.** What the course does not make exceptions for, and the conditions
for an incomplete under institutional policy.

**Submission mechanics.** Where each kind of work is submitted, resubmission rules, and what
counts as the graded attempt.

**Communication.** How to reach staff, expected response time, and any required subject-line
convention. If the course requires a prefix like `[326]`, say it here and say that messages
without it may be missed.

---

## Schedule

A table: week, dates, content units, what is due.

Index it by whatever the course's actual content unit is. When two tracks run with an offset,
encode the offset in the table rather than describing it in prose, and make sure the "due" column
reflects the real deadline rather than the week the material was taught.

State the single weekly deadline if there is one. A course where everything is due Sunday at
11:59 PM is much easier to plan around, and saying it once is better than repeating it per row.

---

## Support resources

Counseling and mental health with the phone number and whether it is staffed at all hours, dean
of students, tutoring, writing center, library. Name the specific service the course's own
deliverables need: a course with a written reflection or a poster should point at the writing
center by name.

---

## Sections to omit rather than fake

An attendance policy for an asynchronous course, office hours nobody holds, a required textbook
nobody reads, a participation grade with no defined mechanism. Each one trains students that the
syllabus is decorative, which is expensive the first time a real policy needs to be enforced.
