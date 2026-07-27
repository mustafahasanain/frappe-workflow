---
name: task-planning
description: Turn a ready plan or plain task description into a validated, repository-aware TASK_PLAN.md. Detects existing/related features, verifies paths, plans normal tasks and complete projects, and prevents silent scope expansion.
user-invocable: false
---

# Task Planning Skill

Produces exactly one active `TASK_PLAN.md` (template:
`templates/task/TASK_PLAN.md`) from either a prepared plan or a plain
description. The plan is repository-aware: every stated path and fact is
verified or explicitly marked for verification.

## When to Use

- The `start` action, with either input type.
- Resuming a `planning`-stage workflow.

## Inputs

- Raw user input (ready plan or description).
- `PROJECT_CONTEXT.md`, `FEATURE_CHANGELOG.md` (searched via the
  feature-changelog skill **before** writing the plan).
- Detection facts (`bin/frappe-workflow detect --json`), current Git state.

## Outputs

- `TASK_PLAN.md` passing `bin/frappe-workflow validate task-plan`
  ([references/plan-validation.md](references/plan-validation.md)).
- Frontmatter filled: deterministic `task_id` (TASK-YYYY-NNN — next number
  from prior plans/Git history, never reusing a found ID; start at 001
  when none found), `task_type`, `status: planned`, app/bench/site facts,
  `suggested_branch`, `related_features`.

## Procedure

1. **Active-task rule:** an unfinished task is never silently replaced —
   the frappe-task router enforces this before delegating here.
2. Feature search first
   ([existing-feature-analysis.md](references/existing-feature-analysis.md)).
3. For ready plans: treat as input, not truth — verify every path, add
   missing technical/validation/security/migration steps, convert to the
   standard format; report every correction made.
4. For descriptions: analyze the repository, then draft the full plan.
5. For `task_type: project`, additionally follow
   [complete-project-planning.md](references/complete-project-planning.md).
6. Every implementation step must be specific and verifiable (template
   step format). Vague steps ("Update backend") are forbidden.
7. Validate, then hand back to the router for the planning gate.

## Preconditions

- Detection succeeded; no unfinished active task.

## Stopping Conditions

- Plan validates and the user has seen it (plus the corrections list for
  ready plans) → done; implementation starts only after the planning gate.
- Input intent unclear (not a development task) → ask, don't guess.

## Prohibited

- Silently changing the business objective, adding unrelated features, or
  expanding product scope (allowed silently: path corrections, missing
  technical validation, security/migration steps — each recorded).
- Starting implementation before the plan is complete and accepted.
- Inventing paths, DocTypes, or Sites — unverified locations say
  `Requires repository verification`.

## Shared Rules

[shared-workflow-rules.md](../../references/shared-workflow-rules.md),
[frappe-project-detection.md](../../references/frappe-project-detection.md).
