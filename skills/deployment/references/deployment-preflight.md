# Deployment Preflight

## Local Preflight (no SSH)

`bin/frappe-workflow deployment preflight` verifies:

- Config valid (`validate-config`): required fields, types, port 1–65535,
  absolute safe `bench_path`, safe host/user/remote/branch/site strings,
  no credential-looking fields.
- Task consistency: config `app_name` == task app, config `branch` == task
  branch, active task has a verified commit
  [`DEPLOY_APP_MISMATCH`, `DEPLOY_BRANCH_MISMATCH`, `DEPLOY_NO_COMMIT`].

Then verify locally (read-only Git):

- `commit.hash` exists locally (`git rev-parse <hash>`).
- The commit exists on the expected remote:
  `git fetch <remote>` then
  `git branch -r --contains <hash>` includes `<remote>/<branch>` —
  if not, the user must push first (pushing is the user's action; the
  workflow never pushes for them).

## Remote Preflight (read-only, over SSH, after consent)

The CLI prints these as ready SSH argv arrays; run them in order and stop
on the first failure:

| Check | Command (remote side) | Failure |
|---|---|---|
| Connection + repo | `git -C <bench>/apps/<app> rev-parse HEAD` | SSH or path failure → stop |
| Fetch refs | `git -C … fetch <remote>` | missing remote → stop |
| Clean tree | `git -C … status --porcelain` | any output → `[PREFLIGHT_DIRTY]`, stop |
| Expected branch | `git -C … branch --show-current` | mismatch → `[PREFLIGHT_BRANCH]`, stop |
| Target commit exists | `git -C … rev-parse <remote>/<branch>` | unresolvable or ≠ task commit → stop |
| Fast-forward possible | `git -C … merge-base --is-ancestor HEAD <remote>/<branch>` | non-zero → `[PREFLIGHT_NO_FF]`, stop |

Judged deterministically by
`scripts/core/deployment.evaluate_remote_preflight` from the captured
outputs — feed it the outputs rather than eyeballing them.

Also confirm bench path and app path exist (`test -d`) on the first
connection.

## Only After All Checks

```bash
git -C <bench>/apps/<app> pull --ff-only <remote> <branch>
```

Never: stash, reset, clean, checkout another branch, create merge commits,
or otherwise touch server-local work.
