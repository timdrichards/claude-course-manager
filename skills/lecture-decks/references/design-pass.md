# The design pass

Do this before writing markup, in three or four sentences of prose, and write it down where the
user can see it. It takes a minute and it is the difference between a deck that looks like this
course and a deck that looks like every generated deck.

The reason to commit in words first is that a palette chosen while writing CSS is really a palette
chosen by whichever hex code came to mind, and those are always the same six hex codes.

---

## Name a palette

Four to six colors, tied to the subject. Background, one or two surface tones, body text, muted
text, and one or two accents.

Tie the choice to something real about the material. A distributed systems deck can take its
accents from a status dashboard, amber for saturation and teal for healthy. A compilers deck can
borrow a terminal palette honestly, since that is where the students will meet the tool. A deck
about typography or design has license to be more chromatic than a deck about memory allocation.
The tie does not have to be clever; it has to be a reason.

Then check contrast against the background for every text color. A projector in a lit lecture hall
loses far more contrast than a laptop suggests, so treat 4.5:1 as the floor for body text and aim
higher. Mid-grey on dark navy reads fine at a desk and disappears in row twenty.

Two accents is a good target, and the second should be rare. If everything is highlighted, nothing
is.

**Looks to avoid**, because they are what gets produced by default and instructors recognize them:

- Cream background with terracotta and sage accents.
- Near-black with a single saturated neon, particularly cyan or lime, and a glow.
- The broadsheet newspaper look: serif headline, rules, tight columns.
- Purple-to-blue gradients on every heading or card.
- Glassmorphism panels floating over a blurred photo.

None of these are bad in themselves. They are all overexposed, and a deck that uses one reads as
untouched.

---

## Pick two typefaces on purpose

A display face for headings and a body face, plus a monospace for code. Google Fonts works and
loads fast enough.

`Inter` with `JetBrains Mono` is a sound pairing and a sensible fallback, but choosing it every
time is the same failure as choosing the same palette every time. Consider what the subject wants:
a geometric sans for anything spatial, a humanist sans for a course with a lot of prose on slides,
a slab or a strong grotesque for a deck that needs to feel like a systems course. `Space Grotesk`,
`Sora`, `IBM Plex Sans`, `Work Sans`, `Fraunces`, and `Newsreader` all pair well with a mono and
none of them are the default.

The monospace matters more here than in most design work, because a code-heavy lecture deck is
mostly monospace by area. `JetBrains Mono`, `IBM Plex Mono`, and `Fira Code` all hold up at a
distance; avoid anything with a small x-height or ambiguous `1lI`.

Always include a system fallback in the stack so a dead podium network degrades to something
readable rather than to Times.

---

## Choose one signature element

The thing the deck is remembered by. One motif, carried across slides, that reinforces the subject
rather than decorating it.

Good ones are usually small, live, and out of the way. A ticking requests-per-second and p99
readout in the corner of a scalability deck. A progress rail that fills as the lecture moves
through its sections. A token stream in the footer of a parsing deck. A tiny memory map that
updates in an allocation deck.

The test is whether it says something. A pulsing gradient bar says nothing. A counter showing the
number of records being scanned says the thing the lecture is about.

One is the number. Two competing motifs is visual noise, and a deck with an effect on every slide
is exhausting to sit through and impossible to present over.

---

## Layout habits worth keeping

**Left-align body slides.** Reveal centers everything by default. Centered text is right for a
title and a section break and wrong for anything with more than one line, because a ragged left
edge slows down every reader in the room.

**Use numbered lists only for genuine sequences.** An agenda is a sequence. A process is a
sequence. Three properties of a hash function are not, and numbering them invites a student to ask
which is first. Cards, columns, or plain bullets are the honest form for a set.

**Give slides room.** A slide holding one idea with air around it presents better than a dense one,
and splitting is cheap. Total talk time is the real constraint, not slide count.

**Bold sparingly.** Two or three genuinely important spans per deck, not every key term. Bolding
everything is a habit that reads as machine emphasis and it also stops working.

**Do not put a footer on the title slide.** Course number, lecture number, and date belong in a
small persistent footer on body slides; the title slide already says all of it larger.

---

## A worked example

For a lecture on caching in a scalable systems course:

> Palette from a monitoring dashboard: deep navy background `#0b1a2b`, a lifted surface `#12293f`
> for code and cards, near-white `#e6eef7` for text, muted steel `#8fa8c0` for captions, amber
> `#ffb703` for anything saturated or slow, teal `#2ec4b6` for anything healthy or cached.
> `Space Grotesk` for headings against `JetBrains Mono` for code, which keeps the headings distinct
> from the wall of monospace the deck is mostly made of. The signature element is a HUD in the
> bottom right showing live requests per second and p99 latency, ticking throughout, driven by the
> same simulation the interactive slide exposes to the audience.

Four sentences. Every later decision follows from them, and the deck cannot drift into the default
look because the default look was never on the table.
