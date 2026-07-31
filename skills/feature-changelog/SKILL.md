---
name: feature-changelog
description: Maintain FEATURE_CHANGELOG.md - the functional feature registry. Baseline discovery, duplicate/extension detection before planning, deterministic feature IDs, post-approval updates, and index validation.
user-invocable: false
---

# Feature Changelog Skill

Owns `docs/ai-context/FEATURE_CHANGELOG.md`: a registry of product
behavior used to decide
whether requested work already exists, extends something, or is new. It
records meaningful business logic only — never commits, renames,
formatting, or refactors without behavior change. The whole file is English.

## When to Use

- `init` with no `docs/ai-context/FEATURE_CHANGELOG.md` → baseline
  discovery
  ([references/baseline-analysis.md](references/baseline-analysis.md)).
- Before any `docs/ai-context/TASK_PLAN.md` is created or accepted →
  feature search
  ([references/feature-detection.md](references/feature-detection.md)).
- New IDs → [references/feature-id-rules.md](references/feature-id-rules.md).
- After a valid Codex `APPROVED`, during finalization → registry update.
- Any registry edit → [references/index-validation.md](references/index-validation.md).

## Inputs

- `docs/ai-context/FEATURE_CHANGELOG.md` (or its absence), the task
  description/plan, `docs/ai-context/PROJECT_CONTEXT.md`, the repository
  itself.
- Deterministic helpers: `bin/frappe-workflow feature search <query>`,
  `feature next-id --type <type> --module <module>`,
  `feature validate-index`.

## Outputs

- Search verdicts for planning: already implemented / related (extension) /
  new — always confirmed by inspecting actual files, never by text
  similarity alone.
- Registry entries following the template format in
  `templates/project/FEATURE_CHANGELOG.md` in the plugin (Index row +
  detailed entry
  grouped by module).

## Preconditions

- Registry updates (beyond baseline) happen **only** in finalization —
  after implementation complete, validations and tests passed, and a valid
  `APPROVED` with matching fingerprint.

## Stopping Conditions

- `bin/frappe-workflow feature validate-index` passes after every edit.
- Baseline: all High-confidence entries written; Medium noted; Low listed
  for user confirmation — then stop.

## Prohibited

- Updating the registry during implementation or review rounds.
- Calculating IDs by guessing — only `feature next-id` output.
- Changing an existing ID, ever (renames keep the ID).
- Statuses other than `Active`, `Deprecated`, `Replaced`, `Removed`.
- Inventing feature history or dates (unknown dates stay `Unknown`).

## Update Rules at Finalization

- New capability → new entry (Index row + detail, next deterministic ID).
- Extension → same ID: update `Last Updated`, Behavior/Main Files when
  needed, add a Change History dated entry.
- Bugfix of an existing feature → Change History entry on that feature;
  an independent `BUG-` entry only when important, independent, and not
  clearly owned by an existing feature.
- Replacement → old entry `Status: Replaced` + `Replaced By:`; new entry
  may carry `Replaces:`.

## Shared Rules

[shared-workflow-rules.md](../../references/shared-workflow-rules.md),
[file-lifecycle.md](../../references/file-lifecycle.md).
