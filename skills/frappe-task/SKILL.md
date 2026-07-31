---
name: frappe-task
description: End-to-end Frappe/ERPNext task workflow - plan, implement, review with Codex, commit, deploy, and hand off to testing. User-invoked only.
disable-model-invocation: true
argument-hint: "[init|start|status|review|apply-review|commit|deploy|testing|reset|help] [task description or input]"
---

# Frappe Task Workflow

You are the orchestrator of a staged Frappe development workflow. You route
actions, enforce gates, and delegate detailed work to the internal skills.
Keep this file's rules loaded; read the referenced files **only when the
current action needs them** (progressive disclosure).

## Parse the Arguments

`$ARGUMENTS` — the first whitespace-separated token is the action; everything
after it is the action input.

Recognized actions: `init`, `start`, `status`, `review`, `apply-review`,
`commit`, `deploy`, `testing`, `reset`, `help`.

- **No arguments** → resume the active task from its persisted workflow
  stage, recorded in `docs/ai-context/task-workflow.json`. This is how work
  continues after Claude Code is closed and reopened.
- **First token not a recognized action** → see "Unknown input" in
  [references/command-routing.md](references/command-routing.md).

## Ground Rules (always)

- Read [../../references/shared-workflow-rules.md](../../references/shared-workflow-rules.md)
  before acting on any workflow-mutating action.
- All deterministic facts come from the helper CLI at
  `${CLAUDE_PLUGIN_ROOT}/bin/frappe-workflow` (detection, state, gates,
  fingerprints, IDs, scans). Never guess what it can compute.
- The workflow state file `docs/ai-context/task-workflow.json` in the
  **target app repository** is the primary logical state; Git verifies it.
  Stage changes go only through `bin/frappe-workflow state transition
  <stage>`.
- Every shared workflow file lives under `docs/ai-context/` and is
  Git-trackable, so an active task can continue on another computer after
  the user commits and pushes the working branch. Only
  `.claude/deployment.local.json` and `.claude/task-workflow.lock` stay
  machine-local. Never commit, push, or pull automatically.
- The nine canonical stages are `planning`, `implementation`,
  `codex_review`, `review_fixes`, `ready_for_commit`, `committed`,
  `deployment_skipped`, `deployed`, `completed`. Never name a stage that is
  not on this list, in output or in state.
- Never commit, push, open SSH, or deploy without the explicit user
  confirmation each of those steps requires.

## Routing

Full per-action procedures: [references/command-routing.md](references/command-routing.md).
Stage semantics: [references/workflow-stages.md](references/workflow-stages.md).
Allowed transitions: [references/state-transitions.md](references/state-transitions.md).
Gates: [references/workflow-gates.md](references/workflow-gates.md).

What each action does, and which skill owns it. These descriptions are
user-facing and must stay accurate — `help` prints them (verbatim, from
[examples/help-output.md](examples/help-output.md)), so a wrong
description here becomes a wrong answer to the user.

| Action | What it does | Delegate to |
|---|---|---|
| (none) | Resume the active task from its persisted stage | — (see command-routing.md §No Action) |
| `init` | Initialize the application: detect bench/app/Sites, generate or validate `docs/ai-context/PROJECT_CONTEXT.md` and `docs/ai-context/FEATURE_CHANGELOG.md`, migrate a legacy layout, and prepare shared workflow storage. **Never starts a task.** | project-context + feature-changelog skills |
| `start` | Accept a prepared plan or a task description; produce a validated, repository-aware `docs/ai-context/TASK_PLAN.md` | task-planning skill |
| `status` | Read-only report of task, stage, progress, review, commit, deployment, blockers, inconsistencies | — (see examples/status-output.md) |
| `review` | Validate the completion gate and generate a Codex review prompt. **Codex is never run automatically.** | codex-review skill |
| `apply-review` | Process an `APPROVED` or `CHANGES_REQUIRED` result, record the review round, route to `review_fixes` or `ready_for_commit` | codex-review skill |
| `commit` | Prepare the Conventional Commit message and exact staging commands; execute only on explicit request | git-finalization skill |
| `deploy` | Ask deploy-or-skip, then run the safe deployment procedure | deployment skill |
| `testing` | Generate a concise Arabic testing-team title and description from the approved behavior | testing-task skill |
| `reset` | Reset active task workflow state after explicit confirmation | — (see command-routing.md §reset) |
| `help` | Print the canonical help text, read-only | — (see examples/help-output.md) |

During the `implementation` stage (reached after `start`, or when resuming
into it), follow the task-implementation skill.

## Resuming After Restart

When invoked with no action and state exists: validate it
(`bin/frappe-workflow validate workflow-state`), cross-check against Git,
then resume work from the recorded `current_stage`. On inconsistencies, follow
[../../references/error-and-blocker-handling.md](../../references/error-and-blocker-handling.md) —
stop and report rather than guessing. When **no state exists**, tell the
user to run `/frappe-workflow:frappe-task init`; do not create a task
automatically.
