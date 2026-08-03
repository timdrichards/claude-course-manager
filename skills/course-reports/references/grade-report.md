# End-of-term grade report

A course-wide grade computation and audit: pull the whole gradebook, apply the
assignment-group weights, map each student to a letter grade, and surface the
things that bite at submission time — ungraded work, boundary cases,
missing/excused confusion, and weights that don't add up. Produces an HTML
report plus a JSON snapshot.

This reads the full roster's grades — **real student records. Read "Writing
student data to disk" in `SKILL.md` and "Student data on disk" in the plugin
README before writing the first snapshot, and follow them every time.** The
output lives under `.canvas-cache/<course_id>/reports/` alongside the activity
report, and must never be uploaded or emailed without an explicit request.

Like `activity-report.md`, this is driven directly by `canvas.py` calls plus
computation — there's no dedicated script, because the weighting and letter
bands are course-specific and belong in the report logic.

## Trust Canvas's totals, but recompute to audit

Canvas already computes a weighted `current_score`/`final_score` per enrollment
when the course has weighted groups. Pull those as the **source of truth**, and
independently recompute from raw scores to **catch discrepancies** — a mismatch
usually means an ungraded assignment, a wrong group weight, or an excused item
skewing a group. Report both and flag where they diverge.

## Data pull (once)

