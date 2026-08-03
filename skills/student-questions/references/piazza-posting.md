# Writing to Piazza

`${CLAUDE_PLUGIN_ROOT}/scripts/piazza_post.py` is the only script here that writes. `piazza_fetch.py` cannot post
anything, which is what makes it safe on a schedule; keep that separation intact rather than
adding a convenience flag that collapses it.

## Actions

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_post.py answer      --course 326 --cid 141 --file draft.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_post.py followup    --course 326 --cid 141 --text "quick note"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_post.py privatize   --course 326 --cid 146            # dry run
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_post.py privatize   --course 326 --cid 146 --live --explain
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/piazza_post.py unprivatize --course 326 --cid 146 --live
```

Drafts belong in `<course>/.infra/piazza/drafts/`, named so the thread is obvious, e.g.
`2026-10-13-cid141.md`. Keeping them on disk rather than passing text inline means the
exact bytes the user approved are the exact bytes that get posted, and they stay readable
afterwards when someone asks what was said.

`answer` fills the official instructor answer slot, which marks the thread resolved and is where
students look. `followup` posts into the discussion instead, leaving the thread visibly open.

`privatize` and `unprivatize` need two things: the `--live` flag, and `"privatize_mode": "live"`
in `.infra/piazza/config.json`. With either missing they print what they would do and exit.
Two switches rather than one because a flag is easy to type by reflex, while the config file is a
decision made once and deliberately. `--override-mode` forces a single run past the config, and
should be reserved for a case the user explicitly asked for.

Every write appends to `.infra/piazza/actions.log` as JSON, including the previous `feed_groups`
value so a privatize can be reversed exactly. Read that log when the user asks what happened
overnight. `course_infra.py verify` surfaces the most recent entry.

The mismatch check runs before any network call: if `.infra/course-profile.md` and
`.infra/piazza/config.json` name different Piazza classes, the script exits without posting. That
is the guard against a course folder copied from last term still pointing at last term's class.

## How privatizing actually works, and what could go wrong

Piazza scopes a post's audience with `config.feed_groups`. A public post has it empty; a private
one holds `instr_<nid>,<author_uid>`, meaning staff plus the author. Making an existing post
private means writing that field through `content.update`.

The hazard is that `content.update` is undocumented, and the unofficial client's own helper sends
only a `subject` field, which is a good way to blank a student's post body. The script therefore
round-trips every existing field explicitly, and after the write it re-reads the post and
compares the body against what was there before. If the body changed, it restores the original
and exits non-zero. If that ever fires, stop and tell the user immediately with the cid — do not
continue down a batch.

Because none of this is verifiable without a real account, the first live run should be against a
dummy course the user creates for the purpose, on a throwaway post, checking in the browser that:

1. the post left the public feed,
2. the student author can still see it,
3. the body text is untouched,
4. `unprivatize` puts it back.

Four minutes of checking against a semester of trusting it.

## The detection threshold

`piazza_fetch.py --scan-leaks` returns a `leak_candidates` array. A post qualifies when it is
public, sits in an assignment folder (matching `hw`, `homework`, `assignment`, `proj`, `lab`,
`pset`) or names an assignment passed via `--assignment-keywords`, and contains at least
`--min-code-lines` (default 6) lines that look authored rather than emitted.

Lines that look like output — tracebacks, `at Foo (bar.js:12)`, `npm ERR!`, caret markers,
`node_modules` paths — are counted separately, and a post whose code is mostly output is not
flagged. This is the difference between "here is my working filter function" and "here is the
error I cannot read", and only the first one is a leak.

Each candidate carries `reasons` and an `excerpt`. Show both to the user: the reasons are how
they calibrate the threshold, and the excerpt is how they check the call in two seconds without
opening Piazza.

Tuning, if it is wrong in practice: raise `--min-code-lines` if it is grabbing too much, and pass
`--assignment-keywords "HW4,Recipe Browser"` so posts that name the assignment outside an
assignment folder still get caught.

## The explanation followup

`--explain` posts a short note on the now-private thread telling the student what happened. It
exists because a thread that silently vanishes reads as punishment, and the common student
response is to repost publicly, which recreates the problem. The default text says the post was
made private because it showed assignment code, that it is not a penalty, and that staff will
answer it there.

Override it with `--explanation` when the course has its own wording. Keep whatever replaces it
short, non-accusatory, and clear that the question will still get answered.

## What not to automate

Do not add auto-posting of drafted replies, on any schedule or trigger. The value of the whole
workflow is that a person reads the hint before students do, and a schedule has no person in it.
If the user asks for it, say plainly what it costs: a wrong hint reaching the entire class with
nobody having read it first.
