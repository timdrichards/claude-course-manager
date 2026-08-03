# Submissions and Grades

Grade changes are student-visible (immediately, or on posting if the
assignment uses a manual posting policy). Confirm before writing, and remember
that the grading skill decides what the number should be — this file is only
how it gets into Canvas.

## Reading submissions

```bash
# One assignment, all students
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignments/<aid>/submissions --all \
    --param "include[]=user" --param "include[]=submission_comments"

# One student across many assignments (the workhorse for grade audits)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/students/submissions --all \
    --param "student_ids[]=11111" --param "assignment_ids[]=222" \
    --param "include[]=assignment"

# student_ids[]=all works for teachers and returns everyone
```

`canvas_api.py --course 326 submissions <assignment_id>` is the readable
one-assignment version of the first call, and prints a table instead of JSON.

Key submission fields: `workflow_state` (`unsubmitted`, `submitted`, `graded`,
`pending_review`), `score`, `grade`, `entered_score`, `entered_grade`, `late`,
`missing`, `excused`, `submitted_at`, `attempt`, `attachments` (uploaded files
with download urls), `seconds_late`, `cached_due_date`, `late_policy_status`.

`cached_due_date` is that student's **effective** due date — it already folds in
any per-student or section override, so it's the right field to compare a
submission time against without separately fetching overrides.
`late_policy_status` is `late`, `missing`, `extended`, `none`, or `null`.

### Score, grade, and entered_grade

Three fields that are not the same thing.

- `score` — the numeric points, after any late penalty Canvas applied.
- `grade` — the display string. For a points assignment it looks like the
  score; for a letter or percentage assignment it does not; for pass/fail it is
  `complete`/`incomplete`.
- `entered_score` / `entered_grade` — what was entered before Canvas deducted a
  late penalty.

When writing, `posted_grade` accepts points, a percentage like `"88%"`, a
letter grade, or `"pass"`/`"fail"`, and Canvas interprets it according to the
assignment's grading type. Sending a bare number to a letter-graded assignment
does something, but not necessarily what was meant. Check `grading_type` on the
assignment when the number matters.

When reading a gradebook to compute anything, use `score`. When showing a
student what they got, use `grade`.

The pair matters most when a late policy is in force: Canvas deducts from the
posted score, so `score` is what the student has and `entered_score` is what
the grader gave. Re-posting `score` as if it were the grade applies the
deduction a second time, which is how a 10%-per-day policy silently becomes
19%.

### Late, missing, and excused

These change what a score means, so read them before acting on one.

- `late: true` — submitted after the due date. Canvas may already have applied
  a late policy deduction, which is why `entered_score` and `score` can differ.
- `missing: true` — Canvas considers it not submitted. Often true for a student
  who submitted outside Canvas, so it is a flag to check rather than a fact to
  act on. In a Gradescope-centric course it is true of nearly everyone, and
  treating it as a zero is wrong; see the course-reports skill's
  `grade-report.md`.
- `excused: true` — excluded from the grade entirely. Setting a score on an
  excused submission is almost always a mistake; excusal is usually an
  accommodation someone granted deliberately.

### The grading queue

"How many are left to grade" means counting `submitted` **plus**
`pending_review`, not "total minus graded", since unsubmitted work is not
waiting on anyone. `pending_review` is where quiz essay questions and
rubric-pending items sit, so a queue filtered on `workflow_state=submitted`
alone undercounts, sometimes badly, in a course with quizzes.

The reliable way to count is to pull the submissions and bucket them
client-side:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/assignments/<aid>/submissions --all \
  | jq '[.[] | select(.workflow_state=="submitted" or .workflow_state=="pending_review")] | length'
```

Canvas does accept a server-side `workflow_state` filter on the submissions
endpoints, but it takes one state at a time; whether repeating the param unions
the states is not something these docs verified, so prefer the client-side
bucket or make one call per state and add them.

### Marking a submission late (when Canvas didn't see it submitted)

Canvas only computes lateness for work submitted *through Canvas*. For grades
imported from Gradescope (no Canvas `submitted_at`), set the status yourself so
the course late policy can deduct:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/assignments/<aid>/submissions/<user_id> --json '{
  "submission": {"late_policy_status": "late", "seconds_late_override": 90000}
}' --live
```

`seconds_late_override` is what Canvas's built-in late policy uses to compute the
deduction (days = ceil(seconds / interval)); set `late_policy_status: "late"`
*without* it and Canvas sees 0 seconds late and deducts nothing. Set
`late_policy_status: "none"` to clear a stale late mark. Doing this across a
Gradescope import — submission-time analysis, accommodations, and the syllabus
cap — is automated by `scripts/mark_late.py`; see `late-policy.md`.

## Grading

```bash
# Score one submission, with a comment
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/assignments/<aid>/submissions/<user_id> --json '{
  "submission": {"posted_grade": "47"},
  "comment": {"text_comment": "Good decomposition; see inline notes on error handling."}
}' --live

# Excuse a student
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/assignments/<aid>/submissions/<user_id> \
    --json '{"submission": {"excuse": true}}' --live
```

