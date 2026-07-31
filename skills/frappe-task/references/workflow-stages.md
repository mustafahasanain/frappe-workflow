# Workflow Stages

The nine stages of a task's life. The persisted `current_stage` in
`docs/ai-context/task-workflow.json` is authoritative; Git only corroborates it.

## planning

Entered at `start` (or state init). `docs/ai-context/TASK_PLAN.md` is
being created or
validated. No implementation happens here. Exit: planning gate passes →
`implementation`.

Owner: task-planning skill.

## implementation

The approved plan is executed step by step; step statuses live in
`docs/ai-context/TASK_PLAN.md`, aggregate counts in state. Self-transition
(`implementation → implementation`) records notable progress events.
Exit: completion gate passes and a review bundle is generated →
`codex_review`.

Owner: task-implementation skill.

## codex_review

A review prompt for the current fingerprint exists at
`docs/ai-context/reviews/round-NNN-prompt.md`. The workflow waits for the user to
bring back Codex's verdict via `apply-review`. Nothing may modify
implementation files in this stage (that would desynchronize the
fingerprint).

Exit: `CHANGES_REQUIRED` → `review_fixes`; valid `APPROVED` with matching
fingerprint → finalization → `ready_for_commit`.

Owner: codex-review skill.

## review_fixes

Findings from `round-NNN-result.md` are validated against the repository
and fixed; tests rerun; the implementation summary updated. Self-transition
allowed for multi-finding progress. Exit: new bundle for the next round →
`codex_review`.

Owner: codex-review skill (fix loop) + task-implementation skill (edits).

## ready_for_commit

Approval is valid and finalization ran:
`docs/ai-context/FEATURE_CHANGELOG.md` updated,
`docs/ai-context/PROJECT_CONTEXT.md` updated when architecture changed,
plan status
`codex_approved`, review record added. Any code/behavior change here
invalidates approval → back to `review_fixes` (the only backward
transition in the engine). Exit: user explicitly executes the prepared
commit → `committed`.

Owner: git-finalization skill.

## committed

The task commit exists and was verified (hash recorded, files match the
task). The deploy question is asked exactly once per arrival here.
Exit: user chooses deploy → `deployed`; skip → `deployment_skipped`.

Owner: deployment skill (question + execution).

## deployment_skipped

Terminal-adjacent: deployment.status = "skipped" with a reason. The testing
task may be generated, with the separate English warning about publishing
only after the changes reach the testing environment. Exit → `completed`.

## deployed

Server HEAD equals the task commit, required bench commands succeeded,
results recorded. Exit → `completed` after the testing task is generated.

Owner: deployment skill → testing-task skill.

## completed

The task is closed: testing task generated, state final. A new `start`
may now replace `docs/ai-context/TASK_PLAN.md`. No transitions out; a new
task begins with
a fresh state (`start`).

## Controlled Reset

Not a stage transition: a confirmed `reset` re-initializes state
(`state init --force`) and clears only active-task files (see
`references/file-lifecycle.md`).
