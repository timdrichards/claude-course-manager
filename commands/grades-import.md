---
description: Import Gradescope (or other CSV) scores into a Canvas assignment, with a preview and accommodation-aware lateness.
argument-hint: [course] [csv path]
---

Import **$2** into a Canvas assignment for course **$1**.

Read `${CLAUDE_PLUGIN_ROOT}/skills/canvas/references/grade-sync.md` and `${CLAUDE_PLUGIN_ROOT}/skills/canvas/references/late-policy.md` in the `canvas`
skill first. Two rules in there are silent-corruption risks, not style notes:

- **Diff against `entered_score`, never `score`.** `score` is post-late-policy,
  so comparing raw CSV values against it makes every already-penalised cell look
  like a mismatch, and "fixing" them resets real penalties to full marks.
- **Never trust the CSV's own lateness column.** It measures against the
  *Gradescope* deadline and is blind to Canvas per-student overrides. Compute
  lateness from submission time minus that student's own `cached_due_date`.

Show the full preview before writing anything: matched rows, unmatched rows with
the reason, and which students would be marked late. **Never auto-penalize an
accommodated student**; route them to the instructor to decide individually.

Prefer a targeted diff over a blanket sync. A course part-way through a term has
manual zeros, waivers, and overrides in it, and a blanket re-import quietly
undoes instructor decisions. Check for an explaining comment on any cell that is
0 in Canvas while the CSV shows a real score.

Verify every write with a fresh read: `score` equals `entered_score` and
`points_deducted` is null, unless a deduction was intended.
