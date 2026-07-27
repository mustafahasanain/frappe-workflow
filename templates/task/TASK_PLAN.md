---
task_id: TASK-<YEAR>-<NNN>
task_title: <short imperative title>
task_type: feature
status: planned
created_at: <YYYY-MM-DD>
updated_at: <YYYY-MM-DD>
suggested_branch: <feature/...>
app_name: <app name>
target_site: <site name>
bench_path: <absolute bench path>
related_features:
  - <FEAT-... or remove this list item>
---

# Task Summary

One paragraph describing the task in plain language.

## Objective

The single outcome this task must achieve.

## Business Requirement

Why the business needs this, in the requester's terms.

## Current Behavior

What the application does today (verified against the repository, not assumed).

## Required Behavior

What the application must do when this task is complete.

## Existing Feature Analysis

Result of searching FEATURE_CHANGELOG.md: related feature IDs, whether this
task is new functionality, an extension, or overlaps existing behavior, and
what inspection of the actual files showed.

## Scope

### In Scope

- Explicit list of what this task includes.

### Out of Scope

- Explicit list of what this task deliberately excludes.

## Assumptions

- Assumptions the plan depends on; each one verifiable or flagged.

## Dependencies

- Other features, apps, services, or data this task depends on.

## Repository Verification Required

- Paths or facts that still need verification before/while implementing.

## Implementation Plan

### 1. <Specific, verifiable step title>

- **Status:** Pending
- **Action:** What will be done.
- **Location:** Confirmed path or `Requires repository verification`.
- **Purpose:** Why this step exists.
- **Implementation Details:**
  - Required fields, validation behavior, permissions, lifecycle events.
- **Expected Result:** The observable outcome of this step.
- **Validation:** Exactly how this step is verified.
- **Dependencies:** None.

## Expected Files

### Files to Create

- `path/to/new_file.py`

### Files to Modify

- `path/to/existing_file.py`

### Files Requiring Verification

- `path/that/needs/checking.py`

## Data Model Changes

New DocTypes, fields, or schema changes — or "None".

## Permissions and Security

Roles, permission rules, input validation, and security considerations.

## Backward Compatibility

What existing behavior must keep working, and how that is protected.

## Migration and Deployment Requirements

Patches, migrations, fixture exports, asset builds, restarts — or "None".

## Testing Plan

### Automated Tests

- Test files/cases to add or update.

### Manual UI Tests

- Steps a human performs in the UI.

### Regression Tests

- Existing behavior to re-verify.

### Integration Tests

- Cross-system checks, when applicable.

## Acceptance Criteria

- Checkable statements that define "done".

## Risks and Constraints

- Known risks, edge cases, and constraints.

## Optional Follow-up Improvements

- Improvements deliberately deferred; not part of this task.
