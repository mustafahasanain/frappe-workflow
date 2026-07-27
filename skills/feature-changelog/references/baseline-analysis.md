# Baseline Analysis

When an existing application has no `FEATURE_CHANGELOG.md`, discover the
already-shipped features once, honestly, with confidence labels.

## Sources (in order of reliability)

1. `PROJECT_CONTEXT.md` (generate it first — init runs project-context
   before this skill).
2. Existing DocTypes with real controller logic.
3. `hooks.py` (doc_events, overrides, scheduler_events).
4. Whitelisted APIs and integration clients.
5. Main services and their tests.
6. Git history and commit messages — supporting evidence for dates and
   intent, never the sole source of a feature claim.
7. Current code behavior (read the actual functions).

## Entry Construction

Each discovered feature gets a normal entry (template format) plus:

```markdown
- **Source:** Baseline project analysis
- **Confidence:** High | Medium | Low
```

- **High** — behavior verified in code and wiring (hooks/UI/API) found.
  → add automatically.
- **Medium** — behavior visible in code but purpose or completeness
  uncertain. → add with an explicit note of what is uncertain.
- **Low** — hints only (a stray file, an ambiguous commit). → do NOT add;
  list them for the user to confirm or discard.

## Dates

- `Added:` from Git history only when a clearly attributable commit exists;
  otherwise `Unknown`. Never invent history.
- Change History for baseline entries: a single entry —
  `#### Unknown — Baseline discovery` describing current behavior.

## Granularity

- One entry per independent functional capability, grouped by module.
- Skip: scaffolding, empty doctypes, dead code, pure utilities.
- Record product behavior, not file inventory (that is PROJECT_CONTEXT's
  job).

## Finish

- IDs via `feature next-id` per (type, module) as entries are added.
- `bin/frappe-workflow feature validate-index` must pass.
- Report counts: N High added, M Medium added (with notes), K Low pending
  confirmation.
