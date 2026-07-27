# Plan Validation

`bin/frappe-workflow validate task-plan` enforces (rule IDs bracketed):

## Frontmatter

- Required keys: `task_id`, `task_title`, `task_type`, `status`,
  `app_name` [`PLAN_FRONTMATTER_KEY`].
- `task_id` matches `TASK-YYYY-NNN` [`PLAN_TASK_ID`].
- `task_type` ∈ feature | change | bugfix | integration | refactor |
  project [`PLAN_TASK_TYPE`].
- `status` ∈ planned | approved | in_progress | implementation_complete |
  codex_approved | committed | completed | blocked [`PLAN_STATUS`].

## Required Sections [`PLAN_SECTION`]

Task Summary, Objective, Business Requirement, Current Behavior, Required
Behavior, Existing Feature Analysis, Scope (In Scope / Out of Scope),
Assumptions, Dependencies, Repository Verification Required,
Implementation Plan, Expected Files, Data Model Changes, Permissions and
Security, Backward Compatibility, Migration and Deployment Requirements,
Testing Plan, Acceptance Criteria, Risks and Constraints.

## Implementation Steps

- At least one numbered `### N. Title` step [`PLAN_NO_STEPS`].
- Each step has Status, Action, Purpose, Expected Result, Validation,
  Dependencies [`PLAN_STEP_FIELD`].
- Step status ∈ Pending | In Progress | Completed | Blocked
  [`PLAN_STEP_STATUS`].
- Blocked steps carry `- **Blocker:**` [`PLAN_STEP_BLOCKER`].

## Judgment Checks (not automatable — verify while writing)

- `target_site` present when implementation needs a Site (migrate,
  UI testing); when genuinely not needed, the plan says why.
- Acceptance criteria are checkable statements, not aspirations.
- Scope sections are explicit enough to detect expansion later.
- "Repository Verification Required" lists every unverified fact from the
  input.

## Task ID Determination

1. Current `TASK_PLAN.md` (if the previous task completed) → its ID.
2. Otherwise Git history of `TASK_PLAN.md`
   (`git log --follow -p -- TASK_PLAN.md`, scanning for `task_id:`) —
   collect all previous IDs.
3. Next ID = max found number + 1 for the current year; never reuse a
   found ID; nothing found → `TASK-<year>-001`.
