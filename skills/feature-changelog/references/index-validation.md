# Index Validation

Run after **every** registry edit:

```bash
bin/frappe-workflow feature validate-index
```

Deterministic checks (implemented in
`scripts/core/feature_registry.validate_registry`; rule IDs in brackets):

| Check | Rule ID |
|---|---|
| Every Index ID has a detailed entry | `REG_NO_ENTRY` |
| Every detailed entry appears in the Index | `REG_NOT_IN_INDEX` |
| No duplicate IDs (index or entries) | `REG_DUP_INDEX_ID`, `REG_DUP_ENTRY_ID` |
| Index/entry name match | `REG_NAME_MISMATCH` |
| Index/entry module match | `REG_MODULE_MISMATCH` |
| Index/entry type match | `REG_TYPE_MISMATCH` |
| Index/entry status match | `REG_STATUS_MISMATCH` |
| Status is a valid value | `REG_STATUS` |
| `Replaced` entries carry `Replaced By` | `REG_REPLACED_NO_LINK` |
| Replacement targets exist | `REG_REPLACED_BY_MISSING`, `REG_REPLACES_MISSING` |
| Prefix matches type | `REG_PREFIX_TYPE` |
| ID number format valid (3+ digits) | `REG_ID_FORMAT` |
| Entry has an `- **ID:**` field | `REG_ENTRY_NO_ID` |

## On Failure

- Fix the registry inconsistency (usually a missed Index row or a stale
  status) and re-run.
- Never suppress a rule or hand-edit around the validator.
- If the failure predates this task (inherited registry damage), report it
  to the user before touching unrelated entries — repairing someone else's
  entries is a scope change.
