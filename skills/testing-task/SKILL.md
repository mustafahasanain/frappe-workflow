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

- The **approved implemented behavior**: `TASK_PLAN.md` (Required
  Behavior + Acceptance Criteria as approved), the feature-changelog entry
  updated at finalization, the implementation summary.
- Deployment status from state.

## Outputs

- Arabic `Title` + `Description` only — content rules in
  [references/arabic-testing-task-rules.md](references/arabic-testing-task-rules.md).
- Copy saved to `.claude/testing-task-ar.md` (template shape:
  `templates/output/TESTING_TASK_AR.md`).
- State: `testing_task = {status: "generated", path, generated_at}`;
  `state transition completed`.

## Preconditions

- Stage is `deployed` or `deployment_skipped`; commit verified.

## Stopping Conditions

- Task generated, saved, workflow `completed` → report the closing
  summary (commit hash, deployment outcome, testing task location). Done.

## Deployment-Skipped Warning

When the stage is `deployment_skipped`, show this **separately, in
English, outside the Arabic content**:

```text
Deployment was skipped. Publish the testing task only after the changes
are available in the testing environment.
```

Never embed the warning inside the Arabic description.

## Prohibited

- Mentioning source files, Python functions, or internal implementation
  in the Arabic text.
- Copying the original task title as the description.
- Describing behavior that was not actually approved and implemented.
- Generating from a stage other than `deployed` / `deployment_skipped`.

## Shared Rules

[shared-workflow-rules.md](../../references/shared-workflow-rules.md).
