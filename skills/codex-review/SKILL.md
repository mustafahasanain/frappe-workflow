---
name: codex-review
description: Codex review lifecycle - build the review bundle, generate the prompt, parse APPROVED/CHANGES_REQUIRED results, run the review-fix loop, and invalidate approval via the implementation fingerprint.
user-invocable: false
---

# Codex Review Skill

Manages the external Codex review of a completed implementation. Codex
reviews only — it never modifies files; the bundle says so explicitly.

## When to Use

- `review` action (stage `implementation`/`review_fixes`, completion gate
  passed) → bundle + prompt
  ([references/review-prompt-generation.md](references/review-prompt-generation.md)).
- `apply-review` action (stage `codex_review`) → parse result
  ([references/review-result-parsing.md](references/review-result-parsing.md)).
- Stage `review_fixes` → fix loop
  ([references/review-fix-loop.md](references/review-fix-loop.md)).
- Any post-approval change →
  ([references/approval-invalidation.md](references/approval-invalidation.md)).

## Inputs

- Passing completion gate; `TASK_PLAN.md`; implementation summary; Git
  state; for `apply-review`, the raw Codex result text or file.

## Outputs

- `.claude/reviews/round-NNN-prompt.md` (via `bin/frappe-workflow review
  bundle`, which secret-scans and embeds the fingerprint).
- `.claude/reviews/round-NNN-result.md` — the original result, preserved
  verbatim.
- State updates: round, prompt/result paths, fingerprint, status
  (pending → changes_required → … → approved), approved_at.

## Preconditions

- Bundle: `validate completion-gate` passes.
- Result parsing: a prompt for the current round exists and state is
  `codex_review`.
- Approval acceptance: current fingerprint == recorded fingerprint.

## Stopping Conditions

- `APPROVED` accepted → finalization (feature-changelog + project-context
  updates, review record) → `validate finalization-gate` →
  `ready_for_commit`. Done.
- `CHANGES_REQUIRED` → `review_fixes`; loop continues until approved.
- Malformed result → reject with the format requirements; stay in
  `codex_review`; never guess a status.

## Prohibited

- Generating a prompt without a passing completion gate.
- Accepting any status other than exactly `APPROVED` / `CHANGES_REQUIRED`.
- Inventing, dropping, or "interpreting away" findings; the original
  result file is never edited.
- Accepting approval whose fingerprint mismatches the working tree.
- Applying a finding without validating it against the repository first.

## Shared Rules

[shared-workflow-rules.md](../../references/shared-workflow-rules.md),
[security-rules.md](../../references/security-rules.md).
