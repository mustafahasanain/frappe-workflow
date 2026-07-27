# Feature ID Rules

## Format

```text
<TYPE-PREFIX>-<MODULE>-<NUMBER>
```

Examples: `FEAT-STOCK-001`, `BUG-SELLING-001`, `CHANGE-PURCHASE-001`,
`INT-MRN-001`, `INT-TELEGRAM-001`.

## Types and Prefixes

| Type | Prefix |
|---|---|
| FEATURE | FEAT |
| CHANGE | CHANGE |
| BUGFIX | BUG |
| INTEGRATION | INT |
| REMOVED | REMOVE |

## Module Token

- Uppercase; spaces and punctuation normalized to `_`
  (`Sales Invoice` → `SALES_INVOICE`). The normalization is implemented in
  `scripts/core/feature_registry.normalize_module_token` — use the CLI, do
  not normalize by hand.
- The token is stable: once a module has entries under one token, reuse it.

## Numbering

- Sequential within the same (type, module) pair.
- Three-digit padding (`001`, `002`, …; grows past 999 without reuse).
- Computed only by:

```bash
bin/frappe-workflow feature next-id --type <FEATURE|CHANGE|BUGFIX|INTEGRATION|REMOVED> --module "<Module>"
```

which scans both the Index and the detailed entries, so a half-edited file
still never reuses a number. **Never** calculate an ID by guessing.

## Immutability

- Existing IDs never change; renaming a feature keeps its ID.
- A new ID is created only for an independent functional capability.
- Extensions and fixes of an existing capability update the existing entry.

## Statuses

Only `Active`, `Deprecated`, `Replaced`, `Removed`. Never `Pending`,
`In Progress`, `Completed`, `Done` — the registry records shipped behavior,
not work in flight.

Replacement linkage:

```markdown
- **Status:** Replaced
- **Replaced By:** FEAT-STOCK-002
```

and optionally on the replacement:

```markdown
- **Replaces:** FEAT-STOCK-001
```

Both link targets must exist; `feature validate-index` enforces it.
