---
name: git-finalization
description: Post-approval finalization and commit preparation - finalization gate, documentation timing, Conventional Commit message generation, exact staging commands, and commit verification.
user-invocable: false
---

# Git Finalization Skill

Turns an approved implementation into a verified task commit. Prepares
everything; **executes the commit only when the user explicitly asks**.

## When to Use

- Right after a valid `APPROVED` (finalization: documentation updates +
  gate) — invoked from the codex-review flow.
- The `commit` action (stage `ready_for_commit`).
- Resuming into `ready_for_commit`.

## Inputs

- Approved state (fingerprint recorded), `TASK_PLAN.md`, the actual diff,
  `bin/frappe-workflow git inspect` / `changed-files`.

## Outputs

- Finalized docs: `FEATURE_CHANGELOG.md` updated (feature-changelog
  skill), `PROJECT_CONTEXT.md` when architecture changed (project-context
  skill), `TASK_PLAN.md` status `codex_approved` + review record.
- A prepared commit: Conventional Commit subject (+ optional body), exact
  `git add -- <path>` commands, excluded-files list.
- After user-requested execution: verified commit, hash/subject recorded,
  stage `committed`.

## Procedure

Gate: [references/finalization-gate.md](references/finalization-gate.md).
Message: [references/conventional-commits.md](references/conventional-commits.md).
Staging: [references/task-file-staging.md](references/task-file-staging.md).

## Preconditions

- `bin/frappe-workflow validate finalization-gate` passes (approval valid,
  fingerprint matches, secret scan clean).

## Stopping Conditions

- Commit executed and verified → record hash/subject,
  `state transition committed`, hand to the deployment question. Done.
- User has not asked to execute → stop after presenting the prepared
  commit; the workflow waits.
- Unrelated files already staged → stop and report (never commit around
  them).

## Prohibited

- `git add .` / `-A` in any form; staging `.claude/` state, deployment
  config, or unrelated files.
- Executing the commit without an explicit user request this session.
- `--amend` (unless the user explicitly asks and nothing was pushed),
  force-push, AI attribution (`Co-Authored-By`, `Claude`, `Codex`,
  `AI-generated`) in the message.
- Updating documentation outside this finalization window.

## Shared Rules

[git-safety-rules.md](../../references/git-safety-rules.md),
[security-rules.md](../../references/security-rules.md),
[shared-workflow-rules.md](../../references/shared-workflow-rules.md).
