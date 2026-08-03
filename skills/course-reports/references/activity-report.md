# Student activity report

One combined capability producing three outputs from a single data pull: a
student activity/status report (engagement, missing work, grade trends, an
explicit "students of concern" list with emails), a daily todo list, and an
instructor todo list for a planning window ("week," "weekend," or an explicit
N days).

This reads a lot of student data into a local file — read "Writing student data
to disk" in `SKILL.md` and "Student data on disk" in the plugin README before
running it, and follow them every time, not just the first.

## Parsing the request

Two independent windows. Both get stated explicitly in the report header —
never leave the reader to guess what "recent" meant.

| Input phrase | Resolves to |
|---|---|
| "past 24 hours" / "last 3 days" / no window given | `report_window`: `[now - N, now]`. Default `N = 7` days if the user gives no lookback at all. |
| "week" | `planning_window`: today through `today + 7 days` |
| "weekend" | the *next* occurring Saturday–Sunday: if today is Mon–Fri, the coming Sat 00:00–Sun 23:59; if today is already Sat or Sun, this weekend (today through Sunday 23:59) |
| "next N days" / an explicit number | `planning_window`: today through `today + N days` |
| unstated | `planning_window` defaults to 1 day (daily todo only) — say so explicitly in the report rather than silently omitting the N-day section |

Compute both windows in the instructor's local timezone first, then convert to
explicit-offset ISO 8601. Canvas returns UTC, and computing "N days ago"
straight off those raw timestamps can silently include or exclude an extra day
near midnight. Prefer an IANA zone name over a fixed offset so the arithmetic
stays right across a daylight-saving boundary.

## Data pull

Five calls total. Do this pull once per report; every derived section below
(report, both todos) reads from the same pulled data rather than re-fetching.

1. **Roster + activity + grades, one call:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
       get /courses/:course/enrollments --all \
       --param "type[]=StudentEnrollment" --param "include[]=email"
   ```
   Pull `last_activity_at`, `total_activity_time`, and `grades.current_score`/
   `final_score`/`unposted_current_score` per enrollment (see the canvas
   skill's `students-enrollments.md`). Filter out `StudentViewEnrollment`
   (`gotchas.md` #8).

2. **Submissions, bulk, via GraphQL** (see the canvas skill's
   `submissions-grades.md`, "Bulk reads: prefer GraphQL" for the full query and
   pagination). Page through all results; this gives `late`/`missing`/`state`/
   `submittedAt` per submission across the whole course in a handful of round
   trips, plus each submission's assignment due date.

3. **Assignments, one call:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
       get /courses/:course/assignments --all --param "include[]=all_dates"
   ```
   Filter client-side for both todos (due-soon + unpublished, ungraded
   backlog) rather than making separate `bucket=` calls — one fetch, several
   derived views.

4. **Calendar events in the planning window:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
       get /calendar_events --all \
       --param "context_codes[]=course_123456" \
       --param "start_date=<planning_window.start>" \
       --param "end_date=<planning_window.end>" \
       --param "type=event"
   ```
   **Interpolate the actual course id yourself** — see the canvas skill's
   `gotchas.md` #16; `context_codes[]=course_:course` is sent literally and
   silently returns nothing. The id is `course_id` in the course's
   `.infra/canvas/config.json`, and `canvas_api.py --course 326 whoami` prints
   it.

5. **Optional, capped enrichment — not for the whole roster:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
       get /courses/:course/analytics/users/<student_id>/activity
   ```
   Per-student page-view/participation timeline. Use only for students
   already flagged at-risk by steps 1–2 (cap around 15 students) — never loop
   this over the full class (`gotchas.md` #12: prefer bulk endpoints over
   per-object loops). The bulk, course-wide
   `/courses/:course/analytics/student_summaries` endpoint is a secondary,
   corroborating signal only — its counts are lifetime-in-course totals, not
   time-windowed, so it can't substitute for `last_activity_at`.

