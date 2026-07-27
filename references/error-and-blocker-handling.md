# Error and Blocker Handling

## Blocker Recording Format

Blockers are recorded in two places, always together:

1. **The plan step** (`TASK_PLAN.md`):

```markdown
- **Status:** Blocked
- **Blocker:** Exact reason preventing completion, including the failing
  command and its relevant output, and the affected files.
```

2. **Workflow state**:

```bash
bin/frappe-workflow state blocker add "step 4: bench migrate failed: <exact error>"
```

A blocker message must contain: what was attempted, the exact failure
(command + error), and what information or decision is missing. Vague
blockers ("didn't work") are not acceptable.

Clearing: `bin/frappe-workflow state blocker clear` — only after the cause
is actually resolved and the step re-validated.

## Recoverable vs Non-Recoverable Inconsistencies

**Recoverable (fix and continue):**

- State says `implementation` but a step status is stale → re-derive step
  counts from `TASK_PLAN.md` and update state.
- Review prompt exists but state lost the round number → recount from
  `.claude/reviews/` filenames (the CLI already does this).
- `analyzed_commit` behind HEAD → incremental context update.

**Non-recoverable without user judgment (stop and report):**

- State says `committed` but the recorded commit hash does not exist.
- State says `ready_for_commit` but the fingerprint no longer matches
  (approval invalidated — needs another review round, tell the user).
- `TASK_PLAN.md` deleted while a task is active.
- Unknown `schema_version` in the state file — never silently repair or
  migrate; report and let the user decide.
- Unrelated files already staged by someone else.

## State Recovery After Restart

When Claude Code reopens mid-task, the no-action command:

1. Detects the environment.
2. Loads and validates `.claude/task-workflow.json`.
3. Cross-checks state against Git (branch, HEAD vs `base_commit`, recorded
   commit hash, fingerprint when in `ready_for_commit`).
4. Continues from the recorded stage, or stops with a precise inconsistency
   report when user judgment is required.

## No Destructive Recovery

Recovery never deletes files, never resets Git, never rewrites review
history, and never downgrades a stage silently. The only stage rollback the
engine permits is `ready_for_commit → review_fixes` (approval invalidation).

## Atomic State Updates

All state writes go through `scripts/core/workflow_state.save_state`:
validate → temp file in the same directory → flush + fsync → atomic
`os.replace`. An interrupted write can never leave invalid JSON behind.

## Clear Error Messages

Every deterministic error carries a bracketed rule identifier, e.g.
`[TRANSITION_REJECTED]`, `[GATE_STEP_INCOMPLETE]`, `[DEPLOY_NO_CONFIG]`.
Skills surface the identifier and the human explanation together.

## CLI Exit Codes

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

Errors print to stderr; machine output (`--json`) prints to stdout.
Validation-only commands never mutate state.
