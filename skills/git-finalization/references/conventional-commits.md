# Conventional Commit Generation

The message is generated from: task type, the plan, the **actual diff**,
approved behavior, and the primary module.

## Format

```text
<type>(<scope>): <imperative subject, lowercase, no trailing period>
```

Optional body: a blank line, then behavior-level bullets:

```text
feat(stock): add unified temporary stock reservation

- support multiple reference doctypes
- validate reserved quantities against availability
- release reservations on completion and cancellation
- add automated coverage for the reservation lifecycle
```

## Type Mapping

| task_type | commit type |
|---|---|
| feature | feat |
| integration | feat |
| bugfix | fix |
| change | feat when it adds behavior, fix when it corrects behavior |
| refactor | refactor |
| project | feat |

Other Conventional Commit types (`docs`, `test`, `perf`, `chore`) only when
the actual diff genuinely justifies them (e.g. a task that turned out to be
tests-only → `test`).

## Scope

The primary module of the change, lowercase (`stock`, `purchases`,
`telegram`). One scope; when a task truly spans modules, pick the dominant
one from the diff, not from the plan's ambitions.

## Subject Rules

- Imperative mood ("add", "correct", "centralize"), ≤ 72 characters.
- Describes the approved behavior, not the process ("fix review findings"
  is wrong; "correct base unit price calculation" is right).

## Body Rules

- Bullets describe behavior visible in the diff, not file names.
- Include the body when the subject alone cannot convey the behavior set;
  omit it for genuinely small changes.

## Never Include

```text
Co-Authored-By
Claude
Codex
AI-generated
```

or any other attribution/trailer of the sort.

## Examples

```text
feat(stock): add unified temporary stock reservation
fix(purchases): correct base unit price calculation
feat(telegram): add scheduled reporting integration
refactor(stock): centralize reservation validation
```
