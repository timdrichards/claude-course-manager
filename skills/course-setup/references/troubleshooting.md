# When something is wrong

Diagnose from `verify` output first. It reports the things that actually go wrong, and its
wording is meant to be repeated to the user rather than paraphrased.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326
```

---

## MISMATCH between the profile and a tool's config

The single most important failure in this plugin, and the only one that should stop work
outright.

The course profile names one class id and the tool's `config.json` names another. The folder does
not know which class it belongs to. This is the normal state of a folder copied from last term
with the profile updated and the config not, and it is how a reply meant for one section reaches
another.

Do not guess which is right. Ask, fix the wrong one, re-run `verify`, and only then continue. Do
not post, announce, or grade in the meantime.

---

## Credentials

**"credentials missing X"**: the file exists but the key is blank, or the key is not in the
environment. Name the exact file and the exact key. Never ask the user to paste a secret into
chat, and never write one yourself.

**"credentials is 0644; other users on this machine can read it"**: run the `chmod 600` command
`verify` prints. Worth one sentence.

**Login fails despite a filled-in credential.** The cause differs by platform:

- *Canvas 401*: the token is wrong, expired, or was revoked. Tokens with an expiry date die
  silently on schedule; make a new one.
- *Canvas 403*: the token works but the account is not a teacher or TA in this course, or the
  course is concluded. Concluded courses are read-only through the API even for instructors.
- *Piazza*: almost always SSO. If the school logs into Piazza through Canvas, there is no Piazza
  password and no workaround.
- *Gradescope*: probably SSO too. Try "Forgot your password?" once; if it fails, switch to the
  `GRADESCOPE_SESSION` cookie described in `platforms.md`.
- *Gradescope, previously working, now failing*: a session cookie expired. The script says so
  specifically rather than reporting a bad password. Get a fresh cookie.

---

## A scraped platform returns nothing, or a scrape error

Piazza and Gradescope are scraped, so their failure modes include the site changing underneath.

A `ScrapeError` from `gradescope_fetch.py` names the page and the element it could not find. That
is a real bug in the script, not a problem with the user's course or credentials; say so plainly
rather than sending them to check their password. The fix is updating the selector in
`gradescope_fetch.py`, which is a small change once someone looks at the page's current HTML.

**A fetch that returns zero results is not the same as a fetch that failed.** Say which. "No new
questions since Tuesday" and "the fetch broke" look identical to a user reading a summary, and
only one of them is good news. State the filter that was applied whenever the answer is nothing.

---

## Corrupt state

**`state/seen.json` is corrupt**: delete it. It only records which items were already handled;
the cost of losing it is re-processing recent items, not data loss.

**`config.json` is not valid JSON**: the script exits naming the file and the parse error. Open
it and fix it; these are small files, usually a trailing comma.

**The registry is corrupt**: `course_infra.py` ignores a corrupt registry rather than failing,
and says so in `list` output. Everything still works from explicit paths. Rebuild it by running
`register` on each course folder.

---

## Course folder problems

**"course folder does not exist"**: the registry points somewhere that has since moved. Run
`register` on the new location, or `unregister` the stale name.

**"no .infra/ in this folder; run init first"**: the folder is real but not a course yet. `init`
is safe on a folder that already holds material; it only adds what is missing.

**A bare name resolves to the wrong course**: `list` shows every registered name. Names match
loosely, so `326` finds `COMPSCI 326`, and an ambiguous name is an error rather than a guess.
Use the full path when two courses genuinely share a number across terms, or register them under
distinct names like `326-f26`.

---

## Undoing a write

Every write to Canvas or Piazza appends to that tool's `actions.log` with the previous value.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 undo
```

That prints the last recorded write and the exact command that reverses it, where a reversal
exists. Some things cannot be undone from here and the output says so rather than pretending:
a submission that had no score before cannot be un-graded through the API, and announcements and
assignments are deleted in the web UI rather than by script.

---

## Dry-run refusing to write

Both Canvas writes and Piazza's privatize need two switches: the command flag (`--live`) and the
course's config (`write_mode` or `privatize_mode` set to `"live"`). Either one missing means the
command reports what it would do and stops.

This is deliberate. The flag is easy to type by accident; the config file is a decision made once,
after watching the tool do the right thing on real data. Flip the config only when the user asks
for it, and only after they have seen a dry run. Do not offer `--override-mode` as a convenience;
it exists for a considered one-off, not for getting past a gate that is doing its job.
