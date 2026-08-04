# The companion overview deck

A short deck that walks students through the course in the first session or as a recorded
welcome. It is a second copy of facts that already live in the syllabus, which means it will
drift, and a deck that contradicts the syllabus is worse than no deck: students believe whichever
they saw last.

**The rule that follows: generate the deck from the syllabus, never alongside it.** When the two
disagree, the syllabus is right and the deck gets rebuilt.

---

## What goes on it

Twelve to sixteen slides. The deck is not the syllabus; it is the parts a student needs to hear
said out loud.

1. **Title.** Course number, title, term, instructor.
2. **What this course is.** The pedagogical stance in one or two sentences, quoted from the
   syllabus description rather than reworded.
3. **What you will build.** The concrete end state. This is the slide that makes people want to
   take the course.
4. **How it is organized.** Content units, parallel tracks, what a week looks like.
5. **Time commitment.** The weekly hours, the per-day number, and the honest advice. In a
   compressed term this is the most important slide in the deck.
6. **Learning objectives.** Condensed; the full list stays in the syllabus.
7. **How you are assessed.** The weights table.
8. **The project or major thread**, if there is one, with its milestone timeline.
9. **Schedule at a glance.** Weeks against units and deliverables.
10. **The grading scale.** State plainly whether there is a curve.
11. **Communication.** How to reach staff, the subject-line convention, expected response time.
12. **Policies.** Late work, no-exemptions, incompletes.
13. **AI use.** Permitted, not permitted, disclosure. Worth its own slide.
14. **Support resources.** Counseling with the phone number, tutoring, writing center.
15. **What to do first.** The concrete first action, with the deadline.

---

## Pacing

**Optimize for how easy the deck is to present, not for the fewest slides.** A slide holding more
than one genuinely distinct point should be split, even if each resulting slide takes only a few
seconds to talk through. More slides is the expected result and it is fine.

The real constraint is total talk time. An overview deck should run about ten to twelve minutes
start to finish.

---

## Building it

**Match the course's existing decks.** A syllabus overview that looks unlike every unit deck is
its own kind of wrong. Look in `course/slides/` and read one before writing anything, along with
any theme file or build script the course keeps beside them.

**The default is the lecture-decks skill**, which builds single-file reveal.js decks. Read
`${CLAUDE_PLUGIN_ROOT}/skills/lecture-decks/SKILL.md` and hand it the content plan above. An
overview deck is mostly facts rather than animation, so it uses little of what that skill offers
beyond the scaffold and the sizing, and that is fine. The reason to build it there anyway is that
it comes out looking like the rest of the course's decks.

**Use the pptx skill instead when the deck has to be a .pptx**, because a department wants the
file, a co-instructor will edit it in PowerPoint, or it is going somewhere that will not open
HTML. Read its SKILL.md first, then build from the content plan above.

Either way the content comes from the live syllabus, fetched fresh, not from the course profile's
summary and not from the previous term's deck.

Set the deck to be browsed by an individual in a window when it is meant for asynchronous
viewing rather than presentation from a podium.

---

## House style on slides

Everything in `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md` applies, and
one rule needs active enforcement: **sweep visible slide text for em-dashes before shipping.**
They survive in decks longer than anywhere else because nobody proofreads a slide the way they
proofread a paragraph. Build-script comments are not visible slide content and do not need
touching.

---

## The numbers that go stale first

When auditing an existing deck against the syllabus, check these in order. Every one has drifted
in a real course:

1. **Tool and technology names**, especially inside learning objectives. A course that switches
   its database mid-term will correct the syllabus, the homework, and the assignment text, and
   leave the deck saying the old name. This is the most common deck drift and the least noticed,
   because nobody reopens the deck after week one.
2. **Weights**, if the assignment plan changed after the deck was built.
3. **The late policy**, which changes mid-term more often than any other.
4. **Dates**, in the schedule slide.
5. **Staff**, when a TA is added after the term starts.
6. **Milestone titles**, which get renamed as the term reveals what they actually are.

A deck built in week zero and never revisited is normal. That is precisely why the audit belongs
in the syllabus workflow rather than in someone's memory: any time the syllabus changes, ask
whether the deck now contradicts it, and say so even when nobody asked.

---

## A presenter script, if one is written

It must track each slide's actual visible text closely. Quote the slide's captions and bullets
near-verbatim for short punchline sentences rather than paraphrasing them, and cite commands and
code literally rather than describing them generically.

Adding spoken color the slide has no room for is expected and good, but frame it explicitly as
going beyond the slide, for instance "the syllabus goes into more detail on this." Never blend it
in as though it were on-screen text: someone reading the script while looking at the slide has to
be able to tell which is which.
