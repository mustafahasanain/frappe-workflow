# File Lifecycle

Which files live where, who tracks them, and when each may change.

## Plugin Repository Files (this repository)

Everything under `frappe-workflow/` — skills, references, templates,
`scripts/`, `bin/`, `hooks/`, `tests/`, `docs/`. These ship with the plugin
and are never generated into a target application.

## Files Generated in a Target Frappe Application

```text
<app-repository>/
├── PROJECT_CONTEXT.md            tracked
├── FEATURE_CHANGELOG.md          tracked
├── TASK_PLAN.md                  tracked
└── .claude/
    ├── task-workflow.json        local, ignored
    ├── deployment.local.json     local, ignored (user-created from template)
    ├── implementation-summary.md local, ignored
    ├── testing-task-ar.md        local, ignored
    └── reviews/                  local, ignored
        ├── round-001-prompt.md
        └── round-001-result.md
```

The ignored set is maintained through the managed `.gitignore` block:

```gitignore
# BEGIN Frappe Workflow Plugin local state
.claude/task-workflow.json
.claude/deployment.local.json
.claude/implementation-summary.md
.claude/testing-task-ar.md
.claude/reviews/
# END Frappe Workflow Plugin local state
```

Managed-block rules: never replace the whole `.gitignore`; preserve every
existing line; never add the block twice; repair the block only when the
markers are balanced and unique; report conflicting entries instead of
guessing.

## When Each File Changes

| File | Created | Updated | Replaced | Reset |
|---|---|---|---|---|
| `PROJECT_CONTEXT.md` | `init` (first full analysis) | Only when architecture/navigation changed (finalization) or incremental re-analysis | Only when missing/invalid/clearly obsolete | Never by `reset` |
| `FEATURE_CHANGELOG.md` | `init` (baseline discovery) | Only after a valid Codex `APPROVED` (finalization) | Never | Never by `reset` |
| `TASK_PLAN.md` | `start` | Step statuses during implementation; metadata at finalization | A **completed** task's plan may be replaced by the next task's plan; an unfinished one requires an explicit decision | Cleared only by confirmed `reset` |
| `.claude/task-workflow.json` | `start` (or `state init`) | Every stage/status change, atomically | By confirmed `reset` only | Yes, confirmed `reset` |
| `.claude/deployment.local.json` | By the **user** from the example template | By the user | — | Never deleted by the plugin |
| `.claude/implementation-summary.md` | Completion gate preparation | Each review-fix round | New task | Confirmed `reset` |
| `.claude/reviews/round-NNN-*.md` | `review` / `apply-review` | Never (append-only history; original results preserved) | — | Confirmed `reset` |
| `.claude/testing-task-ar.md` | `testing` | Regenerated on request | New task | Confirmed `reset` |

## Archival

Review rounds are append-only within a task. When a new task starts after a
completed one, the previous `.claude/reviews/` contents belong to the old
task; the `start` action reports them and offers to clear them as part of
starting fresh (never silently).

## What `reset` Never Touches

Git changes, Git commits, application source files, `PROJECT_CONTEXT.md`,
`FEATURE_CHANGELOG.md`, `.claude/deployment.local.json`, repository history.
