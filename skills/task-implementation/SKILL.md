---
name: task-implementation
description: Execute the approved TASK_PLAN.md step by step - status updates, per-step validation, blocker recording, the implementation summary, and the completion gate before Codex review.
user-invocable: false
---

# Task Implementation Skill

Executes the approved plan during the `implementation` stage (and applies
fixes during `review_fixes`). One step at a time, validated before marked
done.

## When to Use

- Stage `implementation`: next non-completed plan step.
- Stage `review_fixes`: applying validated Codex findings (the codex-review
  skill decides *what*; this skill governs *how* edits are made and
  validated).

## Inputs

- `docs/ai-context/TASK_PLAN.md` (authoritative step list and statuses).
- Workflow state (aggregate counts, blockers).
- The repository.

## Outputs

- Implemented, validated changes; step statuses updated in the plan;
  state counts synced (`total_steps` / `completed_steps` / `blocked_steps`).
- `docs/ai-context/implementation-summary.md` (template:
  `templates/review/IMPLEMENTATION_SUMMARY.md`) when all steps complete.

## Procedure

Per-step loop: [references/implementation-loop.md](references/implementation-loop.md).
Validation rules: [references/step-validation.md](references/step-validation.md).
Gate before review: [references/completion-gate.md](references/completion-gate.md).

## Preconditions

- Stage is `implementation` or `review_fixes`; plan validates.

## Stopping Conditions

- All steps `Completed` and the completion gate passes → hand to the
  codex-review skill (`review` action).
- A step blocks → record it (plan + `state blocker add`), keep stage
  `implementation`, report to the user. Do not continue past a blocking
  dependency.

## Prohibited

- Marking a step `Completed` before its validation succeeded.
- Skipping a step silently, or marking partial work complete.
- Updating `docs/ai-context/FEATURE_CHANGELOG.md` (finalization-only).
- Unrecorded deviation from the plan: small technical deviations that
  preserve the objective are documented in the summary; business scope
  changes stop the work and go back to planning with the user's awareness.
- Reading the whole repository — read only files the current step needs.

## Shared Rules

[shared-workflow-rules.md](../../references/shared-workflow-rules.md),
[error-and-blocker-handling.md](../../references/error-and-blocker-handling.md),
[git-safety-rules.md](../../references/git-safety-rules.md).
