# Usage

Everything runs through one command:

```text
/frappe-workflow:frappe-task [action] [input]
```

With no action, the workflow continues from its persisted stage — that is
how you resume after closing and reopening Claude Code.

## Actions

| Action | What it does |
|---|---|
| *(none)* | Resume the active task from its persisted workflow stage |
| `init` | Initialize the application: detect bench/app/Sites, migrate an older file layout, generate or validate `docs/ai-context/PROJECT_CONTEXT.md` and `docs/ai-context/FEATURE_CHANGELOG.md`, prepare shared workflow storage. Does not start a task |
| `start` | Accept a prepared plan or a task description and generate a validated, repository-aware `docs/ai-context/TASK_PLAN.md` |
| `status` | Read-only report of task, stage, progress, review, commit, deployment, blockers, and inconsistencies |
| `review` | Validate the completion gate and generate a Codex review prompt (Codex is not run automatically) |
| `apply-review` | Process an `APPROVED` or `CHANGES_REQUIRED` result, record the review round, and route to `review_fixes` or `ready_for_commit` |
| `commit` | Prepare the Conventional Commit and exact staging commands (executes only when you say so) |
| `deploy` | Ask deploy-or-skip, then run the safe deployment procedure |
| `testing` | Generate a concise Arabic testing-team title and description from the approved behavior |
| `reset` | Controlled reset of active-task state after confirmation |
| `help` | Print the canonical action list, stages, and workflow. Read-only |

## A Typical Task

```text
/frappe-workflow:frappe-task init
/frappe-workflow:frappe-task start Add Telegram reporting
/frappe-workflow:frappe-task status
/frappe-workflow:frappe-task review
/frappe-workflow:frappe-task apply-review
/frappe-workflow:frappe-task commit
/frappe-workflow:frappe-task deploy
/frappe-workflow:frappe-task testing
```

`init` runs once per application. Everything after it repeats per task.

## Two Kinds of Input to `start`

### A prepared plan

Paste a plan you already wrote (in ChatGPT, a ticket, or anywhere else):

```text
/frappe-workflow:frappe-task start
Plan: add a daily Telegram sales summary.
1. Build the summary from yesterday's submitted invoices.
2. Register a daily scheduler event that sends it.
```

The plan is treated as **input, not truth**. Before it becomes
`docs/ai-context/TASK_PLAN.md`, the plugin reads
`docs/ai-context/PROJECT_CONTEXT.md`, searches
`docs/ai-context/FEATURE_CHANGELOG.md`, verifies every path against the
repository, adds
missing technical steps (validation, migration, security), and reports each
correction it made. What it will not do silently is change your business
objective, add unrelated features, or widen the scope.

### A description only

```text
/frappe-workflow:frappe-task start Sales orders should also reserve stock
```

The repository is analyzed, existing features are searched, and a full plan
is drafted for you before any implementation starts.

### Complete projects

For greenfield work, the plan uses `task_type: project` and additionally
covers modules, DocType design, relationships, permissions, APIs,
integrations, jobs, reports, audit, error handling, phases, MVP scope, and
deferred features. Only the MVP phase gets implementation steps in the
current task — later phases become their own tasks.

## Files Created in Your Application

```text
<app-repository>/
├── docs/ai-context/                  tracked — shared AI context
│   ├── PROJECT_CONTEXT.md            navigation and architecture map
│   ├── FEATURE_CHANGELOG.md          functional feature registry
│   ├── TASK_PLAN.md                  the one active task
│   ├── task-workflow.json            logical workflow state
│   ├── implementation-summary.md     what was actually built
│   ├── testing-task-ar.md            the Arabic testing task
│   └── reviews/                      round-NNN-prompt.md / round-NNN-result.md
└── .claude/                          local, ignored
    ├── deployment.local.json         your deployment config (you create it)
    └── task-workflow.lock            advisory write lock
```

Only those two `.claude/` files are ignored, through a managed block in your
`.gitignore`; the rest of that file is never touched. Details in
[../references/file-lifecycle.md](../references/file-lifecycle.md).

## Continuing a Task on Another Computer

Because `docs/ai-context/` is tracked, an unfinished task is portable:

1. On the first computer, commit the shared files on the working branch and
   push. A work-in-progress checkpoint commit is fine for this.
2. On the second computer, pull or check out that branch.
3. Run `/frappe-workflow:frappe-task` with no action — it resumes from
   `docs/ai-context/task-workflow.json` at the recorded stage.

