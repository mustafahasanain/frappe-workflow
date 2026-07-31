# File Lifecycle

Which files live where, who tracks them, and when each may change.

## Plugin Repository Files (this repository)

Everything under `frappe-workflow/` — skills, references, templates,
`scripts/`, `bin/`, `hooks/`, `tests/`, `docs/`. These ship with the plugin
and are never generated into a target application.

## Files Generated in a Target Frappe Application

Every shared file lives under `docs/ai-context/` and is meant to be
committed, so an active task can continue on another computer. Only
genuinely machine-specific state stays under `.claude/`.

```text
<app-repository>/
├── docs/
│   └── ai-context/
│       ├── PROJECT_CONTEXT.md          tracked
│       ├── FEATURE_CHANGELOG.md        tracked
│       ├── TASK_PLAN.md                tracked
│       ├── task-workflow.json          tracked (workflow state)
│       ├── implementation-summary.md   tracked
│       ├── testing-task-ar.md          tracked
│       └── reviews/                    tracked
│           ├── round-001-prompt.md
│           └── round-001-result.md
└── .claude/
    ├── deployment.local.json           local, ignored (user-created from template)
    └── task-workflow.lock              local, ignored (advisory write lock)
```

The ignored set is maintained through the managed `.gitignore` block, and it
contains **only** the two machine-local files:

```gitignore
# BEGIN Frappe Workflow Plugin local state
.claude/deployment.local.json
.claude/task-workflow.lock
# END Frappe Workflow Plugin local state
```

Managed-block rules: never replace the whole `.gitignore`; preserve every
existing line; never add the block twice; repair the block only when the
markers are balanced and unique; report conflicting entries instead of
guessing. Repairing the block also removes entries written by older plugin
versions, which ignored the shared files.

Nothing under `docs/ai-context/` may be added to `.gitignore` — ignoring it
would break cross-device continuation.

## When Each File Changes

| File | Created | Updated | Replaced | Reset |
|---|---|---|---|---|
| `docs/ai-context/PROJECT_CONTEXT.md` | `init` (first full analysis) | Only when architecture/navigation changed (finalization) or incremental re-analysis | Only when missing/invalid/clearly obsolete | Never by `reset` |
| `docs/ai-context/FEATURE_CHANGELOG.md` | `init` (baseline discovery) | Only after a valid Codex `APPROVED` (finalization) | Never | Never by `reset` |
| `docs/ai-context/TASK_PLAN.md` | `start` | Step statuses during implementation; metadata at finalization | A **completed** task's plan may be replaced by the next task's plan; an unfinished one requires an explicit decision | Cleared only by confirmed `reset` |
| `docs/ai-context/task-workflow.json` | `start` (or `state init`) | Every stage/status change, atomically | By confirmed `reset` only | Yes, confirmed `reset` |
| `docs/ai-context/implementation-summary.md` | Completion gate preparation | Each review-fix round | New task | Confirmed `reset` |
| `docs/ai-context/reviews/round-NNN-*.md` | `review` / `apply-review` | Never (append-only history; original results preserved) | — | Confirmed `reset` |
| `docs/ai-context/testing-task-ar.md` | `testing` | Regenerated on request | New task | Confirmed `reset` |
| `.claude/deployment.local.json` | By the **user** from the example template | By the user | — | Never deleted by the plugin |
| `.claude/task-workflow.lock` | Automatically, on the first state write | Held only for the duration of a write | — | Never deleted by `reset`; safe to delete manually |

`init` creates only `docs/ai-context/PROJECT_CONTEXT.md` and
`docs/ai-context/FEATURE_CHANGELOG.md` (plus the directory and the managed
`.gitignore` block). It never creates `TASK_PLAN.md` or `task-workflow.json`
— those belong to `start`.

## Cross-Device Continuation

The shared files are Git-trackable, not Git-synchronized. Moving them out of
`.gitignore` does not move them between computers by itself:

1. On computer A: commit the shared files on the working branch and push.
   A work-in-progress checkpoint commit is a normal way to do this.
2. On computer B: pull, or check out that branch.
3. Resume with `/frappe-workflow:frappe-task` and no action — it reads
   `docs/ai-context/task-workflow.json` from the branch.

`.claude/deployment.local.json` is specific to each computer and is created
separately on each. The plugin never commits, pushes, or pulls on its own.

## Legacy Layout Migration

Applications initialized before this layout keep `PROJECT_CONTEXT.md`,
`FEATURE_CHANGELOG.md`, and `TASK_PLAN.md` at the repository root and the
workflow files under `.claude/`. `bin/frappe-workflow project migrate` (run
by `init`) moves each old path to its new one, preserving contents and the
full review history, and then repairs the managed `.gitignore` block. It is
idempotent, never touches `.claude/deployment.local.json`, and aborts
without moving anything when a path exists in both layouts.

## Archival

Review rounds are append-only within a task. When a new task starts after a
completed one, the previous `docs/ai-context/reviews/` contents belong to
the old task; the `start` action reports them and offers to clear them as
part of starting fresh (never silently).

## What `reset` Never Touches

Git changes, Git commits, application source files,
`docs/ai-context/PROJECT_CONTEXT.md`,
`docs/ai-context/FEATURE_CHANGELOG.md`, `.claude/deployment.local.json`,
repository history.
