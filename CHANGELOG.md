# Changelog

All notable changes to this plugin are recorded here.

**What counts as the public interface**, and therefore what a version bump is about: skill names
and their trigger descriptions, script names and their command-line flags, the JSON shapes those
scripts read and write, the reference file names a skill links to, and the documented safety
rules. Prose improvements inside a reference are not a version bump. Renaming a flag is.

## 0.7.0

Units, and the arc they form.

**The unit**

- New `units` skill. A unit is a folder rather than a file: the lesson, the code it tells students
  to type, and whichever of the quiz, deck, and Canvas render that unit has, alongside a metadata
  file recording what it teaches and where it sits.
- New `units.py`: `list`, `new`, `adopt`, `check`, `arc`, `shape`, `path`. `check` reads one unit
  against the course's own section contract; `arc` reads the units against each other. Both exit 1
  on a `FAIL`, so either works as a pre-publish step. Pure standard library.
- The section contract is per course, recorded in `course.json` under `units`, and every check
  follows it rather than following this plugin's opinion. Three presets ship as starting points:
  `knowledge-unit` (the default, a broken example repaired in front of the reader, with the three
  Notes beats), `lecture`, and `minimal`. A course can replace the section list entirely.
- Learning objectives live in the unit's metadata and are written into the lesson where students
  see them. Objectives naming an unobservable state, such as "understand", are flagged, since
  nothing can check one.

**The arc**

- The arc checks are the ones that cannot be made from inside a single unit: numbering gaps,
  duplicate numbers, a prerequisite pointing forward or at nothing, an act whose units are not
  consecutive, a `next` pointer that outlived the unit it named, a Looking Ahead promising a unit
  that no longer follows, and an Introduction that never names the unit before it.
- Acts group units into the parts of a course's argument, and are all or nothing: a course where
  some units belong to a named part and others float reads worse than one with no parts at all.
- `arc.md` at the units root carries the through line, and its absence is reported.

**Courses that already have units**

- Unit locations and filenames are configurable, because a course that already has units named
  them years ago. `path` points at the existing folder, and `files` and `artifacts` take patterns
  with `{n}`, `{number}`, and `{slug}`, so `Reference Units/12-resilience/12.md` is read where it
  sits.
- New `units.py adopt`: reads a folder of units that already exists, infers the lesson filename
  from what most units share rather than from whichever folder sorts first, lists the per-unit
  artifacts while ignoring one-offs, and writes one metadata file per unit with the title taken
  from each lesson's own heading. It previews by default, renames nothing, moves nothing, and never
  overwrites metadata that is already there.
- A repo that is not a course-manager course keeps the same config in `.units.json` at its root, so
  adopting a folder of units does not require adopting the course layout first.

**Publishing a unit**

- New `render_html.py` and `assets/unit.css`: Markdown to Canvas-ready HTML with the styling
  inlined onto every element, and syntax highlighting inlined per token, which is the only kind
  Canvas does not strip. It verifies its own output rather than leaving a `grep` for someone to
  remember, and exits non-zero when the page would reach Canvas stripped of its formatting or
  missing the heading Canvas derives a page title from.
- `render_html.py` is the only script here needing packages outside the standard library
  (`markdown`, `premailer`, `pygments`), and it names the one that is missing. Pointed at a unit
  folder it takes `unit.md`, or the folder's single Markdown file, so a course calling its lessons
  `12.md` needs no arguments.
- The unit deck is planned here and built by `lecture-decks`. The PowerPoint path is covered too,
  including reusing a course's `.deck-theme.json` rather than restyling per deck.

**Also**

- New `worked-example.md` reference: one full annotated unit, for when a model beats a description.
- `course/units/` now has a documented shape of its own in the layout reference, and `lecture-decks`
  points at the units skill when a deck belongs to a numbered unit.

## 0.6.0

Lecture decks as reveal.js HTML.

- New `lecture-decks` skill: single-file reveal.js decks with auto-animate code diffs, morphing
  diagrams, an interactive slide, and speaker notes, sized to read from the back of a lecture hall.
- New `deck_check.py`, offline by default, with `--check-urls` to resolve CDN references. It
  encodes the failure modes that render without raising anything in a browser: a missing
  `.reveal-viewport` override, reveal 3 and 4 paths, mismatched auto-animate ids, undersized type,
  browser storage, local file references, and em dashes in visible slide text.
- The viewport override is treated as mandatory rather than a debugging step. `reveal.min.css`
  itself, not a theme file, sets that wrapper to white, so a dark deck without the override ships
  looking washed out.
- Deck sizing guidance is measured rather than estimated. On a widescreen projector the deck
  height sets the scale factor and the width does nothing, so the skill's `deck-scaffold` reference carries
  a scale table and source-size floors instead of an instruction to make the text bigger.
- The syllabus skill's companion overview deck now names this skill as the deck pipeline.

## 0.5.0

Course folder layout.

