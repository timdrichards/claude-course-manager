# Gradescope → Canvas grade sync

Push scores from a CSV into a Canvas assignment — matching each row to a
student, previewing, then bulk-writing. `scripts/sync_grades.py` does the match
and the write; this file explains the workflow and the edge cases.

Gradescope is the worked example throughout because its export is the common
case and its column names are what the script autodetects, but nothing here is
Gradescope-specific: any CSV with a score column and an email or student-id
column works, whatever produced it (another autograder, a TA's spreadsheet, a
scanned-exam tool). Point the `--score-column` / `--email-column` /
`--sid-column` flags at whatever your file calls them.

Gradescope is read-only in this plugin, which is exactly why this exists:
scores computed there have to be carried to Canvas, and Canvas is where grades
live.

## The workflow

1. **Have the Canvas assignment ready.** The sync writes to an existing
   assignment id — create it first if needed (`assignments.md`), and set its
   `points_possible` to the Gradescope max so the raw score maps cleanly. The
   script warns if the two maxes disagree.
2. **Export from Gradescope.** In the Gradescope assignment: *Review Grades →
   Download Grades → CSV*. That per-assignment export has `Name`, `SID`,
   `Email`, `Total Score`, `Max Points`, `Status`, and per-question columns.
3. **Preview the match.** A run without `--live` is the preview:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_grades.py hw3_scores.csv \
       --course 326 --assignment-id 678
   ```
   Read the report: `matched` (with how each was matched), `skipped` (empty
   scores), `unmatched_csv_rows` (in Gradescope, not on the Canvas roster), and
   `canvas_students_without_a_csv_row` (on Canvas, never graded in Gradescope).
4. **Confirm, then apply.** Add `--live`. The post is Canvas's asynchronous
   bulk-grade endpoint; the summary includes a `progress` url — poll
   `GET /progress/<id>` until `workflow_state: completed`. The command
   returning is not proof the grades landed.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_grades.py hw3_scores.csv \
    --course 326 --assignment-id 678 --live
```

Before posting, the script reads every current submission score. That read is
what makes the write reversible — the old scores go into the course's
`actions.log` as the `before` value — and it is also how the preview can tell
you how many students already have a score and are about to be overwritten. An
unexpected overwrite count means the batch is being applied twice or the wrong
assignment id was used.

## Marking late submissions (submission time vs. the Canvas due date)

`sync_grades.py` posts the raw autograder score and stops there — it does not
look at *when* the student submitted. Canvas can't infer lateness on its own
either: the student submitted on Gradescope, not through Canvas, so Canvas has
no `submitted_at` to compare against the due date. The score lands looking
perfectly on-time no matter when it was actually turned in.

`scripts/mark_late.py` closes that gap. It reads each row's **Submission Time**
from the same Gradescope CSV, compares it to that student's *effective* Canvas
due date, and marks the genuinely-late ones — accommodation-aware, and aligned
to your syllabus. Run it **after** `sync_grades.py` (the deduction Canvas
applies is a percentage of the posted score, so the score must be in first):

```bash
# Preview. --per-day/--max-days/--after-max come from your syllabus.
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/mark_late.py hw3_scores.csv --course 326 \
    --assignment-id 678 --per-day 10 --max-days 2 --after-max zero

# Apply after reading the plan
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/mark_late.py hw3_scores.csv --course 326 \
    --assignment-id 678 --per-day 10 --max-days 2 --after-max zero --live
```

This is a distinct capability with its own rules (effective due dates,
accommodations, the syllabus late policy, and how Canvas's built-in policy does
the actual deduction). **Read `late-policy.md` before running it** — that file
is the source of truth for how marking, accommodations, and the Canvas-policy
check fit together. Two things to line up first:

- The CSV must carry submission times. The **per-assignment** export (step 2)
  includes `Submission Time` and `Lateness (H:M:S)`; a whole-course gradebook
  export usually does not. `mark_late.py` prefers `Submission Time` vs. the
  Canvas due date and falls back to Gradescope's `Lateness` column.
- Canvas's course-level late policy (Gradebook → Settings) must be enabled and
  set to your syllabus rate, or marking a submission "late" deducts nothing.
  `mark_late.py` reads it and warns; `late-policy.md` covers verifying and
  setting it against the syllabus.

## Matching

Per row, in order: the column you named → email → SID (vs Canvas
`sis_user_id`) → login id. Never by name (`students-enrollments.md`). Email is
the most reliable for Gradescope because students sign in with their campus
email. The roster is read once via `/courses/:course/users --include email`.

Autodetected columns (override with flags): score = `Total Score` then
`Score`; email = `Email` then `Email Address`; SID = `SID`, `Student ID`, then
`Student SID`. Override when the export is non-standard:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_grades.py grades.csv --course 326 \
    --assignment-id 678 --score-column "Assignment 3" --email-column "Email Address"
```

Ambiguity is never guessed, but it doesn't halt the search either. A key that
matches **more than one** Canvas user is skipped and matching continues with
the next key — so a row whose email is shared by two students (a family
address) still resolves cleanly when its SID identifies exactly one of them.
Every key carries its own duplicate check, the SID included.

Only a row that no unambiguous key resolves lands in `unmatched_csv_rows`, and
its `reason` names what went wrong: `ambiguous_email`, `ambiguous_sid`,
`ambiguous_email_and_sid`, or `no_match`. Nothing is ever posted to a
maybe-right student.

`mark_late.py` uses the same matching function from `canvas_common.py`, so both
halves of an import agree on who each row is by construction rather than by two
copies being kept in step.

## Empty scores and missing submissions

A row with a blank score (a student who never submitted, Gradescope `Status:
Missing`) is **skipped and reported** by default — the sync won't silently
turn "didn't submit" into a real zero. To post zeros for them instead:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_grades.py grades.csv --course 326 \
    --assignment-id 678 --missing-zero --live
```

Decide deliberately: posting a 0 is student-visible and affects the current
grade immediately; skipping leaves the Canvas cell ungraded (which Canvas
treats as 0 only in *final* score, not *current*). See
`submissions-grades.md`'s "Enrollment-level grades" note.

## Gotchas

- **Raw points, not percent.** Gradescope `Total Score` is points; it's posted
  as Canvas points. If the Canvas assignment's `points_possible` differs from
  the Gradescope max, the number still posts literally — the script warns, but
  it can't know which max you meant. Fix the assignment, don't rescale by hand.
- **Regrades overwrite.** Re-running the sync re-posts every matched score,
  overwriting any manual Canvas edits for those students. If you hand-adjusted
  a grade in Canvas after the last sync, a re-sync will clobber it.
- **Whole course export.** A Gradescope *gradebook* export (one row per
  student, one column per assignment) also works — point `--score-column` at
  the assignment's column. But per-assignment exports are cleaner here.
- **SIS-managed emails.** If `email` is permission-gated on your token (see
  `permissions.md`), matching falls back to SIS id / login id; make sure the
  CSV carries a `SID` column in that case.
- **Manual posting policy.** If the assignment posts grades manually
  (`post_manually`), synced grades stay hidden until posted — see
  `submissions-grades.md`, "Posting policy." "I synced the grades" and
  "students can see their grades" are two different claims.
- **The CSV is student data.** A Gradescope export sitting in the project
  folder is a roster with grades attached. See "Student data on disk" in the
  plugin README.
