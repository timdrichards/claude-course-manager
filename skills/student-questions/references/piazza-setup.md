# Pulling questions from Piazza directly

`${CLAUDE_PLUGIN_ROOT}/scripts/piazza_fetch.py` logs into Piazza and writes unanswered threads to JSON. It is
read-only: there is no code path in it that posts, edits, resolves, or deletes anything. That
property is deliberate, because the script runs unattended on a schedule and a bug that posted
to a 180-person class would be unrecoverable. If someone asks for auto-posting, that is a
separate decision and a separate script, not a flag on this one.

## What to tell the user before they set this up

Be upfront about these, since they decide whether this is even worth doing:

- **Piazza has no official public API.** This uses the unofficial `piazza-api` client against
  Piazza's internal endpoints. It works today and can break whenever Piazza changes something.
  When it breaks it should fail loudly rather than quietly return zero threads.
- **It needs a real Piazza password.** If their institution logs into Piazza through Canvas,
  Blackboard, or another SSO provider, they may not have one, and password login will fail. The
  fallback in that case is exporting a browser session cookie, which expires and needs redoing.
- **Requests come from their instructor account.** Keep the polling interval sane. Twice a day is
  fine; every five minutes is asking for trouble.

## Where everything lives

A course is a folder; the tooling lives under `.infra` inside it, one subfolder per service:

```
~/courses/326/
└── .infra/
    ├── course.json            number, title, term, institution
    ├── course-profile.md      shared course knowledge, read by any tool
    ├── .gitignore             ignores */credentials, */state/, */inbox/, */actions.log
    ├── piazza/
    │   ├── config.json        class URL, assignment keywords, privatize mode
    │   ├── credentials        PIAZZA_EMAIL / PIAZZA_PASSWORD, chmod 600
    │   ├── inbox/             fetched threads, one JSON per run
    │   ├── drafts/            replies awaiting approval
    │   ├── state/seen.json    threads already handled
    │   └── actions.log        every write, with undo information
    ├── canvas/                same shape, when something needs it
    └── gradescope/
```

Course-level facts sit directly under `.infra` so a Canvas or Gradescope helper can read them
without knowing Piazza exists. Service-level facts — a class URL, a password, a seen-list — stay
in that service's folder.

One course per folder rather than one shared config, because a shared "already seen" list across
two sections means a thread handled in one silently vanishes from the other's digest, and a
shared class URL is one stray flag away from posting a 326 answer into 426.

## Setup

```bash
pip install piazza-api

python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py init 326 --tool piazza \
    --name "COMPSCI 326" --term "Fall 2026" \
    --course-url https://piazza.com/class/mfxyzabc123
```

`init` is safe to re-run and never overwrites, so it works on a folder that already holds course
material. Fill in the password in `~/courses/326/.infra/piazza/credentials`, then confirm:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326 --tool piazza
```

`verify` exits non-zero when something is wrong and prints what. Read it back to the user before
acting: the course and class URL in one line is enough, and it is what catches a folder belonging
to a different section than the one they are asking about. Drop `--tool` to check every service
configured for the course.

Any path inside the tree resolves to the same course — `~/courses/326`, `~/courses/326/.infra`,
and `~/courses/326/.infra/piazza` are interchangeable. `COURSE_DIR` sets a default so
`--course` can be omitted. Someone teaching several courses on one Piazza account can skip the
per-course credentials file and export `PIAZZA_EMAIL` and `PIAZZA_PASSWORD` instead; the course's
own file wins when both exist.

Adding a service later is the same command with a different `--tool`, and it leaves the existing
ones untouched.

## Running it

```bash
# everything unanswered, into .infra/piazza/inbox/<timestamp>.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_fetch.py --course 326

# last 12 hours, plus a scan for leaked assignment code
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_fetch.py --course 326 --since 12h --scan-leaks

# include answered threads, print instead of saving
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_fetch.py --course 326 --all --stdout
```

`.infra/piazza/config.json` supplies the class URL, the assignment keywords used by leak
detection, and the code-line threshold, so day-to-day commands stay short. Flags override it for
one-off runs.

The state file at `.infra/piazza/state/seen.json` keeps a handled thread out of the next digest.
Its key includes the thread's last-modified time, so an answered thread that gets a new followup
does reappear, which is usually what you want. `--no-state` gives a one-off look that does not
affect the schedule.

Output JSON carries `course_root` and `course_name`, so a digest built from a file on disk can
say which course it belongs to without guessing.

## Scheduling a digest

The credential lives on the user's own machine, which means the fetch has to run there too.
Two shapes work, and which one to recommend depends on whether their desktop is reliably on.

**Cron on their machine (most reliable).** The fetch runs whether or not anything else is awake,
and the JSON waits in `inbox/` until it gets picked up:

```cron
0 7,18 * * 1-5 /usr/bin/python3 /path/to/piazza_fetch.py \
    --course $HOME/courses/326 --since 14h --scan-leaks \
    >> $HOME/courses/326/.infra/piazza/fetch.log 2>&1
```

One line per course. Then a scheduled task reads the newest file in that course's
`.infra/piazza/inbox/`, drafts replies, and sends the digest. If the desktop is asleep at digest
time nothing is lost: the file is still there next run.

**Scheduled task does both.** The scheduled session runs the fetch on their machine through the
device bridge and drafts in the same pass. Simpler, one moving part, but it only works when the
desktop is connected. Fine for someone who leaves their laptop open, wrong for someone who does
not.

Either way, use `create_trigger` from the Claude Code Remote MCP server for the scheduled part.
Cron expressions there are UTC, so convert from local time and remember it shifts with daylight
saving.

## When it breaks

- **"Piazza login failed"** — usually SSO, occasionally a changed password or a captcha after
  repeated failures. Have them confirm they can log in at piazza.com with that email and
  password directly, not through their LMS.
- **Zero threads returned, but there are unanswered questions on the site** — either everything
  is in `.infra/piazza/state/seen.json` already (try `--no-state`), or `--since` is too narrow, or the
  feed shape changed. Check `counts.feed_scanned` in the output: if that is zero, the API contract
  moved and the client needs updating.
- **"does not exist. Set it up with..."** — the course has no `.infra/piazza` yet, or the folder
  was moved and `COURSE_DIR` is stale. Run `course_infra.py verify` on the real path.
- **MISMATCH from verify** — `.infra/course-profile.md` and `.infra/piazza/config.json` name
  different Piazza classes. Do not post anything until the user says which is right. This usually
  means a course folder was copied from last term and the URL was never updated.
- **`ImportError: piazza_api`** — `pip install piazza-api` in whatever Python the cron job uses,
  which is often not the one on their interactive PATH.
