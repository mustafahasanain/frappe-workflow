# Completion Gate (implementation → codex_review)

Codex review is allowed only when **all** of these hold. The deterministic
subset is checked by `bin/frappe-workflow validate completion-gate`; the
rest is your attestation, written into the summary.

## Deterministic (CLI-checked)

- Plan valid; every step `Completed` — none Pending / In Progress /
  Blocked [`GATE_STEP_INCOMPLETE`].
- Stage is `implementation` or `review_fixes` [`GATE_WRONG_STAGE`].
- No unresolved state blockers [`GATE_BLOCKERS`].
- `docs/ai-context/implementation-summary.md` exists [`GATE_NO_SUMMARY`].
- Secret scan clean over changed + staged + untracked files
  [`GATE_SECRET`].

## Attested (verify yourself, record in the summary)

- Every required validation ran; required tests passed — with real output.
- `git diff` contains **only** task-related changes (inspect
  `bin/frappe-workflow git changed-files`; unrelated modifications are a
  stop-and-report).
- No debug code (`print`, `console.log`, `frappe.msgprint` debugging,
  commented-out experiments) and no temporary files remain.
- `docs/ai-context/PROJECT_CONTEXT.md` updated when the task changed
  architecture (per the
  project-context skill's update rules).
- `docs/ai-context/FEATURE_CHANGELOG.md` **not** updated yet.
- A skipped required step fails the gate — there is no such thing as a
  completed task with a skipped required step.

## Building the Summary

Create `docs/ai-context/implementation-summary.md` from
`templates/review/IMPLEMENTATION_SUMMARY.md`: completed task, plan
completion counts, files created/modified (with why), exact test commands,
real results, deviations, known limitations.

## Then

`bin/frappe-workflow review bundle` records the implementation fingerprint
and writes `round-NNN-prompt.md`; the router transitions to `codex_review`.
Fingerprint semantics live in
`skills/codex-review/references/approval-invalidation.md`.
