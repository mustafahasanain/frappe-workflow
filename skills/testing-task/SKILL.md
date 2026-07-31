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

- Arabic `Title` + `Description` **copied to the host clipboard** and
  **printed in the Claude Code terminal**, ready to paste into the testing
  team's task-management system — content rules in
  [references/arabic-testing-task-rules.md](references/arabic-testing-task-rules.md).
- **No file.** Never create `docs/ai-context/testing-task-ar.md`,
  `.claude/testing-task-ar.md`, or any replacement testing-task file
  anywhere.
- State: `testing_task = {status: "generated", generated_at}`;
  `state transition completed`. The generated Arabic text itself is never
  stored in state.

## Preconditions

- Stage is `deployed` or `deployment_skipped`; commit verified.

## Order of Operations

The clipboard copy comes **first**, and everything else depends on it:

1. `CLI clipboard copy` with the finished Arabic text on stdin.
2. Exit code `0` → print the same two blocks in the terminal, record the
   state, transition to `completed`.
3. Exit code `8` (no clipboard) → **stop**. Print nothing of the Arabic
   text, write no file, record no state, transition nothing. Show the
   command's own failure output — it names every method that was checked —
   and tell the user to install a clipboard utility (`wl-clipboard`,
   `xclip`, or `xsel`) or run from a session that has one, then ask for
   `testing` again. Never install a package.

The terminal copy is a convenience, not the delivery channel: a terminal
renders Arabic visually reordered, so text that only reached the terminal
is not a usable hand-off. That is why a failed copy blocks the workflow
instead of falling back to printing.

## Stopping Conditions

- Task copied, printed, state recorded, workflow `completed` → report the
  closing summary (commit hash, deployment outcome, and that the Arabic
  testing task is on the clipboard and shown above). Done.
- Clipboard unavailable → stage unchanged, nothing recorded, the blocker
  reported to the user. Not a completion.

## Repeating After Completion

The text is kept nowhere, so a user who lost it may ask for it again while
the stage is already `completed`. Regenerate it from the same approved
behavior, copy it to the clipboard and print it again, and change nothing:
no transition (there is none from `completed`), no state write, no file. A
failed copy at this point changes nothing either — the stage stays
`completed`.

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
- Printing the Arabic text, recording state, or transitioning to
  `completed` after a failed clipboard copy.
- Installing a clipboard package, or working around a missing one with a
  file, a here-doc into an editor, or any other on-disk detour.
- Mentioning source files, Python functions, or internal implementation
  in the Arabic text.
- Copying the original task title as the description.
- Describing behavior that was not actually approved and implemented.
- Generating from a stage other than `deployed` / `deployment_skipped`.

## Shared Rules

[shared-workflow-rules.md](../../references/shared-workflow-rules.md).
