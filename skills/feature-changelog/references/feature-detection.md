# Feature Detection Before Planning

Run **before** creating or accepting any `TASK_PLAN.md`.

## Procedure

1. Extract the behavioral keywords from the task input (nouns: doctypes,
   modules, quantities; verbs: reserve, calculate, notify…).
2. `bin/frappe-workflow feature search "<keywords>"` — returns scored
   matches over ID, name, module, DocTypes, keywords, purpose, behavior,
   and main files.
3. Interpret the advisory score:

```text
90–100% = likely already implemented
60–89%  = related existing feature
below 60% = likely new functionality
```

4. **The score never decides.** For every match ≥ 60, open the entry's
   Main Files and verify what the code actually does.

## Outcome: Already Implemented

Inspect the entry and its files, then classify:

- Task already complete → report that; no task needed.
- Existing implementation incomplete → plan completes it (same ID).
- Requested behavior differs → plan is a change to the feature (same ID).
- Actually an extension → see below.
- A regression → bugfix task referencing the feature.

Never reject a task on text similarity alone.

## Outcome: Related Existing Feature

Overlapping behavior is normally an **extension**: reuse the same feature
ID, and the plan's "Existing Feature Analysis" section records the ID and
what the extension adds. Example: existing reservation supports Sales
Invoice; the request adds Sales Order → extend `FEAT-STOCK-001`.

## Outcome: New Functionality

No sufficiently related feature → propose the next deterministic ID:

```bash
bin/frappe-workflow feature next-id --type FEATURE --module "Stock"
```

Record the proposed ID in the plan's `related_features` only when related
entries exist; a genuinely new feature gets its ID at finalization (the
next-id is recomputed then, in case another task landed first).

## Record in the Plan

The plan's "Existing Feature Analysis" section always states: the search
terms, the top matches with scores, which files were inspected, and the
final classification with reasoning.
