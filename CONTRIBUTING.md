# Contributing

## The one rule that matters

**Never put real student data in this repository.** Not in an issue, not in a test fixture, not
in a screenshot, not in a commit message. Names, emails, SIS ids, grades, submissions, and
accommodation details are education records: FERPA-protected in the US, personal data under GDPR
in the UK and EU, and the instructor running this tool is the data controller for whatever lands
on their disk.

When you need to show a problem, invent a student. `Ada Lovelace, alovelace@example.edu, SIS
900001` is enough to reproduce anything in here.

## Anything that changes a grade needs a test

Not a suggestion. The grading paths in this plugin have already shipped two bugs that silently
changed scores, and both were found by reading rather than by running:

- A late-day budget that was spent by ungraded and excused submissions.
- A default timezone hardcoded to the author's own, which shifted lateness calculations for
  everyone outside US Eastern.

Neither raised an error. Both produced a defensible-looking number that was wrong. If a change
touches lateness, penalties, rubric scoring, roster matching, or anything that computes or posts
a score, it needs a test that fails before the change and passes after.

## Running the tests

```bash
pip install pytest pyyaml
env -i PATH="$PATH" HOME=/tmp/h python -m pytest tests/ -q
```

The empty environment is the point. The suite is offline by design: no credentials, no network,
no reading the developer's own course folders. If a test needs any of those, it is testing the
wrong thing.

```bash
python scripts/prose_check.py --self-test
python .github/validate_plugin.py
```

## Writing

Documentation here follows `skills/course-setup/references/house-style.md`, and the checker
enforces the mechanical parts:

```bash
python scripts/prose_check.py path/to/file.md
```

No em dashes, straight quotes, sentence-case headings. `ai-tells.md` explains the rest, including
the things that look like AI tells and are not, which the checker deliberately ignores.

## Adding a platform

`course_infra.py` reads its whole notion of a tool from the `TOOLS` dict at the top of the file:
config keys, credential keys, and the regex that finds the platform's id in a course profile. Add
an entry there and `init`, `verify`, and the credential loader pick it up with nothing else
changed.

Write the client as a script beside the others, and have it call `resolve`, `load_config`,
`require_credentials`, and `log_action` so it behaves like the rest. Any write goes through the
two-switch gate and records its before-value.

## Reporting a platform quirk

The most valuable issues here are the ones that document a thing an LMS actually does, especially
when it disagrees with its own documentation. Include the endpoint, the request, the response, and
what you expected. Those become reference entries and save the next person an afternoon.
