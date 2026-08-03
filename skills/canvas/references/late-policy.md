# Late policy automation

Three related jobs live here:

1. **Mark late Gradescope imports** — decide which imported submissions are
   actually late (submission time vs. the Canvas due date), accommodation-aware,
   and mark them so Canvas's built-in policy deducts. `scripts/mark_late.py`.
   This is the piece that pairs with the Gradescope import (`grade-sync.md`).
2. **Verify Canvas's built-in late policy matches the syllabus** — so that
   "marked late" actually deducts the rate the syllabus promises. A
   read-compare-set flow over `/courses/:course/late_policy` (below).
3. **Apply your own after-the-fact penalty** — a flat percent-per-day or a
   semester late-day budget, computed and posted with an audit comment.
   `scripts/late_penalties.py`.

Jobs 1+2 are the usual pairing for a Gradescope course: the import marks
lateness, Canvas's own policy does the deduction. Job 3 is for when you want the
script itself to own the deduction (a late-day budget Canvas can't express, or a
penalty applied after grading with the built-in policy off).

## Align the policy with the syllabus first

Every number below — the per-day rate, how many late days are allowed, whether
late work is capped then zeroed — comes from the **syllabus**, not from a
default. Find it before touching grades:

- **The course folder first.** `.infra/course-profile.md` and whatever syllabus
  the course keeps (the syllabus skill writes one). Read the actual late-work
  language.
- **Else Canvas.** `canvas.py --course 326 get /courses/:course --param
  "include[]=syllabus_body"` for the syllabus page, or a wiki page named
  syllabus (`pages.md`).

Read the late-work paragraph and extract: the **rate** (% per day), the **unit**
(per day vs. per hour), the **cap** (how many late days are accepted), and what
happens **after** the cap (typically scored zero / not accepted). State the
values you extracted back to the user and confirm them — late-work wording is
often ambiguous and this drives real deductions. A common CS pattern: *"late up
to two days at 10%/day, then not accepted (zero)."*

### Check and set Canvas's built-in late policy

Canvas has a course-level late policy (Gradebook → Settings → Late Policies)
that auto-deducts as grades are entered. `mark_late.py` relies on it for the
deduction, so it must be **enabled** and match the syllabus rate.

```bash
# Read the current policy
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/late_policy

# Set it to the syllabus rate (10%/day, floored at 50%). Confirm with the user
# first — this changes how every late grade in the course is computed.
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/late_policy --json '{
  "late_policy": {
    "late_submission_deduction_enabled": true,
    "late_submission_deduction": 10.0,
    "late_submission_interval": "day",
    "late_submission_minimum_percent_enabled": true,
    "late_submission_minimum_percent": 50.0
  }
}' --live
```

`POST` creates the policy; updating an existing one is a PATCH, which
`canvas.py` does not expose as a subcommand. If `POST` returns an
"already exists" error, make the change in the Canvas gradebook UI and say so
rather than improvising — this is a course-wide grading setting. Compare each
field to the syllabus and report mismatches before changing anything (Safety
Rule 1).

**What Canvas's policy cannot express:** a hard cap like *"accepted for only 2
days, then zero."* Canvas keeps deducting the per-day rate down to
`late_submission_minimum_percent` and no further — it never zeroes at a day
boundary. So the floor is *not* the same as the syllabus's zero. `mark_late.py`
handles the cap itself (`--after-max zero`); Canvas handles the per-day slope up
to the cap. Tell the user this explicitly so the two policies aren't assumed to
be equivalent.

## Marking late Gradescope imports (`mark_late.py`)

The workflow companion to `sync_grades.py`. After the scores are posted, this
computes lateness and marks it. Read `grade-sync.md` for where it sits in the
import; this section is the rules it applies.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/mark_late.py hw3_scores.csv --course 326 \
    --assignment-id 678 --per-day 10 --max-days 2 --after-max zero
