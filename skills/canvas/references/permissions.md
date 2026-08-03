# Roles, permissions, and what your token can actually do

An API token carries **exactly the permissions of the user who made it** —
nothing more. There is no separate scope system to configure: if you can do it
in the Canvas UI, the token can do it; if you can't, the token can't. It also
carries them across *every* course that account touches, not just this one;
Canvas has no per-course tokens.

That makes permission failures the single most confusing class of error here,
because of one Canvas design choice:

> **Canvas returns `404 Not Found` for objects your token is not allowed to
> see.** Not `403`. A missing assignment and a forbidden assignment are the
> same response.

So never conclude "that object doesn't exist" from a 404 alone. Rule out
permission first (below), then id, then deletion. `canvas.py` says this in its
own 404 hint, so the message you get back already carries the warning.

`403` does happen, for three narrower reasons: a permission that applies to the
*action* rather than to seeing the object, a **concluded course** (read-only
through the API, so writes 403 even though reads work), and rate limiting,
which Canvas signals as a 403 whose body mentions a rate limit. `canvas.py`
retries that last one for you.

## Telling a real 404 from a permission 404

```bash
# 1. Who am I, which Canvas, and which course does this folder point at?
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 whoami

# 2. Can I see the course at all?
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /courses/:course

# 3. What is my enrollment in it?
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/enrollments --all --param "user_id=self"
```

If (1) works and (2) 404s, it's almost always permission or a wrong instance,
not a deleted course. If (2) works and a nested object 404s, compare against
the same object in the Canvas web UI while logged in as yourself — if you can
see it there but not via API, suspect a *granular* permission (below) rather
than the role as a whole.

## What each capability needs

Roles vary by institution — admins can rename them and toggle individual
permissions — so treat this as "what the operation requires", not "what your
role is called".

| Capability | Typically needs | Canvas permission |
|---|---|---|
| Read assignments, pages, modules, files | Any enrolled role | — |
| Create / edit / delete assignments | Teacher, Designer | Assignments and Quizzes — add / edit / delete |
| Create / edit pages, modules, files | Teacher, Designer | Course Content — add / edit / delete |
| Read the roster | Teacher, TA | Users — view list |
| Read student **email addresses** | Teacher (often not TA) | Users — view primary email address |
| Read `sis_user_id` | Teacher + SIS rights | SIS Data — read |
| Read submissions and grades | Teacher, TA | Grades — view all grades |
| Post / change grades, bulk grade, late status | Teacher, TA (if granted) | Grades — edit |
| Create rubrics | Teacher, Designer | Rubrics — add / edit / delete |
| Create groups / group sets | Teacher, TA | Groups — add / manage |
| Post announcements | Teacher, TA (if granted) | Announcements — add |
| Moderate discussions | Teacher, TA | Discussions — moderate |
| Add / remove enrollments | Teacher, or admin at SIS schools | Users — Students — add / remove |
| Change course settings, late policy | Teacher | Course Content — edit / Manage Course |
| Masquerade (`as_user_id`) | Account admin | Users — act as |
| Anything under `/accounts/...` | Account admin | account-level role |

Two that surprise people most often:

- **Email addresses are separately gated.** `--param "include[]=email"` can
  silently return rows with no `email` field even though the roster itself
  reads fine. That breaks CSV imports that match by email. Fall back to
  `sis_user_id` or `login_id` (see `students-enrollments.md`), and make sure
  your CSV carries a SID column.
- **TAs are inconsistent.** Many institutions grant TAs grade editing but not
  roster email, or grading but not announcements. If a TA-run script half-works,
  this is why.

## Working as a TA or Designer

The examples here assume teacher-level access, but most read paths and grading
paths work fine for a TA with `Grades — edit`. What generally will not work
without a Teacher/Designer role:

- creating or deleting assignments, pages, modules
- changing the course-level late policy or course settings
- enrollment changes

If you are a TA, prefer the read-only capabilities (roster, submissions,
downloads, the course-reports skill) and the grading capabilities, and hand the
structural changes to the instructor.

## Account admins

Admin tokens can reach `/accounts/...` endpoints and masquerade as other users
(`--param as_user_id=<id>`), which is useful for reproducing "the student can't
see it" reports. Masquerading is **logged by Canvas** and attributed to you —
tell the user when you use it, and never use it to view anything you would not
open in front of them.

## Testing without risk

Institutions usually run beta and test instances
(`<school>.beta.instructure.com`, `<school>.test.instructure.com`) refreshed
from production weekly and Saturdays respectively. They are the right place to
try a destructive or bulk operation for the first time. Point `base_url` at one
in the course's `.infra/canvas/config.json`. Two caveats:

- Tokens are per-instance. A token created after the last refresh does not
  exist on beta yet — mint a new one there and put it in that folder's
  credentials file.
- Notifications are suppressed on beta, which is exactly what you want when
  testing announcements.

## First run against an unfamiliar instance

Canvas installs differ in enabled features and API surface. Check these once,
then trust them for the session:

1. **Token works, and as whom** — `canvas_api.py --course 326 whoami`. It
   prints the account, the instance, and the course id and name it reaches, so
   it doubles as the course-confirmation step.
2. **Email visibility** — `canvas.py --course 326 get /courses/:course/users
   --all --param "enrollment_type[]=student" --param "include[]=email"`;
   confirm `email` is actually populated, not just present.
3. **Quiz engine** — is New Quizzes enabled? Classic and New have different
   APIs and New cannot export per-student answers (`quizzes.md`). Default to
   Classic.
4. **Weighted groups** — `canvas.py --course 326 get /courses/:course --param
   "include[]=total_scores"`; read `apply_assignment_group_weights` before
   computing any grade or creating any assignment.
5. **HTML sanitization** — if you push authored HTML, create one page, `GET` it
   back, and confirm your inline styles survived (`pages.md`).

Self-hosted Canvas instances can lag the cloud API by a release or more; if a
documented endpoint 404s on one of these while your token is clearly fine,
check the instance's Canvas version before assuming this documentation is wrong.
