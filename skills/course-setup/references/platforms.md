# Connecting a platform

Each platform needs an id and a credential. What follows is where to find each, what SSO does to
it, and what the credential can do if it leaks. Tell the user the last part: a Canvas token is
not a low-stakes thing to paste into a file.

---

## Canvas

**The one with a real API.** Documented, versioned, stable, and it returns useful errors. Anything
that has to actually land should go through Canvas rather than a scraped platform.

**Base URL**: the host you use for Canvas, e.g. `https://umass.instructure.com`. No trailing path.

**Course id**: the number in the course URL. `.../courses/123456/assignments` means `123456`.

**Token**: Canvas → Account → Settings → Approved Integrations → **New Access Token**. Set an
expiry date. Copy it immediately; Canvas shows it once.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 --tool canvas \
    --base-url https://umass.instructure.com --course-id 123456
# then put CANVAS_TOKEN=... in <course>/.infra/canvas/credentials
```

**What the token can do.** Everything the account can do, in every course that account touches,
not just this one. Canvas has no per-course tokens. That means a leaked instructor token can read
every student's grades and submissions across all courses, and change them. Say this plainly when
asking the user to create one, recommend an expiry date, and tell them to delete it in Canvas when
they stop using it. The credentials file is created at mode 600; `verify` complains if that
changes.

**SSO is not a problem here.** Token auth is independent of how the user signs in with a browser,
so a school that uses SSO for Canvas still issues working API tokens.

**Failure meanings**: 401 means the token is wrong or expired. 403 means the token is valid but
the account lacks permission in this course, or the course is concluded and therefore read-only.
404 usually means the wrong course or assignment id.

---

## Piazza

**No official API.** The client talks to Piazza's internal endpoints through the unofficial
`piazza-api` package, so it can break when Piazza changes something.

**Class URL**: `https://piazza.com/class/<id>` from the browser address bar while in the course.

```bash
pip install piazza-api
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 --tool piazza \
    --course-url https://piazza.com/class/<id>
# then fill PIAZZA_EMAIL / PIAZZA_PASSWORD in <course>/.infra/piazza/credentials
```

**SSO is a hard stop.** If the school logs into Piazza through Canvas or another SSO provider,
the account may have no Piazza password at all, and password login cannot work. Establish this
before promising a scheduled digest will run. There is no workaround in this plugin.

**Where the password reaches**: the instructor's Piazza account, which means every course they
teach or take on Piazza.

---

## Gradescope

**No public API, and Gradescope says so.** The client scrapes their web app. Two consequences the
user should hear before relying on it:

1. **It breaks.** Surveying maintained open-source clients, the HTML parsing broke about once a
   quarter over the last year, while login and URLs stayed stable for six. Every selector in
   `gradescope_fetch.py` raises loudly rather than returning nothing, so a break looks like an
   error and not like an empty course.
2. **It cannot write scores.** No maintained client implements score-writing, Gradescope
   documents no import path, and its data model computes scores from rubric selections rather
   than point values. The script therefore has no write path at all. Push grades through Canvas.

**Course id**: the number in the Gradescope course URL, e.g. `.../courses/753413`.

```bash
pip install requests beautifulsoup4
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 --tool gradescope \
    --course-id 753413
# then fill GRADESCOPE_EMAIL / GRADESCOPE_PASSWORD
```

**SSO, and the way around it.** Gradescope's login page offers a native email/password form
alongside school-credentials and Google buttons. An account created through SSO has no native
password by construction. Have the user try **"Forgot your password?"** once with their school
address; if a reset works, password login works and nothing else is needed.

If that fails, the account is SSO-only and no script can log in with a password. A SAML redirect
chain plus MFA is designed to be un-scriptable, and pretending otherwise just produces confusing
failures. The fallback: log into Gradescope in a browser, copy the `_gradescope_session` cookie
value from developer tools, and set it as `GRADESCOPE_SESSION` in the credentials file. The
script prefers that cookie over the password when both are present. Session cookies expire, so
this is a periodic chore rather than a one-time setup; when it expires the script says so
specifically instead of failing as a bad password.

**What can be read**: courses, assignments, roster, per-assignment `scores.csv`, submission
lists, and submission downloads as zips.

---

## Google Workspace

Drive, Calendar, and Gmail come from account-level connectors rather than anything in this
plugin, so there is nothing to configure in `.infra`. If they are connected they appear as tools
automatically; if they are not, the user connects them in their Claude settings.

Useful in course work for: pulling a syllabus or assignment spec out of Drive, reading the course
schedule off a calendar, and drafting mail to students or staff. Nothing in this plugin sends
mail on its own.

---

## Adding a platform later

Every tool follows the same shape, and `course_infra.py` reads its whole notion of a tool from
the `TOOLS` dict at the top of that file. Adding one means adding an entry there with its config
keys, credential keys, and the regex that finds its id in a course profile. `init`, `verify`, and
the credential loader pick it up with no other change. Write its client as a separate script next
to the others and have it call `course_infra.resolve`, `load_config`, `require_credentials`, and
`log_action` so it behaves like the rest.
