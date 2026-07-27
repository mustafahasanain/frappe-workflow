# Task File Staging

## Build the Staging Set

Start from `bin/frappe-workflow git changed-files` and the plan's Expected
Files. The staging set is exactly:

- Implementation files the approved task created/modified.
- The tracked finalization docs touched this task:
  `TASK_PLAN.md`, `FEATURE_CHANGELOG.md`, and `PROJECT_CONTEXT.md` when it
  was updated.

## Generate Exact Commands

```bash
git add -- path/to/file.py
git add -- path/to/file.js
git add -- TASK_PLAN.md FEATURE_CHANGELOG.md PROJECT_CONTEXT.md
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
  .claude/task-workflow.json        (local workflow state, ignored)
  .claude/reviews/                  (review history, ignored)
  sites-notes.txt                   (untracked, unrelated to this task)
```

## Hard Rules

- Never `git add .`, `git add -A`, `git add --all`.
- Never stage `.claude/` local state or `deployment.local.json` (the
  security scanner also blocks these by filename).
- Never stage a file the task didn't touch.
- **Already-staged unrelated files** (someone else's `git add`): stop,
  report them, and wait — do not unstage them, do not commit.
- Do not amend existing commits unless explicitly requested; never
  force-push.

## Execution Boundary

Everything above is preparation and is always shown to the user. The
`git add` and `git commit` commands run **only** when the user explicitly
asks Claude Code to create the commit now. "Prepare the commit" is not
consent to execute it. After execution, verify per
[finalization-gate.md](finalization-gate.md) §Commit Verification.
