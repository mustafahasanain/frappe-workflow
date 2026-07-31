# Implementation Loop

For every plan step, in order (respecting step Dependencies):

1. **Set `- **Status:** In Progress`** in `docs/ai-context/TASK_PLAN.md`.
2. **Read only relevant files** — the step's Location plus what it
   references. Not the whole repository.
3. **Verify unconfirmed paths** — any `Requires repository verification`
   location is resolved now; update the plan with the confirmed path.
4. **Implement** the step's Action per its Implementation Details.
5. **Run the step's Validation** exactly as written in the step (see
   [step-validation.md](step-validation.md)).
6. **Run relevant tests** — the app's tests affected by this step; on a
   Site-dependent step, the Frappe test runner against the task's
   `target_site`.
7. **Record commands and results** — real command lines and real outcomes;
   they feed the implementation summary's "Tests Executed"/"Test Results".
8. **Mark `Completed`** only after 5 and 6 succeeded, then sync state
   counts.

## Self-Transition Checkpoints

After completing a step that closes a milestone (or before a pause), run
`bin/frappe-workflow state transition implementation --reason "steps X/Y completed"`
to append a progress record.

## When Blocked

- Set the step to `Blocked` with an exact `- **Blocker:**` line (attempted
  command, exact error, missing information).
- `bin/frappe-workflow state blocker add "<step>: <exact reason>"`.
- Stage stays `implementation`. Report to the user. Never silently skip,
  never fake completion, and never "temporarily" continue a dependent step.

## Deviations

- Technical deviation preserving the objective (different helper name,
  extra null-check, corrected path): allowed — record it in the plan step's
  Implementation Details and in the summary's "Deviations from Plan".
- Business scope deviation: stop; the plan must be updated with user
  awareness first (see task-planning skill).
