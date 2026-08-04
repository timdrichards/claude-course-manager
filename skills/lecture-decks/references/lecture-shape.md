# The shape of a lecture deck

What goes on the slides, in what order, and at what pace. The mechanics live in the other
references; this one is about the teaching.

---

## Pacing

Roughly one slide per minute of talking, counted after the auto-animate pairs are expanded. A fifty
minute lecture is around forty slides, a seventy five minute one around sixty. That rate assumes
slides carrying one idea each; a deck of twenty dense slides runs longer than a deck of forty
sparse ones and is worse to sit through.

Split rather than compress. A slide holding two genuinely distinct points should be two slides even
if the second takes fifteen seconds, because the alternative is a slide the room is still reading
while the instructor talks over it.

Budget the interactive slide generously. It always takes longer than planned, and the time is well
spent, because it is the part students ask questions during.

---

## A default order

Adapt it rather than filling it in. The shape below is what a technical lecture tends to want.

1. **Title.** Course number, lecture number, title, date. One motif. No footer.
2. **Where we were and where this goes.** One slide connecting the last lecture to this one.
   Students who missed the last class are in the room, and this is the cheapest possible fix.
3. **Agenda**, numbered, because it is a real sequence. Three to five items, not eight.
4. **The motivating problem.** Something broken, slow, or wrong, ideally from the course's own
   codebase. The deck earns attention here or it does not earn it.
5. **The naive approach**, shown as working code. This is the first half of an auto-animate pair.
6. **Why it fails**, as the morph. The code changes, or the diagram gains a component, or the
   number moves. This is the slide the lecture is built around.
7. **The idea**, stated plainly on its own slide with nothing else on it.
8. **The mechanism**, usually two or three auto-animate pairs walking through it.
9. **The interactive slide.** Let the class drive a parameter and watch the consequence.
10. **Trade-offs, or what goes wrong.** Labeled cards, not a numbered list, because these are a set
    rather than a sequence.
11. **A discussion prompt**, with speaker notes carrying the question, the answer to listen for,
    and the misconception to name.
12. **What to do next.** The reading, the lab, the deadline. Concrete.

Section-break slides between the big movements help more than they cost. They give the room a
moment to catch up and they give the instructor a place to take questions.

---

## What belongs on a slide

**Code that runs.** Every example on a slide should compile and do what the slide says it does. An
error in a lecture deck is found by a hundred people at once, in real time, and it costs the rest
of the lecture. Use the course's real examples where they exist.

**Ten to twelve lines of code at most.** Longer than that and it is unreadable from the back and
too much to hold in mind. Split it across an auto-animate pair, or highlight regions with
`data-line-numbers` steps and talk through them one at a time.

**One idea per slide.** The test: can the slide be summarized in a sentence that is not a list?

**Numbers with units and sources.** "40ms" beats "slow." A number a student can write down is a
number they can check later.

**Nothing the instructor will read aloud verbatim.** A slide that is a script is a slide the room
reads faster than it is spoken, and then they are ahead and bored. Put the prose in speaker notes.

---

## Speaker notes

`<aside class="notes">` on any slide where the instructor needs something the slide cannot show.
They open with `S` in a second window and never reach the projector.

The slides that need them most:

- **Discussion prompts.** The question is on screen; the notes carry what to listen for, the
  common wrong answer, and how to bring the room back.
- **The interactive slide.** Which order to click things in, what to ask before revealing the
  result, and what the number should come out around so a surprising result is recognized as a bug
  rather than a finding.
- **Anything with a known misconception attached.** Name it in the notes so it gets named out loud
  every time the lecture is given, including by a TA covering it.
- **Timing checkpoints.** "Should be here at 20 minutes." A deck that runs long runs long in the
  same place every term.

Notes do not need to be sentences. They are a prompt for someone who knows the material.

---

## Adapting existing material

Prefer it to inventing. A unit page, a lab handout, last term's deck, or a textbook chapter the
course already uses gives examples that are known to work and that students have seen. Consistency
of naming across the lab and the lecture is worth more than a fresh example that is marginally
better in isolation.

When adapting last term's deck, the things that go stale are the same ones that go stale on a
syllabus: tool and library names, version numbers, dates, and any URL. Check those specifically
rather than reading the whole thing for errors.

---

## The handout question

Ask whether the deck will be posted for students afterward, because it changes what belongs on it.
A deck presented and then discarded can be sparse and lean on the instructor's voice. A deck posted
to the LMS is read by people who were not in the room, and it needs enough on each slide to stand
alone, or a companion set of notes.

The honest middle is a sparse deck plus the speaker notes exported, rather than a dense deck that
serves neither purpose well. Say this out loud when handing over a deck that is about to be posted.
