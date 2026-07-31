# Task File Staging

## Build the Staging Set

Start from `bin/frappe-workflow git changed-files` and the plan's Expected
Files. The staging set is exactly:

- Implementation files the approved task created/modified.
- The shared AI-context files touched this task. They live under
  `docs/ai-context/` and are tracked, so they belong in the task commit:
  `docs/ai-context/TASK_PLAN.md`,
  `docs/ai-context/FEATURE_CHANGELOG.md`,
  `docs/ai-context/PROJECT_CONTEXT.md` when it was updated, and — when the
  user wants the task to continue on another computer —
  `docs/ai-context/task-workflow.json`,
  `docs/ai-context/implementation-summary.md`, and
  `docs/ai-context/reviews/`.

`bin/frappe-workflow project paths` prints these locations
(`tracked_shared_files`) so no path is ever typed from memory.

## Generate Exact Commands

```bash
git add -- path/to/file.py
git add -- path/to/file.js
git add -- docs/ai-context/TASK_PLAN.md docs/ai-context/FEATURE_CHANGELOG.md docs/ai-context/PROJECT_CONTEXT.md
```

- Every path explicit; grouping several paths after one `--` is fine.
- Then the commit command with the generated message:

```bash
git commit -m "feat(stock): add unified temporary stock reservation" -m "- support multiple reference doctypes
- validate reserved quantities against availability"
```

## Always Show the Exclusions

List files present in changed/untracked output that are **intentionally
not staged**, with the reason, e.g.:

```text
Excluded from this commit:
  .claude/deployment.local.json      (machine-local deployment config, ignored)
  .claude/task-workflow.lock         (machine-local write lock, ignored)
  sites-notes.txt                    (untracked, unrelated to this task)
```

## Hard Rules

- Never `git add .`, `git add -A`, `git add --all`.
- Never stage `.claude/deployment.local.json` or
  `.claude/task-workflow.lock` (the security scanner also blocks the
  deployment config by filename).
- Never stage a file the task didn't touch.
- **Already-staged unrelated files** (someone else's `git add`): stop,
  report them, and wait — do not unstage them, do not commit.
- Do not amend existing commits unless explicitly requested; never
  force-push.

## Continuing on Another Computer

Committing `docs/ai-context/` is what makes an unfinished task portable.
Pushing the working branch and pulling it on the second computer is the
whole mechanism — there is no background sync. A work-in-progress
checkpoint commit is a legitimate way to hand a task over mid-flight; say
so when the user asks how to continue elsewhere.

The plugin never commits, pushes, or pulls on its own, and
`.claude/deployment.local.json` is created separately on each computer.

## Execution Boundary

Everything above is preparation and is always shown to the user. The
`git add` and `git commit` commands run **only** when the user explicitly
asks Claude Code to create the commit now. "Prepare the commit" is not
consent to execute it. After execution, verify per
[finalization-gate.md](finalization-gate.md) §Commit Verification.
