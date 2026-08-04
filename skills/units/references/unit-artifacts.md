# The rest of the unit

Four things can hang off a unit besides the lesson. Produce one when asked, or when the sibling
units already have it and this unit would be the odd one out. Never produce all four by default; a
course that generates a deck and a quiz for every unit ends up with thirty artifacts nobody
maintains.

---

## The quiz bank

`quiz.json` in the unit folder, in the shape `upload_quiz.py` already takes, so nothing translates
between what gets written here and what reaches Canvas.

```json
{
  "quiz": {
    "title": "Unit 9 check: idempotency",
    "description": "<p>A short check on idempotency and delivery semantics.</p>",
    "quiz_type": "practice_quiz"
  },
  "questions": [
    {
      "question_name": "Q1",
      "question_text": "<p>What makes an operation idempotent?</p>",
      "question_type": "multiple_choice_question",
      "points_possible": 1,
      "answers": [
        {"answer_text": "Running it once or five times leaves the same result", "answer_weight": 100},
        {"answer_text": "It always completes in under a second", "answer_weight": 0},
        {"answer_text": "It never fails", "answer_weight": 0}
      ]
    }
  ]
}
```

- `quiz_type` is `practice_quiz` for an ungraded check, `assignment` for a graded one. Default to
  the former unless the instructor asks otherwise.
- Field names match the Classic Quiz question payload exactly. See
  `${CLAUDE_PLUGIN_ROOT}/skills/canvas/references/quizzes.md`.
- Prefer auto gradable types: `multiple_choice_question`, `true_false_question`,
  `short_answer_question`. An essay question in a per-unit check creates grading work the unit was
  not asking for.

Writing the questions:

- Four to six. This checks understanding rather than examining it.
- Draw from the unit's own content: the terms bolded in the Naming the pattern beat, and the
  observable condition from the Exercise. Trivia the unit never taught is how a check for
  understanding becomes a memory test.
- At least one question should require telling this unit's concept apart from the previous unit's,
  mirroring the backward contrast the lesson already makes. Objectives that only ever get tested in
  isolation produce students who know nine things and cannot pick between them.

Upload with the write gate the same as everything else:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/upload_quiz.py quiz.json --course 326 --dry-run
```

---

## The deck

Built by the lecture-decks skill, from the unit, not from scratch. The unit is better raw material
than anything invented alongside it, and its code examples are already known to run.

Plan the deck here, build it there:

- The hook comes from the Introduction's framing, meaning the problem from the source reading
  rather than "today we will learn about X."
- The middle is the Notes arc compressed: what looked fine, why it was not, what the fix is, what
  the pattern is called. A deck that reproduces every code block is a document read aloud.
- One slide on the real world tool, one teaser for the exercise, and a closing slide naming the
  next unit.
- Roughly one slide per minute of talking.

Save it in the unit folder under whatever the course's config calls it, `slides.html` by default.
It belongs to the unit, and putting it there is what keeps them revised together.

### When the course ships PowerPoint

Some courses do, and converting a reveal deck is not the answer: the animated code diff and any
live demo are exactly what the conversion drops. Build a real `.pptx` instead, through the `pptx`
skill, and keep two things consistent across the course.

**The theme is decided once, not per deck.** Look for `.deck-theme.json` at the course root first
and reuse its palette, fonts, and motif exactly. Consistency across a term's decks is the whole
point, so do not restyle even slightly. If there is no theme file but the course already has decks,
do not try to recover a theme from the `.pptx`: a pptxgenjs deck applies colors as per-shape hex
fills rather than a theme color scheme, so there is nothing real in there to read. Ask for the
values instead, then write `.deck-theme.json` so the next unit inherits them.

If neither exists, choose a palette and one repeating motif tied to what the course teaches, write
it to `.deck-theme.json` immediately, and every later deck follows it.

**Look at the rendered slides before calling it done.** Render to images and check them, because a
deck that is correct in the build script still overflows, crowds, and clips.

```bash
python3 ~/.claude/skills/pptx/scripts/office/soffice.py --headless --convert-to pdf out.pptx
pdftoppm -jpeg -r 150 out.pdf slide
```

If the `syllabus-deck` skill is installed, its `deck-template.js` chrome helpers and its QA prompts
are a better starting point than writing either from scratch.

---

## The Canvas page

`unit.html`, from `render_html.py`. See `canvas-render.md` beside this file.

---

## A supplementary document

A deeper reference on one tool a unit uses in passing: containers, a debugger, a rebase workflow.
Useful to the student who wants more than the unit's single Real World section gives them.

**Only on explicit request.** If it is unclear whether the instructor wants this or wants the
unit's Real World section expanded, ask, because the two answers produce different work.

Name it after its parent unit, `09-docker-compose.md`, so it never reads as orphaned. Open with one
line saying which unit it supports and close with a line pointing back to it. In between, whatever
organization the topic actually has: concepts, the commands that matter, a worked example, the
pitfalls. Match the unit's voice, which is concrete, code driven, and does not use a term it has
not explained.

Render it to HTML through the same pipeline as the lesson when it is going to Canvas.
