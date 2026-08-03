# Changelog

All notable changes to this plugin are recorded here.

**What counts as the public interface**, and therefore what a version bump is about: skill names
and their trigger descriptions, script names and their command-line flags, the JSON shapes those
scripts read and write, the reference file names a skill links to, and the documented safety
rules. Prose improvements inside a reference are not a version bump. Renaming a flag is.

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