```

**Effective due date, per student.** Lateness is measured against the deadline
that student is actually entitled to, not just the base date — the latest of:
the assignment's base `due_at`, a Canvas per-student override
(`cached_due_date`, read live), or a recorded accommodation (below). Submission
time comes from the CSV `Submission Time` column (falling back to Gradescope's
`Lateness`). `--grace-minutes` and `--tz` tune the comparison; part-days round
**up** to whole late days.

`--tz` sets the timezone for *naive* timestamps (ones carrying no offset) and
defaults to the machine's current UTC offset. It accepts either an offset
(`-04:00`) or an IANA zone (`America/New_York`, `Europe/London`,
`Asia/Kolkata`). **Prefer the IANA zone**: a fixed offset is applied uniformly,
so submissions on the other side of a daylight-saving change land an hour off.
Most exports (including Gradescope's) already carry an offset, in which case
this setting never applies. Do not hardcode an offset for a course you are not
sitting in; a default of `-04:00` once produced silently wrong late marks for
everyone outside US Eastern, which is why the default is now derived from the
host machine.

**How a submission is marked.** For a late, un-accommodated submission within
the cap, the script sets `late_policy_status: "late"` and
`seconds_late_override` on the Canvas submission (one PUT per student — Canvas
has no bulk endpoint for late status). It does **not** touch the score; Canvas's
enabled policy applies the deduction to the posted score. Over the cap with
`--after-max zero`, it posts `0` with an explaining comment (Canvas can't zero
at a day boundary). `--after-max accept` marks late with no cap; `--after-max
flag` (the default) routes over-cap submissions to review instead of acting.

**Accommodations are never auto-penalized.** A student counts as accommodated if
their effective deadline is extended (a Canvas override, or an
`--accommodations` entry) or they're marked exempt. If they submitted within
their extension they're simply on-time. If they're late *past* their extension,
or exempt, they go to the `needs_review` bucket — reported with their effective
deadline and lateness, but **left untouched** for you to handle individually
(Safety Rule 4). This is the deliberate "determine the appropriate action per
student" path: the script surfaces the facts and defers the judgment to a human.

**The `--accommodations` file** is a structured hand-off you assemble from the
sources that actually hold this information in the course folder — Canvas
overrides (which the script already reads on its own), and whatever the course
profile or a dedicated accommodations file records. Read those prose sources
yourself and distill them into the file; don't expect the script to parse prose.

```json
{
  "default_tz": "America/New_York",
  "students": [
    {"email": "a@example.edu", "type": "extension",  "due_at": "2026-07-26T23:59:00-04:00", "note": "accommodation: 48h"},
    {"sid":   "12345678",    "type": "extra_days",  "days": 2, "note": "accommodation: flexible deadlines"},
    {"email": "b@example.edu", "type": "exempt", "note": "religious observance"}
  ]
}
```

Rows are matched to Canvas users by email → SID → login id, exactly like the
grade sync; unresolvable rows are reported in `accommodations_unresolved`, never
guessed. `type`: `extension` (a specific new deadline), `extra_days` (base due +
N days), or `exempt` (→ `needs_review`, never auto-excused).

**An accommodations file is student data of the most sensitive kind.** It
records which students have accommodations, which is exactly the sort of thing
that must not reach version control or anyone who did not already know. Keep it
out of git and see "Student data on disk" in the plugin README.

**Idempotent.** Re-running after a regrade/resubmit that made a student on-time
clears a stale `late` status (sets it back to `none`). The script only touches
students present in the CSV and reports every change. Every batch it applies is
recorded in the course's `actions.log` with each student's prior late status,
score, and seconds-late override, so it can be reversed.

## Applying your own penalty (`late_penalties.py`)

Use `late_penalties.py` instead of jobs 1+2 when the script should own the
deduction: a semester late-day budget (which Canvas can't express), or a penalty
applied after the fact with the built-in policy off. It computes the deductions
from each submission's `late`/`seconds_late` and applies them as a bulk grade
update with a comment on each explaining the math. **Do not run both** the
built-in Canvas policy and `late_penalties.py` on the same assignment — they'd
double-deduct.

Reach for it specifically when you want a **late-day budget** (students get N
free late days across the term, penalties only after), a penalty applied
**after the fact** to already-graded work, or a **preview and audit trail** (a
per-student comment) before anything changes. Grades must already be entered —
the penalty adjusts the existing score. The script skips on-time, excused, and
ungraded submissions and reports them, and under the budget policy those also
spend no late days.

## Flat percent-per-day (one assignment)

```bash
# 10% of full marks per late day, capped at 5 days, 10-minute grace. Preview:
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/late_penalties.py apply --course 326 \
    --assignment-id 678 --per-day 10 --max-days 5 --grace-minutes 10

# Apply
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/late_penalties.py apply --course 326 \
    --assignment-id 678 --per-day 10 --max-days 5 --grace-minutes 10 --live
```

- Deduction is `days × per-day% × points_possible` — "10%/day" on a 50-pt
  assignment is −5 pts/day. `--floor` sets a minimum adjusted score (default 0).
- `days` rounds any part-day **up** after subtracting `--grace-minutes`; a
  submission inside the grace window is not penalized.
- The preview lists each `change` (old → new, days, points off) and the
  `untouched` count with reasons. Confirm before adding `--live`.

## Late-day budget (across assignments)

Each student gets `budget_days` late days for the term with no penalty; days
beyond the budget are charged at `per_day_after` percent. Configure with JSON:

```json
{
  "budget_days": 3,
  "per_day_after": 10,
  "grace_minutes": 10,
  "floor": 0,
  "assignments": [231, 245, 262]
}
```

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/late_penalties.py budget \
    --config late-budget.json --course 326
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/late_penalties.py budget \
    --config late-budget.json --course 326 --live
```

How the budget is spent: for each student, their submissions across the listed
assignments are ordered **chronologically by submission time**, and each late
submission draws from the remaining budget first; only the over-budget days are
penalized on that assignment. The preview shows a per-student ledger
(`late_days_used`, `budget_remaining`, and each penalty). Every penalized
submission gets a comment noting days used, days covered, and the adjustment.

Assumptions to be aware of and state to the user:
- **Order is by `submitted_at`, not by deadline.** For most courses these agree;
  they can differ if a student submits an earlier assignment late *after* a
  later one. If deadline order matters, run the assignments through separate
  `budget` invocations in the order you want them charged, or grade in that
  order.
- **The listed assignments define the budget scope.** Only assignments in the
  config consume or are charged against the budget. Add every assignment the
  policy covers.
- **Re-running re-applies from the current score.** The script reads the
  *current* Canvas score as the baseline, so running `budget` twice would
  penalize an already-penalized score. Apply the budget once per grading pass,
  or restore raw scores before re-running.

## Safety

Both subcommands are bulk, student-visible grade changes (Safety Rules 1 and 3):
run without `--live` first, show the user the changes, and confirm. Both use
Canvas's asynchronous bulk-grade endpoint and return a `progress` url per
assignment — poll `GET /progress/<id>` until `completed`. Penalized scores post
immediately unless the assignment uses manual posting (`submissions-grades.md`,
"Posting policy").

A late penalty is a grade change a student will ask about. Have the syllabus
language ready, and consider whether the batch needs an announcement
(course-comms) rather than arriving silently in the gradebook.
