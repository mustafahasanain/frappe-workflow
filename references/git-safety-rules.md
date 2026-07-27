# Git Safety Rules

These rules apply locally and on any deployment server. The safety hook
(`hooks/hooks.json`) additionally blocks the destructive commands at the
tool level.

## Read-Only Commands (always allowed)

```bash
git status --porcelain
git branch --show-current
git rev-parse HEAD
git rev-parse <remote>/<branch>
git diff / git diff --cached / git diff --name-only
git log
git show --name-only <commit>
git ls-files --others --exclude-standard
git remote -v
git fetch <remote>          # updates remote refs only; no working-tree change
git merge-base --is-ancestor A B
```

## Allowed Non-Destructive Commands

- `git add -- <explicit path>` — exact paths only.
- `git commit` — only when the user explicitly asks to create it now.
- `git checkout -b <branch>` — creating a new branch for the task.
- `git pull --ff-only <remote> <branch>` — the only allowed pull form on a
  deployment server, and only after preflight passes.

## Disallowed Destructive Commands

Never run, locally or remotely:

```text
git reset --hard
git clean -fd / -fdx (any file-deleting clean)
git push --force / git push -f / --force-with-lease
git checkout -- .
git restore .
git branch -D on branches with unmerged work
history rewrites (rebase/amend of pushed commits)
```

`git commit --amend` is allowed only when the user explicitly requests it
and the commit has not been pushed.

## Exact Staging Rules

- Generate one `git add -- <path>` per task-related file (paths may be
  grouped in a single command, but every path is explicit).
- **Never** `git add .`, `git add -A`, or `git add --all` by default.
- Never stage: `.claude/` local state, `deployment.local.json`, credentials,
  `.env` files, or anything unrelated to the approved task.
- List intentionally excluded files so the user can see what was left out.
- If unrelated files are **already staged**, stop and report them; do not
  commit around them and do not unstage them silently.

## Remote and Branch Verification

Before any push- or pull-adjacent operation:

- Verify the remote exists (`git remote -v`) and matches the deployment
  configuration.
- Verify the branch name matches the task state.
- Verify the expected commit exists on the expected remote before asking a
  server to fetch it.

## Server Repository Safety

On the deployment server the repository is treated as append-only:

- Fast-forward pulls only (`git pull --ff-only`).
- A dirty server working tree stops the deployment — never stash, reset,
  clean, or checkout another branch to "fix" it.
- Diverged history stops the deployment; a human resolves it.
