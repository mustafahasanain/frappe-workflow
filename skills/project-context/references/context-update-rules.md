# Context Update Rules

## The Decision Question

```text
Will a future agent misunderstand the project or inspect the wrong files
if PROJECT_CONTEXT.md is not updated?
```

Answer **no** → do not change content. The `analyzed_commit` may still be
advanced after confirming the code changes require no content change.

## Update Content When a Task Changes

- Architecture (layering, service boundaries, new module).
- Navigation (where a feature area's logic now lives).
- Core components / important DocTypes (new, renamed, repurposed).
- Main services (new service file, moved responsibilities).
- Hooks or overrides (new doc_events, new override, removed hook).
- Integrations (new external service, changed entry points).
- Development workflow (new build step, new test harness).
- Deployment workflow (new migration requirement, new worker).

## Do NOT Update For

- Bug fixes inside an already-documented component (behavior details belong
  to `FEATURE_CHANGELOG.md`).
- Refactors that keep files and responsibilities in place.
- New fields on a documented DocType that don't change its role.
- Anything readable by opening the already-referenced file.

## Timing

- During **finalization** (after Codex approval) only — never mid-
  implementation, so the review fingerprint stays meaningful. The
  finalization-file exception in
  `skills/frappe-task/references/workflow-gates.md` covers this file.
- During `init`/`start` incremental runs — allowed, because no approval is
  active then.

## Style Constraints

- Keep sections concise; component blocks over prose walls.
- Reference files; never paste function bodies.
- Related Feature IDs stay in sync with `FEATURE_CHANGELOG.md` entries
  touched by the same finalization.