**One-time schema check** (mirrors the canvas skill's "check once per Canvas
instance" pattern): before relying on `user.email` in the GraphQL query, run
`graphql 'query { __type(name: "User") { fields { name } } }'` once and confirm
`email` is listed and actually returns non-null values. If it's unavailable or
permission-gated, cross-reference by `user._id` against the email map built
from call #1 instead.

## Default at-risk thresholds

Each is overridable per-run by explicit instructor request; note in the
report's methodology section whichever ones were overridden.

| Signal | Default | Source |
|---|---|---|
| Inactivity | no activity in **5+ days** (`now - last_activity_at`) | enrollments call |
| Missing work | **2+** submissions with `missing: true` | GraphQL submissions |
| Grade drop | `current_score` down **10+ points** vs. the immediately previous cached snapshot (only computable if a prior snapshot exists) | snapshot diff |
| Low absolute grade (context only, non-triggering) | `current_score < 60` — noted on the at-risk row for context, never itself a flag reason unless combined with one of the above | enrollments call |

A student is "of concern" if **any** threshold trips. List every reason that
fired for them — never collapse to just one.

**A caution on the missing-work threshold in a course that collects work
elsewhere.** Canvas marks a submission `missing` whenever its due date has
passed with no Canvas submission attached, which is true of every assignment
handed in through Gradescope or on paper. Where that is the course's normal
channel, `missing` counts are noise and the threshold will flag the entire
roster. Check `submission_types` on the assignments involved and use the
absence of a `score` instead — the reasoning is worked through in
`grade-report.md`'s "`missing: true` carve-out". Say in the methodology section
which signal the run actually used.

## Daily todo

- **Grading backlog aging**: submissions with `state == "submitted"` (turned
  in, ungraded) where `now - submittedAt > 48h`, grouped by assignment, with
  counts and the oldest age. Count `pending_review` too — quiz essays sit
  there and are just as ungraded.
- **Due today/tomorrow and unpublished**: assignments with `due_at` in
  `[now, now+48h]` and `published == false`.
- **Newly at-risk today**: diff this run's at-risk set against the most
  recent prior snapshot's at-risk set (see "Local snapshot cache" below).
  Name them explicitly. If no prior snapshot exists, say so explicitly
  rather than silently treating everyone currently at-risk as "new."

## Next-N-days todo (planning window)

- **Upcoming due dates with setup gaps**: assignments with `due_at` inside
  the planning window where `published == false`, or the description is
  empty/whitespace-only.
- **Grading-backlog projection**: count of currently `unsubmitted` +
  `submitted`-but-ungraded submissions for assignments whose `due_at` falls
  before the planning window ends — what will need grading attention by the
  end of this window even before new submissions arrive.
- **Calendar items**: everything from the `/calendar_events` pull, listed as
  title + start/end.

## Report structure

A single, self-contained `<!doctype html>` document — inline `style="..."`
throughout (not required here the way it is for Canvas pages, since this never
touches Canvas, but kept anyway for zero-dependency portability and consistency
with the rest of this plugin). Charts are hand-authored inline `<svg>`
(`<rect>`/`<text>`/`<line>` elements) — no charting library, no build step.
Section order:

1. **Header** — course name/id, generated-at (local + UTC), report window,
   planning window, and which thresholds (if any) were overridden.
2. **Executive summary strip** — total students; active/inactive counts in
   the window; total missing/late/ungraded; count of students of concern,
   with a delta vs. the last snapshot ("+2 since last report on <date>," or
   "no prior snapshot found" on the first run).
3. **Students of Concern table** — Name, Email, Reasons (short badges, e.g.
   "Inactive 6d," "Missing ×3," "Grade ↓12pts"), Last Activity (date + "N
   days ago"), Current Score, Missing Count, Trend arrow vs. previous
   snapshot (↑/↓/flat/new).
4. **Engagement chart** (inline SVG) — horizontal bars, students bucketed by
   days-since-last-activity (0–1 / 2–3 / 4–6 / 7+).
5. **Submission status chart** (inline SVG) — one stacked horizontal bar per
   assignment due within the report window (on-time/late/missing/ungraded
   segments).
6. **Grade trend** (inline SVG) — current-score distribution this run vs.
   the previous snapshot's distribution, side by side.
7. **Today's Todo** — checklist, each item backed by the concrete Canvas
   fact behind it (assignment name, id/html_url, count).
8. **Next-N-Days Todo** — same checklist shape, grouped by the three
   derivation categories above.
9. **Methodology / appendix** — thresholds actually used, exact window
   boundaries, which snapshot was used as the diff baseline (path/timestamp,
   or "none"), and a note if per-student Analytics enrichment (step 5) was
   used and for how many students.

## Local snapshot cache

Path: `./.canvas-cache/<course_id>/reports/<compact-ISO-timestamp>-report.{json,html}`
— same basename for the pair (e.g. `20260707T140000Z-report.json` /
`.html`), so they're trivially found together. Use compact (no-colon)
timestamps since `:` is unsafe in filenames.

**This cache is a student record** — the `.gitignore` check applies before the
first one is written.

`.json` schema:

```json
{
  "course_id": "123456",
  "generated_at": "2026-07-07T18:00:00Z",
  "report_window": {"start": "2026-07-04T18:00:00Z", "end": "2026-07-07T18:00:00Z"},
  "planning_window": {"kind": "week", "n_days": 7, "start": "2026-07-07", "end": "2026-07-14"},
  "thresholds": {"inactivity_days": 5, "missing_count": 2, "grade_drop_points": 10, "overridden": []},
  "previous_snapshot": "20260630T140000Z-report.json",
  "students": [
    {
      "user_id": 11111,
      "name": "...",
      "email": "...",
      "last_activity_at": "...",
      "current_score": 82.5,
      "missing_count": 2,
      "at_risk": true,
      "reasons": ["missing_2plus", "inactive_6d"]
    }
  ]
}
```

**Finding the previous snapshot**: no index file — list
`./.canvas-cache/<course_id>/reports/*-report.json`, sort lexically (compact
ISO sorts chronologically), and take the entry immediately before the current
run. Record which one was used in `previous_snapshot` for traceability; if none
exists, record `null` and say so in the report.

**No script for this.** Unlike page caching (`cache_pages.py`), which earns its
own script because it's a genuinely bulk, repeated, mechanical operation across
many pages, a report snapshot is one JSON object, written once per run, already
fully computed in-context. Read prior snapshots with the Read tool (list + sort
by filename), compute the diff directly, and write the new snapshot + HTML
report with the Write tool.

## Opening the report

No script needed — the HTML authored here already *is* the complete, final,
standalone document (not a fragment needing a wrapper). Try `open <path>`
(macOS), fall back to `xdg-open <path>` (Linux) if `open` isn't found, and if
neither exists, print the absolute path and tell the user to open it manually.

## What this report is not

It flags; it does not decide. Nothing here contacts a student, files an
academic concern, or writes to Canvas. When the user wants to act on the list —
a check-in message, a nudge about missing work — that is the course-comms
skill, and an individual student's circumstances are theirs to weigh.