For ordinary grading prefer the curated commands, which read the current scores
first and print `was -> will be` per student before anything is sent:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 \
    set-grade <aid> --user <canvas_user_id> --score 17 --comment-file feedback.md --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 \
    set-grades <aid> --file grades.json --live
```

Comments post as submission comments and the student sees them. Write them as
the instructor would; a comment is feedback, not a log line.

### Grading through a rubric

When an assignment has a `use_for_grading` rubric, grade by criterion instead
of setting `posted_grade` — Canvas sums the criteria into the score. Do not
also set `posted_grade`; the two sources fight. `rubric.py grade` applies
per-criterion scores/comments across a roster by criterion name; see
`canvas-rubrics.md`.

### Bulk grading (one request, asynchronous)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/assignments/<aid>/submissions/update_grades --json '{
  "grade_data": {
    "11111": {"posted_grade": "45"},
    "22222": {"posted_grade": "50", "text_comment": "Nice work"}
  }
}' --live
```

Returns a Progress object; poll `GET /progress/<id>` until
`workflow_state: completed`. The command returning is not proof the grades
landed. Preview the full grade_data with the user first.

## Posting policy

With manual posting, grades stay hidden until posted. Check `post_manually` on
the assignment.

This is the most confusing thing Canvas does, and it makes two claims people
treat as one into two different claims: **"I pushed the grades" and "students
can see their grades" are not the same statement.** The API call succeeds, a
`submissions` read shows the score, and the student sees nothing. If the user
expects students to see scores immediately, check the assignment's posting
policy in the Canvas gradebook.

The reverse also holds: **with an automatic posting policy there is no draft
state.** A score is visible the instant it is set. Get the number right before
`--live`.

Post or hide via GraphQL mutations (`postAssignmentGrades`,
`hideAssignmentGrades`) since REST has no clean equivalent:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 graphql \
  'mutation { postAssignmentGrades(input: {assignmentId: "222"}) { progress { _id } } }' --live
```

`canvas.py` recognizes a `mutation` in the query string and puts it through the
same write gate as a REST write, so posting grades needs `--live` and the
course's `write_mode` like everything else.

## Bulk reads: prefer GraphQL

For "every score for every student on every assignment", REST pagination is
painful. One GraphQL query does it:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 graphql '
query ($courseId: ID!, $cursor: String) {
  course(id: $courseId) {
    submissionsConnection(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        _id score grade submittedAt late missing excused state
        assignment { _id name pointsPossible dueAt }
        user { _id name sisId email }
      }
    }
  }
}' --vars '{"courseId": "123456"}'
```

Page with `after: "<endCursor>"` when `hasNextPage` is true. GraphQL `_id`
matches REST ids; plain `id` is an opaque global id. `--vars` takes the numeric
course id — `:course` substitution does not reach inside a GraphQL variable
block (`gotchas.md` #16).

`user.email` availability depends on schema/permission scope on your
instance — verify once per instance (`graphql 'query { __type(name: "User")
{ fields { name } } }'` and check `email` is listed and non-null in practice)
before relying on it; otherwise cross-reference by `user._id` against the
email map from `/courses/:course/users --param "include[]=email"`
(`students-enrollments.md`).

For the combined status/todo report (missing/late/ungraded within a time
window, grouped by assignment, with at-risk flagging), see the course-reports
skill, which builds directly on this query.

## Files attached to submissions

Each attachment object includes a tokenized `url` for download; fetch it with
plain HTTP (the url embeds its own auth, no Bearer header needed). Attachment
urls expire, so download promptly rather than storing links.

### Bulk-downloading every submission

For offline grading, feedback, or a similarity check (MOSS for code, Turnitin
and friends for prose), pull the whole assignment at once with
`download_submissions.py` instead of walking attachments by hand:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/download_submissions.py --course 326 \
    --assignment-id 678 --dry-run
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/download_submissions.py --course 326 \
    --assignment-id 678
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/download_submissions.py --course 326 \
    --assignment-id 678 --out ./hw3-code --submitted-only
```

It writes a per-student folder (`<sortable_name>_<user_id>/`) containing each
uploaded file, `text_entry.html` for a typed submission, `submitted_url.txt`
for a URL submission, and `_submission.json` (attempt, submitted_at, late,
score). The Test Student and no-submission students are skipped and counted.

This script writes only to local disk, so it takes no `--live` and there is no
write gate on it — nothing changes in Canvas. What it does create is a folder
full of student work.

**Downloaded student work is PII.** Output defaults to
`.canvas-cache/<course_id>/submissions/<assignment_id>/` under the working
directory. Before the first download in a project, make sure `.canvas-cache/`
is gitignored — see "Student data on disk" in the plugin README, which is a
must and not a suggestion. If you redirect output with `--out`, the same
applies to that directory.

## Enrollment-level grades (current/final)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/enrollments --all --param "type[]=StudentEnrollment"
```

Each enrollment carries `grades.current_score`, `grades.final_score` (ungraded
as zero), and `unposted_current_score` variants that include hidden grades.
Be careful which one you report; current vs final differ meaningfully
mid-semester. The course-reports skill's grade report is built on this
distinction.
