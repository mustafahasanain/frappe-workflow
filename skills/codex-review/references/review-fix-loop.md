# Review-Fix Loop (stage `review_fixes`)

For each round with `CHANGES_REQUIRED`:

## 1. Inspect Every Finding

Validate each finding **against the repository** before touching code:

- Open the cited file/lines; confirm the Issue actually exists.
- Check the Plan Reference: does the plan really require what the fix
  demands?
- Classify: **valid** (fix it), **invalid** (refute with evidence), or
  **unclear** (needs the user or another Codex round to clarify).

## 2. Apply Valid Fixes

Through the task-implementation skill's rules: read only what's needed,
implement, validate, run affected tests. Severity orders the work (High
first), but all valid findings are addressed before the next round.

## 3. Refute Invalid Findings

Do not silently ignore them. Record in the implementation summary (a
"Review Round NNN responses" note): the finding, why it does not apply,
with file/line evidence. Codex sees this in the next round's bundle.

## 4. Update the Summary

Refresh `docs/ai-context/implementation-summary.md`: new test results, any new
deviations, the round-response notes.

## 5. Next Round

1. `bin/frappe-workflow validate completion-gate` (must still pass — steps
   remain Completed, no new secrets, etc.).
2. `bin/frappe-workflow review bundle` → new fingerprint + round-NNN+1
   prompt.
3. Update state round/fingerprint/prompt_path;
   `state transition codex_review --reason "review prompt round NNN+1"`.
4. Repeat until `APPROVED`.

## Loop Hygiene

- Self-transition `review_fixes → review_fixes` records progress on
  multi-finding rounds.
- Round files are append-only history: `round-001-…`, `round-002-…` all
  remain.
- If a finding requires a business-scope change, that is not a "fix" — it
  goes back to planning with user awareness (no silent scope expansion).
- If rounds stop converging (Codex re-raising refuted findings without new
  evidence, or contradicting its previous round), stop and surface the
  disagreement to the user rather than looping forever.
