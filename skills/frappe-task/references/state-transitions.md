# State Transitions

Enforced by `scripts/core/workflow_state.py`; attempted via
`bin/frappe-workflow state transition <stage> [--reason ...]`. Any pair not
listed is rejected with `[TRANSITION_REJECTED]` (exit code 5).

## Allowed Transition Table

```text
planning        → implementation

implementation  → codex_review
implementation  → implementation      (progress checkpoint)

codex_review    → review_fixes        (CHANGES_REQUIRED)
codex_review    → ready_for_commit    (valid APPROVED + matching fingerprint)

review_fixes    → codex_review        (next round bundle created)
review_fixes    → review_fixes        (multi-finding progress)

ready_for_commit → review_fixes       (approval invalidated by code change)
ready_for_commit → committed          (user-executed, verified commit)

committed       → deployed            (verified deployment)
committed       → deployment_skipped  (user chose skip)

deployed            → completed       (testing task generated)
deployment_skipped  → completed       (testing task generated)
```

`completed` has no outgoing transitions. A controlled reset
(`state init --force` after confirmation) is not a transition.

## Diagram

```text
planning ──► implementation ⟲ ──► codex_review ──► ready_for_commit ──► committed
                                   ▲        │            │                │    │
                                   │        ▼            ▼(invalidated)   ▼    ▼
                                   └── review_fixes ⟲ ◄──┘          deployed  deployment_
                                                                        │       skipped
                                                                        ▼         │
                                                                    completed ◄───┘
```

## Transition Records

Every transition appends to `transition_history` in the state file:

```json
{
  "from": "implementation",
  "to": "codex_review",
  "at": "2026-07-27T10:15:00Z",
  "reason": "review prompt round 001",
  "round": 1
}
```

Pass context via `--reason`; the codex-review and git-finalization skills
add the review round or commit hash through their state updates.

## Guarded Transitions

The engine enforces the *shape*; the skills enforce the *gates* before
requesting a transition:

| Transition | Gate that must pass first |
|---|---|
| planning → implementation | planning gate (plan validated + accepted) |
| implementation → codex_review | completion gate + bundle created |
| codex_review → ready_for_commit | valid APPROVED + fingerprint match + finalization gate |
| ready_for_commit → committed | user-executed commit verified |
| committed → deployed | explicit consent + preflight + verification |
| committed → deployment_skipped | explicit user skip |
| deployed → completed | testing task generated |
| deployment_skipped → completed | testing task generated |

Requesting a transition without its gate is a workflow violation even when
the engine would accept the shape.
