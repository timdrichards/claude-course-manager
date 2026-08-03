# Discussions and Announcements

**An announcement is a discussion topic with `is_announcement: true`.** Same
endpoints, same payload, one flag. The consequences differ enormously:
announcements notify students immediately on creation (subject to their
notification preferences) and cannot be "unpublished", only deleted or given
a future `delayed_post_at`. Always confirm announcement text with the user
before posting.

The course-comms skill writes the text; this file is how it lands. For an
ordinary announcement, `canvas_api.py --course 326 announce --title "..."
--file body.md --live` is the shorter path and takes `--at <ISO timestamp>` for
scheduling. Everything below is the general surface underneath it, and the
place to go for discussions, which `canvas_api.py` does not create.

## Discussions

### List / read

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/discussion_topics --all
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/discussion_topics/<id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/discussion_topics/<id>/entries --all
```

Full threaded content is easier via the materialized view:
`GET /courses/:course/discussion_topics/<id>/view` returns the whole tree in
one call.

### Create

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/discussion_topics --json '{
  "title": "Week 3 Retrospective",
  "message": "<p>Post one thing that went well and one to improve.</p>",
  "discussion_type": "threaded",
  "published": false,
  "require_initial_post": true
}' --live
```

Note: discussion payloads are **flat**, not nested under a `discussion_topic`
key. This inconsistency with assignments/quizzes trips people constantly.

Options:
- `discussion_type`: `threaded` (replies to replies) or `side_comment`.
- `require_initial_post: true` hides peers' posts until a student posts.
- Graded discussion: include an `assignment` object in the same payload:
  `"assignment": {"points_possible": 5, "due_at": "..."}`.
- `delayed_post_at` schedules visibility; `lock_at` closes it.
- `pinned: true` pins to the top of the discussions index.

### Replying / moderating

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/discussion_topics/<id>/entries \
    --json '{"message": "<p>Instructor note: see the rubric for details.</p>"}' --live
# Lock a topic
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/discussion_topics/<id> --json '{"locked": true}' --live
```

## Announcements

### Post (student-visible immediately; confirm first)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/discussion_topics --json '{
  "title": "Demo Day room change",
  "message": "<p>Demo Day moves to CS Building room 150.</p>",
  "is_announcement": true
}' --live
```

### Schedule for later (safer default when the timing allows)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/discussion_topics --json '{
  "title": "Reminder: HW7 due Friday",
  "message": "<p>Submit on Gradescope by 11:59pm.</p>",
  "is_announcement": true,
  "delayed_post_at": "2026-09-17T09:00:00-04:00"
}' --live
```

Anything written outside business hours should be scheduled rather than posted.
A 2am announcement gets read at 2am by exactly the students who should be
asleep.

### List

Announcements do not appear in the plain discussion_topics list. Either:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/discussion_topics --all --param only_announcements=true
# or across courses, note the required context code and date window:
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /announcements --all \
    --param "context_codes[]=course_123456" \
    --param start_date=2026-01-01 --param end_date=2026-12-31
```

Two traps in that second call. The `/announcements` endpoint defaults to a
narrow recent date window, so pass explicit dates or results will look
mysteriously empty. And `context_codes[]` is a query param, so `:course` is
**not** substituted there — interpolate the numeric course id yourself
(`gotchas.md` #16). `canvas_api.py --course 326 announcements` avoids both.

### Comments on announcements

By default announcements allow replies unless `locked: true` is set at
creation or the course disables commenting. Set `"locked": true` for
one-way announcements.
