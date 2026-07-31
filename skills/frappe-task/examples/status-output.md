# Example `status` Output

The `status` action renders a read-only report in this shape (values come
from `detect --json`, `state show`, `git inspect`, and the plan file —
never invented):

```text
Frappe Workflow Status
======================

Task:        TASK-2026-003 — Add Telegram reporting integration
Type:        integration
Stage:       review_fixes

App:         general_trading
Bench:       /home/mustafa/frappe-bench
Target Site: car.wash
Branch:      feature/almasah-telegram-reports
HEAD:        4f2c9ab

Plan:        in_progress (docs/ai-context/TASK_PLAN.md valid)
Steps:       6 total — 5 completed, 1 in progress, 0 blocked

Codex Review:
  Round:     2
  Status:    changes_required
  Prompt:    docs/ai-context/reviews/round-002-prompt.md
  Result:    docs/ai-context/reviews/round-002-result.md
  Open findings: 1 of 3 remaining

Commit:      not created
Deployment:  pending
Testing task: pending

Blockers:    none

Consistency:
  ✓ state branch matches Git branch
  ✓ recorded base commit is an ancestor of HEAD
  ✓ workflow state schema valid
```

Once the `testing` action has run, the same line reports the recorded
status and timestamp from `testing_task` — and never a file path, because
the Arabic title and description are printed in the terminal and are not
saved anywhere:

```text
Testing task: generated (2026-07-31T13:09:37Z)
```

A state file written by an older plugin version may still carry a
`testing_task.path`; ignore it and never print it.

When something is inconsistent, the Consistency section names it precisely:

```text
Consistency:
  ✗ state records branch 'feature/telegram' but Git is on 'develop'
    → resolve before continuing (see error-and-blocker-handling.md)
```

Formatting rules:

- Plain text block, stable field order, no color.
- Omit sections that do not apply yet (e.g. no Codex Review block during
  planning) rather than printing empty placeholders.
- Blockers are listed verbatim with their recorded timestamps.
- `status` never mutates state, files, or Git.
