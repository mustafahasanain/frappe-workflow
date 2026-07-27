# Canonical `help` Output

The `help` action is **read-only**. It prints the block below and touches
nothing else: no environment detection, no state read or write, no Git
commands, no file creation.

Reproduce this text verbatim. Do not improvise action descriptions, do not
rename or invent workflow stages, and do not summarize the block into a
shorter table — the wording below is the specification, not a suggestion.

```text
Frappe Workflow — /frappe-workflow:frappe-task
==============================================

Usage:
  /frappe-workflow:frappe-task [action] [input]

Running the command with no action resumes the active task from its
persisted workflow stage, recorded in .claude/task-workflow.json.

Actions:

  init          Initialize the current Frappe application: detect the
                bench, application, and available Sites; generate or
                validate PROJECT_CONTEXT.md and FEATURE_CHANGELOG.md; and
                prepare local workflow storage. Does not start a task.

  start         Accept a prepared plan or a plain task description and
                generate a validated, repository-aware TASK_PLAN.md.

  status        Report the current task, stage, implementation progress,
                review round, commit, deployment, blockers, and any
                state/repository inconsistencies. Read-only.

  review        Validate the completion gate and generate a Codex review
                prompt. Codex is not run automatically — you run the
                prompt yourself and bring the result back.

  apply-review  Process a Codex result of APPROVED or CHANGES_REQUIRED,
                record the review round, and route the workflow:
                CHANGES_REQUIRED goes to review_fixes; a valid APPROVED
                goes to ready_for_commit.

  commit        Prepare a Conventional Commit message and the exact
                staging commands. The commit is executed only when you
                explicitly ask for it.

  deploy        Ask whether to deploy or skip, then run the safe
                deployment procedure. No SSH connection is opened before
                you answer.

  testing       Generate a concise Arabic testing-team title and
                description from the approved implemented behavior.

  reset         Reset the active task workflow state after explicit
                confirmation. Never touches Git history, application
                files, PROJECT_CONTEXT.md, or FEATURE_CHANGELOG.md.

  help          Show this message. Read-only.

Workflow stages:

  planning
  implementation
  codex_review
  review_fixes
  ready_for_commit
  committed
  deployment_skipped
  deployed
  completed

Normal workflow:

  planning
  → implementation
  → codex_review
  → review_fixes when changes are required
  → codex_review until approved
  → ready_for_commit
  → committed
  → deployed or deployment_skipped
  → completed

Examples:

  /frappe-workflow:frappe-task init
  /frappe-workflow:frappe-task start Add Telegram reporting
  /frappe-workflow:frappe-task status
  /frappe-workflow:frappe-task review
  /frappe-workflow:frappe-task apply-review
  /frappe-workflow:frappe-task
```

## Rules

- The nine stage names above are the only ones that may appear. Never
  print an invented stage such as `in_review`, `awaiting_review`,
  `in_progress`, or `done`.
- `init` initializes the application; it never starts a task. `start` is
  what creates a task.
- `review` generates a prompt; the plugin never runs Codex itself.
- Never truncate a description mid-sentence. Every line above is complete
  as written.
- Do not run the helper CLI, read state, or inspect Git to render help.
  Help works even when no bench, application, or task exists.
