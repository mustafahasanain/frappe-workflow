# Existing Feature Analysis (planning-side)

The feature-changelog skill owns detection mechanics
(`skills/feature-changelog/references/feature-detection.md`). This file
covers how planning consumes the result.

## Before Writing Any Plan

1. Run the feature search on the task's behavioral keywords.
2. Inspect Main Files of every match scoring ≥ 60.
3. Classify: already implemented / incomplete / differs / extension /
   regression / new.

## How the Classification Shapes the Plan

| Classification | Plan consequence |
|---|---|
| Already complete | No task. Report to the user with the evidence (entry + files). |
| Incomplete implementation | Plan completes it; `related_features` carries the ID; Current Behavior describes what exists. |
| Requested behavior differs | `task_type: change`; plan states old vs new behavior explicitly. |
| Extension | Same feature ID in `related_features`; Out of Scope states what the existing feature already covers. |
| Regression | `task_type: bugfix`; Current Behavior cites the broken behavior and, when findable, the breaking change. |
| New | Fresh plan; Existing Feature Analysis records why nothing matched. |

## Duplicate-Work Guard

When the user's input asks for something the registry marks Active and the
code confirms works, do not plan "reimplementation" — present the finding.
The user may still decide the behavior differs; that becomes a `change`
task with the difference spelled out.

## Record

The plan's "Existing Feature Analysis" section always contains: search
terms used, matches with scores, files inspected, classification, and
reasoning. This section is what the Codex reviewer uses to check scope.
