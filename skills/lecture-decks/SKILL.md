---
name: lecture-decks
description: >
  Build lecture slide decks as single-file reveal.js HTML: animated code diffs, morphing diagrams,
  live interactive demos, and speaker notes, sized to read from the back of a lecture hall. Use
  whenever the user wants slides, a deck, or a presentation for teaching, and especially when they
  say "reveal.js", "HTML slides", "animate this code", "morph between these versions", "show the
  diff", "make this slide interactive", "slides for lecture 5", "a deck on hash tables", "build
  slides from these notes", or "turn this unit into slides". Prefer this over the pptx skill for
  anything presented from a podium or posted for students to review, since a deck here runs in a
  browser and can animate code and run a live demo, which PowerPoint cannot. Do NOT use when the
  user specifically needs a .pptx or .potx file, which is the pptx skill, or to decide what goes on
  the syllabus overview deck, which the syllabus skill plans and then hands here to build.
---

# Lecture decks

A lecture deck is a teaching instrument, not a document. It is read at forty feet by people who
cannot rewind, and the thing it does that no handout can is show change over time: a function
growing an await, a diagram gaining a cache, a number climbing as load rises. Reveal.js is here
because it does that natively and PowerPoint does not.

The output is one `.html` file with no build step, no `node_modules`, and no assets folder. An
instructor can email it, drop it in a course folder, open it on a podium machine that has never
heard of npm, and present it. That constraint is worth protecting: inline the CSS and the
JavaScript, and load reveal itself from a CDN.

## Step 0: establish the course

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326
```

Load `.infra/course-profile.md` for the course number, the term, the voice, and the technologies
this course actually teaches, so code examples use the course's stack rather than a generic one.
Decks belong in `course/slides/`, which survives the term. If the course does not exist yet, offer
course-setup, but do not block a deck on it.

Read `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md` before writing slide
text. The profile's `Voice` section overrides it.

## Ask before building

Two answers change the whole deck, and guessing wrong wastes the work: how long it has to run, and
what the students already know. Roughly one slide per minute of talking is a workable planning
rate, so a fifty minute lecture is around forty slides once the auto-animate pairs are counted.

Also ask whether existing material should be adapted. A unit page, a lab handout, or last term's
deck is better raw material than anything invented here, and the code examples in it are already
known to compile.

## The design pass, before any code

Do this first, in prose, in three or four sentences. Skipping it is how every deck ends up looking
like every other deck.

Name a palette of four to six colors tied to the subject. Pick a display face and a body face
deliberately. Then pick one signature element the deck will be remembered by, a single motif
carried across slides rather than an effect applied to all of them. In a deck about scalable
systems that was a live-ticking requests-per-second readout in the corner; in one about parsing it
might be a token stream in the footer.

`references/design-pass.md` has the method, the palettes to avoid because they read as machine
default, and how to choose a signature element that reinforces the subject instead of decorating
it.

## The scaffold, and the one bug that ruins a dark deck

Reveal wraps the deck in a `.reveal-viewport` div at runtime, and `reveal.min.css` itself, not any
theme file, sets that wrapper to `background-color:#fff; color:#000`. Style only `body` and
`.reveal` and a white sheet sits behind everything, so light text renders washed out and looks
half-transparent. It is the single most common way a good dark theme ships broken.

Every deck needs this, and it is not optional:

```css
.reveal-viewport {
  background-color: var(--bg) !important;
  color: var(--text) !important;
}
```

`references/deck-scaffold.md` has the full verified head and init block: which CDN files to load,
the `Reveal.initialize` options that matter, PDF export, and the reveal 4 boilerplate that is
still all over the internet and 404s against reveal 5.

