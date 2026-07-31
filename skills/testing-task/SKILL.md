---
name: testing-task
description: Generate the concise Arabic testing-team task (title + description) from the approved implemented behavior, warn separately when deployment was skipped, and close the workflow at completed.
user-invocable: false
---

# Testing Task Skill

Produces the final hand-off to the (Arabic-speaking) testing team and
closes the workflow.

## When to Use

- The `testing` action — only from stage `deployed` or
  `deployment_skipped`.

## Inputs

- The **approved implemented behavior**: `docs/ai-context/TASK_PLAN.md`
  (Required
  Behavior + Acceptance Criteria as approved), the feature-changelog entry
  updated at finalization, the implementation summary.
- Deployment status from state.

## Outputs

- Arabic `Title` + `Description` **printed in the Claude Code terminal**,
  ready to copy into the testing team's task-management system — content
  rules in
  [references/arabic-testing-task-rules.md](references/arabic-testing-task-rules.md).
- **No file.** Never create `docs/ai-context/testing-task-ar.md`,
  `.claude/testing-task-ar.md`, or any replacement testing-task file
  anywhere.
- State: `testing_task = {status: "generated", generated_at}`;
  `state transition completed`. The generated Arabic text itself is never
  stored in state.

## Preconditions

- Stage is `deployed` or `deployment_skipped`; commit verified.

## Stopping Conditions

- Task printed, state recorded, workflow `completed` → report the closing
  summary (commit hash, deployment outcome, and that the Arabic testing
  task was printed above for copying). Done.

## Reprinting After Completion

The text lives only in the terminal, so a user who lost it may ask for it
again while the stage is already `completed`. Regenerate and print it from
the same approved behavior, and change nothing: no transition (there is
none from `completed`), no state write, no file.

## Deployment-Skipped Warning

When the stage is `deployment_skipped`, show this **separately, in
English, outside the Arabic content**:

```text
Deployment was skipped. Publish the testing task only after the changes
are available in the testing environment.
```

Never embed the warning inside the Arabic description.

## Prohibited

- Writing the title or description to any file, in the application repo or
  anywhere else. Older plugin versions saved
  `.claude/testing-task-ar.md` / `docs/ai-context/testing-task-ar.md`; such
  a file may still exist in an old application — leave it untouched, never
  read it, never update it.
- Mentioning source files, Python functions, or internal implementation
  in the Arabic text.
- Copying the original task title as the description.
- Describing behavior that was not actually approved and implemented.
- Generating from a stage other than `deployed` / `deployment_skipped`.

## Shared Rules

[shared-workflow-rules.md](../../references/shared-workflow-rules.md).
