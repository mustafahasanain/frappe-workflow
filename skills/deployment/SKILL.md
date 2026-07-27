---
name: deployment
description: Optional demo-server deployment - explicit confirmation, local and remote preflight, fast-forward-only pull over SSH, minimal required bench commands, and deployed-commit verification.
user-invocable: false
---

# Deployment Skill

Deploys the verified task commit to the demo server — only after the user
explicitly chooses to. Skipping is a first-class outcome, not a failure.

## When to Use

- The `deploy` action, or resuming into stage `committed`.

## The Question (always, verbatim, before anything else)

```text
The task has been committed successfully.

Deploy this task to the demo server?

1. Deploy now
2. Skip deployment
```

**No SSH connection is opened before the answer.**

- **Skip** →

  ```bash
  bin/frappe-workflow state set deployment.required false --json-value
  bin/frappe-workflow state set deployment.status skipped
  bin/frappe-workflow state set deployment.skip_reason "Skipped by user"
  bin/frappe-workflow state transition deployment_skipped --reason "user skipped"
  ```

  (use the user's stated reason when they gave one). No SSH, no server
  commands, no local deployment commands. Done.
- **Deploy now** → the procedure below.

## Procedure

1. Config: `bin/frappe-workflow deployment validate-config`
   (`.claude/deployment.local.json`; see the example template).
2. Local + config/task consistency: `bin/frappe-workflow deployment
   preflight` — also prints the exact remote read-only preflight commands
   ([references/deployment-preflight.md](references/deployment-preflight.md)).
3. Remote preflight over SSH per
   [references/ssh-safety.md](references/ssh-safety.md) — read-only.
4. Fast-forward-only pull; then the minimal bench command set from
   `bin/frappe-workflow deployment required-commands --commit <hash>`
   ([references/frappe-command-matrix.md](references/frappe-command-matrix.md)).
5. Verify and record
   ([references/deployment-verification.md](references/deployment-verification.md));
   `state transition deployed`.

## Inputs

- Stage `committed` with verified `commit.hash`; deployment config.

## Outputs

- Deployment record in state (commits before/after, commands, results,
  timestamp) — secrets never recorded.

## Preconditions

- Explicit "Deploy now" answer this session; both preflights pass.

## Stopping Conditions — stop immediately, report, change nothing

Server local changes · unexpected branch · missing remote · missing
commit · diverged history · failed bench command · mismatched final
commit. Recovery on the server is a human decision, never automatic.

## Prohibited

- Any SSH before the explicit answer.
- stash / reset / clean / checkout-another-branch / merge commits on the
  server; discarding server work.
- Running bench commands the changed files do not require.
- Printing private keys, passwords, or storing them in config or records.

## Shared Rules

[git-safety-rules.md](../../references/git-safety-rules.md),
[security-rules.md](../../references/security-rules.md).