- `course_infra.py init` now creates the course material tree alongside `.infra`, split into
  `course/` for what survives every offering and `semesters/<term>/` for what does not.
- New `layout` command builds or repairs the tree, and rolls a course into a new term.
- Folder naming is per course and recorded in `course.json`: `kebab` (default), `snake`, `title`,
  or `as-is`. `--add-folder` and `--skip-folder` adjust the default set.
- Semester slugs are `YYYY-MM-season[-session]` and always kebab, whatever the naming style,
  because they have to sort. Sessions advance the month, so Summer Session II is `2026-07-summer-2`
  and sorts after Session I.
- `students/`, `grading/`, and `accommodations/` are added to the course `.gitignore` on creation.
  Appends rather than overwrites, and does not duplicate on rerun.
- Nothing is ever deleted. Dropping a folder from the configuration stops it being created and
  leaves its contents alone. `verify` reports drift in both directions.

## 0.4.0

Writing that does not read as machine output.

- New `prose_check.py`, a checker for the tells catalogued in Wikipedia's *Signs of AI writing*.
  Findings are graded `FIX` (character set and artifacts), `STRONG` (structural shapes that
  survive paraphrasing), and `REVIEW` (density).
- It also reports signs of *human* writing, and says so when it finds none.
- It deliberately does not flag the guide's ineffective indicators: perfect grammar, formal
  register, hedging, transition words, the Oxford comma. Tests assert that it never will.
- New `ai-tells.md` reference, including the guide's own warning that treating the signs as the
  problem "could just make detection harder."
- Every skill that drafts prose now runs the check before handing anything over.
- Blockquotes are never linted, and a file can declare `<!-- prose-check: reference -->`.

## 0.3.0

Syllabus skill rebuilt around what the courses actually do.

- Treats the live LMS page as the source of truth, with a drift check before editing and a
  verify step after writing.
- Adds auditing the syllabus against the live course, term rollover, a syllabus quiz that
  targets `upload_quiz.py`, and keeping the companion overview deck in sync.
- New shared `house-style.md`, referenced by every drafting skill.

## 0.2.1

- Trimmed the `canvas` skill description under the 1024-character limit that the plugin loader
  enforces. Also trimmed `student-questions`, which had 17 characters of headroom.

## 0.2.0

Merged the standalone `canvas-lms-skill` (v0.7.0) into the plugin.

- `canvas.py` becomes the general Canvas client; `canvas_api.py` is the curated layer on top;
  `canvas_common.py` holds the write gate, CSV loading, and one roster-matching function.
- Adds `sync_grades.py`, `mark_late.py`, `late_penalties.py`, `rubric.py`, `upload_quiz.py`,
  `groups.py`, `download_submissions.py`, `cache_pages.py`, and 13 Canvas reference documents.
- Every writing wrapper now goes through the two-switch gate and logs before-values.
- New `course-reports` skill for end-of-term grades and at-risk reporting.
- Student data at rest is now a plugin-level concern, with the FERPA and GDPR framing and an
  automatic gitignore requirement.

**Fixed in the port:**

- `late_penalties.py` spent late-day budget on ungraded and excused submissions, and unsubmitted
  work sorted first, so a student with one unsubmitted assignment lost their whole allowance.
  This silently changed grades.
- `FileNotFoundError` in `late_penalties.py` and `groups.py` produced a traceback instead of the
  JSON error every other path emits.
- `cache_pages.py` wrote without an explicit encoding, failing on non-ASCII page bodies under a
  C or POSIX locale.
- `canvas.py` had no request timeout, so a hung connection blocked forever.
- A 429 was only retried when its body contained the string "Rate Limit".
- `explain_http` reported a rate-limited 403 as a permissions error.
- The 403-versus-404 guidance was corrected: Canvas returns **404** for objects a token may not
  see, which is what `permissions.md` exists to prevent people misdiagnosing.

## 0.1.0

First version. One folder per course, shared course knowledge under `.infra`, and skills for
course setup, syllabi, assignments, student questions, grading, and class communication across
Canvas, Piazza, and Gradescope.

---

## Known gaps

Stated plainly, because a scope claim that is quietly false is worse than an absent feature.

- **Gradescope cannot be written to.** No maintained client implements score writing, Gradescope
  documents no import path, and its data model computes scores from rubric selections rather than
  point values. Grades go to Canvas.
- **The Canvas tests use a mock server.** It is not Canvas, and it cannot catch Canvas changing
  its own semantics.
- **Verified against Canvas Cloud only**, at roughly 15 to 200 students.
- **No end-to-end test of the write paths.** The gate and the audit log are tested; an actual
  grade landing in an actual gradebook is not.
- **Piazza and Gradescope are scraped**, so both break when those sites change. Gradescope fails
  loudly by design; Piazza depends on an unofficial client.
- **The course-reports skill has no script, deliberately.** Weighting and letter bands are
  course-specific, so it is a documented workflow, which also means it has no tests.
