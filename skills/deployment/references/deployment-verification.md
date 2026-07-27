# Deployment Verification

Deployment succeeds **only** when all of these hold:

1. **Server HEAD == expected task commit.**
   Remote `git rev-parse HEAD` after the pull; compare with
   `bin/frappe-workflow deployment verify --expected <task-commit>
   --server-head <output>` (handles short/long hash prefixes).
2. **Every selected bench command exited 0** (see frappe-command-matrix).
3. **No blocking errors occurred** at any step.
4. **App and Site remain reachable** to the extent verifiable — e.g.
   remote `bench --site <site> version` or an equivalent cheap read-only
   check succeeds. Do not overclaim: record exactly what was verified.

## Record (into state `deployment` + transition reason)

```text
expected commit
server commit before
server commit after
commands executed (with exit codes)
results (trimmed, secrets redacted)
deployment timestamp
```

State updates:

```bash
bin/frappe-workflow state set deployment.required true --json-value
bin/frappe-workflow state set deployment.status deployed
bin/frappe-workflow state set deployment.server_commit <verified hash>
bin/frappe-workflow state set deployment.deployed_at <UTC timestamp>
bin/frappe-workflow state transition deployed --reason "verified <hash> on <host>"
```

## On Verification Failure

- Status stays failed-pending; **never** record `deployed`.
- Report exactly which check failed and the server's current state
  (before/after commits, failing command output).
- Do not attempt automatic rollback — the server is a shared environment;
  recovery is a human decision.
- The workflow remains in `committed`; after the cause is fixed the
  deploy action may be run again from the top (question included).
