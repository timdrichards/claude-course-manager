# Cross-cutting Gotchas

Skim this once per session. Ordered roughly by how often each one burns time.

1. **Pagination is silent.** Every list endpoint returns 10 items by default
   with no warning that more exist. Always use `canvas.py get ... --all` for
   lists. If a count looks suspiciously round or small, this is why. A
   truncated list is invisible: 100 students out of 300 looks exactly like a
   class of 100.

2. **Payload nesting is inconsistent.** Assignments, quizzes, pages, and
   modules nest under a key (`{"assignment": {...}}`). Discussion topics,
   announcements, group categories, and file upload initiation are flat. When a
   POST returns 200 but nothing changed, wrong nesting is the usual cause:
   Canvas ignores unknown top-level keys instead of erroring.

3. **404 means "no" three different ways:** wrong id, deleted object, or
   insufficient permission. Canvas returns 404 rather than 403 for objects your
   token is not allowed to see, so a permission problem and a missing object are
   the same response. Do not conclude an object does not exist from a 404 alone.
   See `permissions.md` for how to tell them apart. (403 is a different animal
   here: permission on an action you can otherwise see, a concluded read-only
   course, or rate limiting.)

4. **Two quiz engines, two APIs.** Classic Quizzes: `/api/v1/.../quizzes`.
   New Quizzes: `/api/quiz/v1/.../quizzes`, far fewer capabilities, no
   per-student answer export. Identify the engine before promising anything.
   See `quizzes.md`.

5. **Published vs visible are different questions.** An object can be
   published yet invisible: inside an unpublished module, before `unlock_at`,
   restricted by section/override, or a locked file. When a student "can't
   see" something, check module state, dates, and overrides, not just
   `published`.

6. **Announcements fire on creation.** No unpublish, no undo of the
   notification. Use `delayed_post_at` to schedule, and always confirm the
   text with the user first.

7. **Datetimes: send an explicit offset, read UTC.** Canvas returns UTC (`Z`).
   A bare `2026-09-18T23:59:00` may be interpreted as UTC, making an 11:59pm
   Eastern deadline land at 7:59pm. Always send the offset
   (`2026-09-18T23:59:00-04:00`), and prefer an IANA zone name
   (`America/New_York`) anywhere a script takes a timezone, because a fixed
   offset applied across a daylight-saving boundary is wrong on one side of it.
   Never mirror Canvas's `Z` back as a way of avoiding the question.

8. **The Test Student pollutes counts.** `StudentViewEnrollment` appears in
   some listings (submissions especially, once "Student View" has been used).
   A user with no email and a name like "Test Student" is that. Filter it out
   of rosters, counts, and grade exports.

9. **HTML in, HTML out.** `description`, `body`, and `message` fields are raw
   HTML. Markdown is not rendered. Canvas also sanitizes aggressively: script
   tags, some iframes, and inline styles may be stripped on save, so verify
   round-trip if formatting matters.

10. **Deletes cascade.** Deleting an assignment deletes grades; deleting a
    file breaks links; deleting an enrollment (task=delete) erases the
    record. Prefer unpublish, conclude, or deactivate. The UI undelete page
    (`/courses/<id>/undelete`) can rescue some objects; the API cannot, and
    neither can `canvas_api.py undo`.

11. **SIS sync can overwrite manual changes.** At SIS-managed institutions,
    enrollments and sections resync from the registrar. Manual roster edits
    may not stick.

12. **Rate limiting is per token and burst sensitive.** The helper backs off
    automatically — this is true and worth relying on: `canvas.py` retries on
    429, on Canvas's 403-with-a-rate-limit-body, and on 502/503, and it pauses
    when `X-Rate-Limit-Remaining` drops near its floor. For large jobs
    (hundreds of writes) expect it to slow down; that is intended behavior, not
    a hang. Prefer bulk endpoints (`bulk_update`, `update_grades`, GraphQL)
    over per-object loops anyway.

13. **Masquerading** (`--param as_user_id=<id>`) executes as another user and
    requires admin permission. Useful for "what does the student see"
    debugging; it is logged by Canvas, so mention it to the user.

14. **Beta and test instances** (`<school>.beta.instructure.com`,
    `<school>.test.instructure.com`) refresh from production weekly and
    Saturdays respectively. Tokens created after the last refresh do not
    exist there. Great sandbox; notifications from beta are suppressed. To use
    one, point `base_url` at it in the course's `.infra/canvas/config.json`
    (or set `CANVAS_BASE_URL`) and put a beta-minted token in that folder's
    credentials file.

15. **GraphQL coverage is partial.** Excellent for bulk submission reads and
    grade posting mutations; missing for many admin operations. `_id` in
    GraphQL equals the REST id; `id` is an opaque global id.

16. **`:course` substitution only rewrites the URL path, never `--param`
    values.** Still true in the merged `canvas.py`: substitution happens in
    `resolve_path`, which touches the path and nothing else. Endpoints that
    take the course as a *query* param instead of a path segment — e.g.
    `/calendar_events?context_codes[]=course_<id>` — need the numeric id
    interpolated by hand. `context_codes[]=course_:course` is sent to Canvas
    literally and silently returns nothing. The id is `course_id` in the
    course's `.infra/canvas/config.json`, and `canvas_api.py --course 326
    whoami` prints it.

17. **A write with no `--live` is not a failure.** `canvas.py` prints the
    request it would have sent and exits normally. Read the preview before
    adding the flag; do not treat the absence of a Canvas object as a bug. A
    write refused because the course config still says `dry-run` is different:
    that exits nonzero, on purpose, so a refusal never looks like a preview.