Taking these files out of `.gitignore` makes them *trackable*, not
*synchronized*: Git commit, push, and pull are still required, and the
plugin never performs any of them for you. `.claude/deployment.local.json`
stays specific to each computer and is created separately on each.

## Migrating an Application from the Old Layout

Applications initialized before this layout keep `PROJECT_CONTEXT.md`,
`FEATURE_CHANGELOG.md`, and `TASK_PLAN.md` at the repository root and the
workflow files under `.claude/`. The `init` action migrates them; you can
also run it directly:

```bash
bin/frappe-workflow project migrate --dry-run   # report what would move
bin/frappe-workflow project migrate             # move it
```

Contents and the full review history are preserved, old entries are removed
from the managed `.gitignore` block, `.claude/deployment.local.json` is
never touched, and rerunning it does nothing. If a path exists in **both**
layouts the command stops with `MIGRATE_CONFLICT` (exit 1) without moving
anything, so you decide which copy is current.

## What Requires Your Explicit Approval

- Replacing an unfinished task (finish it or `reset` first).
- Choosing a Site when the app is installed on more than one.
- Creating a Site or installing an app on one — never automatic.
- Executing the prepared commit.
- Deploying (no SSH connection is opened before you answer).
- Any reset.

## Helper CLI

The skills call a deterministic helper for anything that should not be
guessed. You can run it yourself:

```bash
bin/frappe-workflow detect [--json]

bin/frappe-workflow state show
bin/frappe-workflow state init [--force]
bin/frappe-workflow state set <dotted.path> <value> [--json-value]
bin/frappe-workflow state transition <stage> [--reason TEXT]
bin/frappe-workflow state blocker add <message>
bin/frappe-workflow state blocker clear

bin/frappe-workflow validate project-context
bin/frappe-workflow validate feature-changelog
bin/frappe-workflow validate task-plan
bin/frappe-workflow validate workflow-state
bin/frappe-workflow validate completion-gate
bin/frappe-workflow validate finalization-gate

bin/frappe-workflow feature search <query>
bin/frappe-workflow feature next-id --type <TYPE> --module <MODULE>
bin/frappe-workflow feature validate-index

bin/frappe-workflow git inspect
bin/frappe-workflow git fingerprint
bin/frappe-workflow git changed-files

bin/frappe-workflow review bundle
bin/frappe-workflow review fingerprint
bin/frappe-workflow review parse-result <file>

bin/frappe-workflow deployment validate-config
bin/frappe-workflow deployment preflight
bin/frappe-workflow deployment required-commands [--commit <hash>]
bin/frappe-workflow deployment verify --expected <hash> --server-head <hash>

bin/frappe-workflow security scan

bin/frappe-workflow project paths
bin/frappe-workflow project ensure-gitignore
bin/frappe-workflow project migrate [--dry-run]
```

Global options: `--repo <path>` (target repository, default: current
directory) and `--json` (machine-readable output on stdout).

`state set` writes one field that already exists in the schema, atomically,
re-validating the whole file before it lands:

```bash
bin/frappe-workflow state set codex_review.status approved
bin/frappe-workflow state set codex_review.round 2 --json-value   # int, not "2"
bin/frappe-workflow state set commit.hash 4f2c9ab
```

A typo is an error rather than a new junk key, and four paths are refused
because a dedicated operation enforces a rule a raw write would bypass:
`current_stage` (use `state transition`), `blockers` (use `state blocker`),
`transition_history`, and `schema_version`.

`project paths` prints every managed location as JSON, so scripts and
skills never hard-code one:

```bash
bin/frappe-workflow project paths
```

`project ensure-gitignore` writes or repairs the managed `.gitignore` block
idempotently, and `project migrate` moves an old-layout application onto
`docs/ai-context/`. Both are run by the `init` action.

### Exit Codes

```text
0 = success
1 = validation failure
2 = invalid usage
3 = environment detection failure
4 = unsafe repository state
5 = workflow transition rejected
6 = deployment preflight failure
7 = security scan failure
```

Errors always go to stderr; validation-only commands never mutate state;
secrets are never printed (values are redacted to `abc...xyz`).

## Resuming Work

Closing Claude Code loses nothing. Reopen it in the application directory
and run the command with no action: the state file is validated,
cross-checked against Git, and work continues from the recorded stage. If
something is genuinely inconsistent — say the recorded commit no longer
exists — the plugin stops and tells you exactly what it found instead of
guessing.

The same applies across computers: because
`docs/ai-context/task-workflow.json` is committed with the branch, pulling
that branch on a second machine and running the command with no action
resumes the task there. See
[Continuing a Task on Another Computer](#continuing-a-task-on-another-computer).
