# Complete Project Planning (`task_type: project`)

A complete-project task uses the same `TASK_PLAN.md` skeleton with these
additional required subsections (add them under the listed parent
sections):

## Under "Task Summary" / "Objective"

- **Project Objectives** — ranked outcomes.
- **User Roles** — every actor and what they may do.
- **User Journeys** — the main end-to-end flows in user terms.
- **Main Workflows** — document lifecycles (draft → submitted → …),
  approval chains, Frappe Workflow definitions when used.

## Under "Data Model Changes"

- **Module Breakdown** — modules and their responsibilities.
- **DocType Design** — per DocType: purpose, key fields, naming strategy
  (autoname/series), submittable or not.
- **Child Tables** — parent/child relations.
- **Data Relationships** — Link/Dynamic Link graph; what cascades.

## Under "Permissions and Security"

- **Roles** — new roles and role profiles.
- **Permission matrix** — DocType × role × (read/write/create/submit/
  cancel/delete), plus user-permission and query conditions.

## Under "Implementation Plan"

- **APIs** — whitelisted endpoints with request/response shape.
- **Integrations** — external systems, auth model, failure behavior.
- **Background Jobs** — scheduled/queued work, frequency, idempotency.
- **Reports and Dashboards** — report type (query/script), filters,
  audiences.
- **Audit Requirements** — versioning, track changes, activity logs.
- **Error Handling and Logging** — user-facing errors vs logged detail.

## Under "Migration and Deployment Requirements"

- **Migration Strategy** — data import, fixtures, patches sequencing.
- **Deployment Strategy** — environments, ordering, rollback constraints.

## Phasing (own top-level section: `## Development Phases`)

- **MVP Scope** — the smallest shippable phase; every MVP item maps to
  implementation steps in THIS plan.
- **Phase 2+** — named phases with their deliverables.
- **Deferred Features** — explicitly out of scope with reasons.

Only the MVP phase gets implementation steps now; later phases become
their own future tasks. This keeps the completion gate meaningful — a
project plan whose steps cover the MVP can actually reach "all steps
Completed".

## Testing Strategy

Extend the Testing Plan with per-module coverage expectations and seed/demo
data needs for manual testing.
