## What this changes

## Why

## Does it change a grade, a score, or anything posted to students?

If yes: which test covers it? Anything that computes or posts a score needs a test that fails
before this change and passes after.

## Checklist

- [ ] No real student data anywhere in the diff
- [ ] `env -i PATH="$PATH" HOME=/tmp/h python -m pytest tests/ -q` passes
- [ ] `python .github/validate_plugin.py` passes
- [ ] `python scripts/prose_check.py` clean on any documentation touched
- [ ] Any new write goes through the two-switch gate and records a before-value
- [ ] CHANGELOG updated if the public interface changed
