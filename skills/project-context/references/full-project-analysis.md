# Full Project Analysis (first-time)

Performed once, when `docs/ai-context/PROJECT_CONTEXT.md` does not exist.
Goal: fill every
template section with verified, concise, navigation-oriented content.

## What to Inspect

Work through these sources; skip what the app does not have, never invent:

1. **Structure** — top-level tree of `<app>/<app>/` (modules, doctype
   folders, public/, templates/, www/).
2. **`hooks.py`** — the wiring hub: doc_events, overrides
   (`override_doctype_class`, `override_whitelisted_methods`), fixtures,
   `scheduler_events`, app include files, permission hooks.
3. **`modules.txt`** — module list; group Core DocTypes by these.
4. **Important DocTypes** — for each module, DocTypes with controllers that
   contain real logic (not empty scaffolds): read the JSON for fields/links,
   the `.py` for lifecycle logic.
5. **Python controllers and services** — files with business rules,
   validation, calculations.
6. **Client scripts** — `public/js/*`, doctype-level `.js` with nontrivial
   behavior.
7. **Whitelisted APIs** — `@frappe.whitelist()` occurrences; group by area.
8. **Overrides** — subclasses of Frappe/ERPNext controllers.
9. **Scheduled/background jobs** — `scheduler_events` targets, `frappe.enqueue`
   call sites, `tasks.py`.
10. **Fixtures and patches** — `fixtures/`, `patches.txt`, `patches/`.
11. **Tests** — layout and how they run.
12. **README / docs** — existing documentation to reference, not duplicate.
13. **Git history** — only when it clarifies intent (`git log --oneline`
    high level; do not transcribe it).
14. **Integrations** — external service clients, webhooks, tokens (never
    copy secrets; reference settings DocTypes instead).

## Writing Rules

- Use the template `templates/project/PROJECT_CONTEXT.md` section for
  section; every section gets real content or an explicit "None found".
- Component blocks (Core DocTypes / Business Logic) follow the template's
  component format: Purpose / Primary Service / Primary DocType / Used By /
  Frontend Entry Points / Related Feature IDs / Important Constraint.
- Navigation Map: task-oriented rows ("to change X, start at Y").
- Versions: read `frappe/__init__.py` and `erpnext/__init__.py` under the
  bench when present, else `Unknown`.

## Recording the Analyzed Commit

```yaml
analyzed_commit: <output of git rev-parse HEAD, short form acceptable>
```

Set `generated_at` to today's real date, `context_version: 1`.

## Finish

`bin/frappe-workflow validate project-context` must pass before reporting
the analysis complete.
