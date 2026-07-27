# Shared Workflow Rules

Rules that apply to every skill in this plugin.

## Source-of-Truth Hierarchy

When sources disagree, trust them in this order:

1. **The repository itself** — actual code, actual paths, actual Git history.
2. **`.claude/task-workflow.json`** — the logical workflow state (stage,
   review rounds, fingerprints, commit status).
3. **`TASK_PLAN.md`** — what was agreed for the active task.
4. **`PROJECT_CONTEXT.md` / `FEATURE_CHANGELOG.md`** — navigation and
   feature history; useful, but re-verify against code before acting.
5. **User-provided plans or descriptions** — input to validate, never
   unquestionable truth.

Git verifies that the recorded logical state is still truthful; it does not
replace it (Git cannot tell whether a plan was approved or a review passed).

## Workflow Stage Rules

- The only stages are: `planning`, `implementation`, `codex_review`,
  `review_fixes`, `ready_for_commit`, `committed`, `deployment_skipped`,
  `deployed`, `completed`.
- Stage changes happen only through
  `bin/frappe-workflow state transition <stage>`, which enforces the allowed
  transition table (see `skills/frappe-task/references/state-transitions.md`).
- Never edit `current_stage` by hand and never skip a gate to "save time".

## How State Is Written

Never hand-edit `.claude/task-workflow.json`. Every write goes through the
CLI so it stays atomic and validated:

```bash
bin/frappe-workflow state set <dotted.path> <value> [--json-value]
bin/frappe-workflow state transition <stage> --reason "<why>"
bin/frappe-workflow state blocker add "<exact reason>"
bin/frappe-workflow state blocker clear
```

`state set` only accepts paths that already exist in the schema (a typo is
an error, not a new key) and refuses `current_stage`, `blockers`,
`transition_history`, and `schema_version` — each of those has a dedicated
operation that enforces a rule a raw write would bypass. Use `--json-value`
when the field is a number, boolean, or null.

## Repository Verification Requirements

- Never assert a path, DocType, hook, or Site exists without checking.
- Plan steps whose location is unverified must say
  `Requires repository verification` and be verified before implementation.
- Detection results (bench, app, sites) come from
  `bin/frappe-workflow detect --json`, not from memory.

## No Silent Scope Changes

- The business objective in `TASK_PLAN.md` is fixed once planning completes.
- Technical corrections (wrong path, missing validation step, missing
  migration) may be added and must be recorded in the plan.
- Adding features, changing the objective, or expanding product scope
  requires explicit user awareness and a plan update first.

## No Invented Results

- Never claim a test passed without running it and reading the output.
- Never invent Frappe paths, Sites, DocTypes, hooks, or review findings.
- Never fabricate feature history during baseline analysis.
- If something was not done, the record says it was not done.

## No Skipped Gates

- Codex review requires the completion gate
  (`bin/frappe-workflow validate completion-gate`) to pass.
- Commit preparation requires the finalization gate
  (`bin/frappe-workflow validate finalization-gate`) to pass.
- A blocked or pending plan step fails the completion gate; there is no
  override flag.

## Context and Feature-Changelog Timing

- `PROJECT_CONTEXT.md` is updated only when a future agent would otherwise
  misunderstand the project or inspect the wrong files.
- `FEATURE_CHANGELOG.md` is **never** updated during implementation — only
  after Codex returns a valid `APPROVED` (see the feature-changelog skill).

## User Approval Boundaries

The user must explicitly decide (the workflow never assumes):

- Replacing an unfinished task (reset or complete first).
- Selecting a Site when multiple candidates exist.
- Creating a Site or installing an app on a Site (never automatic).
- Executing the prepared Git commit.
- Deploying or skipping deployment.
- Any controlled reset.
