---
name: project-context
description: Create and maintain PROJECT_CONTEXT.md - the concise navigation and architecture map of a Frappe application. Full first-time analysis, incremental updates keyed to analyzed_commit, and strict update-decision rules.
user-invocable: false
---

# Project Context Skill

Maintains `docs/ai-context/PROJECT_CONTEXT.md` in the target app
repository: a concise map
that prevents future agents from rereading the whole repository. It is not
a code dump, not a Git history, not a feature archive, not a task tracker.

## When to Use

- During `init` when `docs/ai-context/PROJECT_CONTEXT.md` is missing →
  first-time analysis
  ([references/full-project-analysis.md](references/full-project-analysis.md)).
- During `init` or `start` when it exists → incremental analysis
  ([references/incremental-analysis.md](references/incremental-analysis.md)).
- During finalization when the approved task changed architecture or
  navigation → content update per
  ([references/context-update-rules.md](references/context-update-rules.md)).

## Inputs

- Target app repository root (from `bin/frappe-workflow detect --json`).
- Template: `templates/project/PROJECT_CONTEXT.md` (plugin repository).
- Current HEAD (`git rev-parse HEAD`) and, for incremental runs, the
  recorded `analyzed_commit`.

## Outputs

- `docs/ai-context/PROJECT_CONTEXT.md` in the app repository, passing
  `bin/frappe-workflow validate project-context`.
- Frontmatter with `analyzed_commit` set to the commit that was analyzed.

## Preconditions

- Detection succeeded; the app root is a Git repository.
- For incremental runs: existing file parses (frontmatter present).

## Stopping Conditions

- Validation passes and `analyzed_commit` equals current HEAD → done.
- The repository has no commits yet → record that, produce the structural
  sections from the working tree, set `analyzed_commit` after the first
  commit exists.
- Existing file invalid/obsolete beyond repair → report it and perform one
  full re-analysis (this is the only case that rereads everything).

## Prohibited

- Copying implementation details that reading the referenced file provides.
- Binding the app to a Site here (Site choice is task-level state).
- Updating content when the update-decision question answers "no"
  (bumping `analyzed_commit` alone is allowed after confirming no content
  change is needed).
- Inventing versions: `frappe_version`/`erpnext_version` come from the
  bench (`apps.txt`, `__init__.py` versions) or are recorded as `Unknown`.

## Shared Rules

[shared-workflow-rules.md](../../references/shared-workflow-rules.md),
[frappe-project-detection.md](../../references/frappe-project-detection.md),
[file-lifecycle.md](../../references/file-lifecycle.md).