Confirm the CDN URLs return 200 before relying on them. Versions do get pruned.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -I <url>
```

## Making things move

Auto-animate is the reason to use reveal for teaching. Two consecutive sections marked
`data-auto-animate`, with matching `data-id` attributes on corresponding elements, tween between
states instead of cutting. Applied to a pair of `<pre>` blocks it produces a real code diff:
unchanged lines glide to their new positions while added lines fade in, so students watch the
edit happen rather than hunting for what moved.

The same trick works on diagram nodes, which reflow around an inserted box, and on any element
holding a number.

Use it where the change is the point. A slide that merely follows another slide should be an
ordinary slide, and a deck where everything morphs is as flat as a deck where nothing does.

`references/auto-animate.md` has the three recipes with working markup, plus the failure modes:
duplicate ids, silent no-op when a section is missing the attribute, and how to restart an
animation on purpose.

## One thing that actually responds

At least one slide should compute something live, driven by inline JavaScript: buttons that run a
simulation, a slider that redraws a chart, a small visual model of the thing being taught. This is
what separates a deck from a PDF, and it is also the best question-answering tool available when
someone asks "what if the load doubled."

Plain divs with CSS heights make a perfectly good bar chart. Reach for a charting library only
when the shape genuinely needs one.

Never use `localStorage` or `sessionStorage`. Keep state in ordinary variables.

`references/interaction.md` has the patterns, the chart without a library, and how to keep a
simulation from wandering off during a fifty minute class.

## Reading from the back of the room

Reveal scales the whole slide to fit the screen, and the scale factor is
`min(screen_w / deck_w, screen_h / deck_h)`, so on a widescreen projector the **height** is what
binds. Lowering `width` alone changes nothing. Measured on a 1920x1080 projector, a 960x700 deck
renders 32px text at 46px, while a 980x620 deck renders the same text at 52px.

That gets part of the way. The rest is raising the source sizes for body text, code, and any
custom component, since values tuned on a laptop stay small after scaling. `references/deck-scaffold.md`
has the measured table and the floors worth holding to.

## Speaker notes

Put `<aside class="notes">` on any slide where the instructor needs a prompt: the question to ask,
the misconception to name, the number to say out loud. They open with `S` and never appear on the
projector. Discussion slides in particular are close to useless without them, since the whole
point of the slide is the thing that is not written on it.

## Before handing it over

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/deck_check.py deck.html
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/deck_check.py deck.html --check-urls
```

The checker is offline by default and encodes the failure modes above: a missing viewport
override, reveal 4 paths, mismatched auto-animate ids, undersized type, browser storage, files that
are not self-contained, and em dashes in visible slide text. Fix everything it reports as `FAIL`.

Then look at it rendered, because a deck that passes every check can still be unreadable. The
checker cannot see contrast, crowding, or a diagram that overflows its slide. If a headless browser
is available, load the file at 1920x1080, step through every slide, screenshot them, and actually
look at the images; that pass reliably finds a clipped code block or an overlapping footer that
reads fine in the markup. If no browser is available, say so when handing the deck over rather than
implying it was checked.

Slide text goes out under the instructor's name like everything else here:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prose_check.py --text "the visible slide text"
```

Em dashes survive in decks longer than anywhere else, because nobody proofreads a slide the way
they proofread a paragraph.

Hand over the file, say how to drive it, and say it plainly: arrow keys or space to advance, `S`
for speaker notes, `Esc` for the overview grid, `F` for fullscreen, and `?` for the rest.

## Always

- Never invent a fact about the course, a date, or an API that does not exist. Mark the gap
  `[CHECK: ...]` and list the markers when handing the deck over.
- Code on a slide must run. An example that does not compile gets found by a hundred people at
  once, and it gets found during the lecture.
- Adapt the course's existing examples rather than inventing parallel ones. Students who learned
  `fetchUser` in the lab should meet `fetchUser` on the slide.

## References

- `references/deck-scaffold.md`: the verified head, init options, CDN files, the viewport bug,
  projector sizing with measured numbers, and PDF export. Read before writing the first line.
- `references/auto-animate.md`: code diffs, diagram reflow, and counters, with the failure modes.
- `references/interaction.md`: live demos, charts without a library, and keeping state sane.
- `references/design-pass.md`: palette, type, the signature element, and the looks to avoid.
- `references/lecture-shape.md`: what goes on the slides, pacing, and the shape of a deck that
  survives being presented.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md`: voice and formatting,
  shared with every drafting skill here.