1. **Course settings — is the course weighted, and by what?**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /courses/:course \
       --param "include[]=total_scores" --param "include[]=current_grading_period_scores"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
       get /courses/:course/assignment_groups --all --param "include[]=assignments"
   ```
   Read `apply_assignment_group_weights` on the course and `group_weight` on
   each group. If weighting is off, the course is points-based — sum points
   instead of weighting groups, and say so in the report. Note any group
   `rules` (`drop_lowest`, `drop_highest`, `never_drop`): Canvas applies them
   and a recompute that ignores them will disagree for exactly the students the
   rule helped.

2. **Enrollment-level grades (Canvas's own totals):**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
       get /courses/:course/enrollments --all \
       --param "type[]=StudentEnrollment" --param "include[]=email"
   ```
   Per enrollment: `grades.current_score` (graded work only),
   `grades.final_score` (ungraded counted as 0), and the `unposted_*` variants
   that include hidden grades. Choose deliberately — see below. Filter out
   `StudentViewEnrollment` (canvas skill's `gotchas.md` #8).

3. **Every score, for the recompute + audit** — one GraphQL query (see the
   canvas skill's `submissions-grades.md`, "Bulk reads: prefer GraphQL"):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 graphql '
   query ($courseId: ID!, $cursor: String) {
     course(id: $courseId) {
       submissionsConnection(first: 100, after: $cursor) {
         pageInfo { hasNextPage endCursor }
         nodes { score grade state late missing excused
                 assignment { _id name pointsPossible omitFromFinalGrade
                              assignmentGroup { _id name groupWeight } }
                 user { _id name email } } } } }' --vars '{"courseId": "123456"}'
   ```
   Page with `after: endCursor`. This gives per-student, per-assignment scores
   grouped by assignment group — everything the recompute needs. `--vars` takes
   the numeric course id; `:course` is not substituted inside GraphQL variables.

## Computing the grade

**Weighted courses** (`apply_assignment_group_weights: true`):

1. Within each group, `group_pct = Σ(earned points) / Σ(points_possible)` over
   that student's **graded, non-excused, non-omitted** assignments in the group.
   - Exclude `excused` submissions from *both* numerator and denominator (an
     excused item shrinks the group, it isn't a zero).
   - Exclude assignments with `omit_from_final_grade: true`.
   - For a **final** grade, count still-ungraded/`missing` as 0 (include in the
     denominator) — **but read the carve-out below before treating `missing` as
     a zero.** For a **current** grade, exclude ungraded entirely. State which
     one the report uses.
2. `course_score = Σ(group_pct × group_weight)`, then normalize by the sum of
   the weights of groups that actually have gradeable work (so a group with no
   graded assignments yet doesn't silently count as 0% mid-semester).

**Points-based courses:** `course_score = Σ(earned) / Σ(points_possible)` over
gradeable assignments — no group weighting.

Match your recompute to Canvas's `current`/`final` choice; if they still differ
by more than a rounding epsilon, list the assignment(s) responsible.

### The `missing: true` carve-out

`missing` means *Canvas* believes nothing was submitted. It does **not** mean
the student did no work. Canvas sets it for any assignment past its due date
with no Canvas submission attached, which includes every assignment the course
collects somewhere else — Gradescope, a paper handin, an autograder, an
external tool.

So the rule "count `missing` as 0 for a final grade" holds only where Canvas is
the actual submission channel. In a Gradescope-centric course, applying it
verbatim zeroes out real work for the entire class.

Before treating any `missing` as a zero, check the assignment's
`submission_types`:

- `online_upload`, `online_text_entry`, `online_url`, `online_quiz`,
  `discussion_topic` — Canvas is the channel. `missing` with no `score` means
  nothing was turned in, and zero is right for a final grade.
- `on_paper`, `none`, `external_tool` — Canvas never saw a submission and never
  will. `missing` says nothing. Use the presence of a `score` instead: graded
  means submitted, ungraded means nobody has entered it yet, and *that* is what
  the report should flag.

An imported score is the strongest signal available: a submission with a
`score` and `missing: true` was submitted somewhere else and graded. Never zero
one of those. When the two signals conflict for a whole assignment — many
students with scores and `missing: true` — say so in the report and treat the
assignment as externally collected rather than deciding student by student.

## Letter grades

Apply the course's scheme, and read it rather than assuming it. If Canvas has a
grading standard attached (`grading_standard_id` on the course), read it and
use its bands verbatim:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/grading_standards --all
```

That is the preferred source, because it is the scale Canvas itself will show
the student. With no standard attached, confirm the exact bands with the user
or read them from the syllabus — the boundary rounding rule matters as much as
the numbers. Schemes vary widely by institution, department, and country; the
plus/minus scale below is one common US mapping, shown only to make the table
shape concrete, never as a default to fall back on silently:

| A | A− | B+ | B | B− | C+ | C | C− | D+ | D | F |
|---|----|----|---|----|----|---|----|----|---|---|
| ≥93 | ≥90 | ≥87 | ≥83 | ≥80 | ≥77 | ≥73 | ≥70 | ≥67 | ≥60 | <60 |

Whichever source was used, name it in the report header.

## Audit checks (the point of the report)

Flag every one of these, per student where relevant:

- **Ungraded work remaining** — submissions in `submitted`/`pending_review`
  state; the grade isn't final until these are done. Count per assignment, and
  count both states: `pending_review` is where quiz essays sit.
- **Current vs final gap** — students with many missing assignments have a
  large `current − final` gap; list them, since "current" flatters them.
- **Boundary cases** — students within ~1 point below a letter boundary. These
  are the rounding/appeal conversations; surface them early.
- **Missing vs excused** — assignments marked `missing` (see the carve-out
  above) vs `excused` (dropped). A wrongly-excused item silently raises a
  grade; a should-be-excused `missing` wrongly lowers it.
- **Externally collected assignments** — any assignment where `missing` is
  widespread but scores exist. Name it, and say how the report treated it.
- **Weight sanity** — group weights don't sum to 100 (with weighting on), or a
  weighted group has zero gradeable assignments.
- **Recompute mismatch** — where your independent total disagrees with
  Canvas's, with the likely cause.

## Report structure

A single self-contained `<!doctype html>` document, inline-styled, hand-authored
inline `<svg>` for any chart (same conventions as `activity-report.md` — no
libraries, no build step). Sections:

1. **Header** — course name/id, generated-at (local + UTC), weighting mode,
   current-vs-final basis used, letter scheme (and its source), and any
   overrides.
2. **Summary strip** — student count, grade distribution (A/B/C/D/F counts),
   count with ungraded work outstanding, count of boundary cases, and total
   audit flags.
3. **Grade distribution chart** (inline SVG) — bar per letter grade.
4. **Roster table** — Name, Email, Current %, Final %, Letter, Missing count,
   Ungraded count, and audit badges ("2 ungraded", "0.4 below B+", "weight
   mismatch").
5. **Audit section** — each check above with the students it caught, so it
   reads as a to-do list before you submit final grades.
6. **Methodology** — exact formula used, excluded assignments (omitted/
   excused), how `missing` was treated and why, the current-vs-final choice,
   and the snapshot path.

## Snapshot cache

Path and handling mirror `activity-report.md` exactly:
`./.canvas-cache/<course_id>/reports/<compact-ISO-timestamp>-grades.{json,html}`.
Compact (no-colon) timestamps so they sort chronologically and pair by
basename. The `.json` carries per-student `{user_id, name, email, current,
final, letter, missing_count, ungraded_count, flags[]}` so a later run can diff
against it ("3 students moved down a letter since last week").

**This snapshot is a student record.** The `.gitignore` check applies before
the first one is written; never transmit it anywhere without an explicit
request.
