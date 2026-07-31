# Workflow Gates

Gates are hard checkpoints. A failed gate stops the workflow with the full
error list; there are no override flags.

## Planning Gate (before `planning → implementation`)

- `bin/frappe-workflow validate task-plan` passes (frontmatter, sections,
  step structure).
- Every "Requires repository verification" location has been verified or is
  explicitly listed under "Repository Verification Required".
- Existing-feature analysis was performed (feature-changelog skill) and its
  outcome recorded in the plan.
- Target Site selected (or the plan explicitly notes why none is needed).
- The user has seen the plan; for ready-plan input, corrections made during
  standardization were reported.

## Completion Gate (before `implementation → codex_review`)

Deterministic part: `bin/frappe-workflow validate completion-gate`, which
checks:

- Plan valid; **every** step `Completed` (no Pending / In Progress /
  Blocked).
- Stage is `implementation` or `review_fixes`.
- No unresolved blockers in state.
- `docs/ai-context/implementation-summary.md` exists.
- Secret scan over changed + staged + untracked files is clean.

Judgment part (the skill must verify and attest in the summary):

- Every step's validation actually ran; required tests passed (real output).
- Git diff contains only task-related changes.
- No debug code or temporary files remain.
- `docs/ai-context/PROJECT_CONTEXT.md` updated if architecture changed.
- `docs/ai-context/FEATURE_CHANGELOG.md` **not yet** updated (that happens
  at finalization).

The bundle step then records the implementation fingerprint.

## Approval Gate (inside `apply-review`)

- Result parses with exactly `APPROVED` or `CHANGES_REQUIRED`.
- `APPROVED` only counts when `bin/frappe-workflow review fingerprint`
  equals `codex_review.implementation_fingerprint` in state. A mismatch
  means the code changed after the prompt was generated → reject the
  approval and create a new bundle.

## Finalization Gate (before commit preparation)

`bin/frappe-workflow validate finalization-gate`:

- Stage is `codex_review` or `ready_for_commit` — the only two stages from
  which finalization legitimately runs [`FINAL_WRONG_STAGE`].
- The target is a Git repository; without one the fingerprint cannot be
  verified, so approval cannot be trusted [`FINAL_NO_GIT`].
- `codex_review.status == "approved"` [`FINAL_NOT_APPROVED`] with a
  recorded fingerprint [`FINAL_NO_FINGERPRINT`].
- Current fingerprint still matches the approved one
  [`FINAL_FINGERPRINT_MISMATCH`].
- `docs/ai-context/TASK_PLAN.md` exists [`FINAL_NO_PLAN`] and is
  structurally valid — the full `validate task-plan` ruleset runs here too,
  so a malformed plan, missing frontmatter, or a missing required section
  cannot slip through [`FINAL_PLAN_INVALID`, plus the underlying `PLAN_*`
  errors].
- `docs/ai-context/TASK_PLAN.md` status is `codex_approved` (or already
  `committed`) [`FINAL_PLAN_STATUS`].
- Secret scan clean [`FINAL_SECRET`].

All checks accumulate: one run reports every problem, not just the first.

Plus (skill judgment): review record present in the plan, documentation
updates done at this stage only, no unrelated changes in the diff, no
unrelated files already staged.

## Approval Invalidation

After `ready_for_commit`, any change to implementation files changes the
fingerprint; the finalization gate then fails with
`[FINAL_FINGERPRINT_MISMATCH]` → transition `ready_for_commit →
review_fixes` and run another review round.

**Shared-context exception:** the fingerprint excludes `docs/ai-context/`
and `.claude/` entirely, by construction (see
`skills/codex-review/references/approval-invalidation.md`). Documentation
and workflow updates that cannot affect runtime behavior — the feature
changelog, the project context, the plan, the workflow state, the
implementation summary, the review history — are part of
finalization or bookkeeping, so editing them after approval keeps the
comparison stable while any application edit fails it. The git-finalization
skill additionally checks `git diff --name-only` so a surprising
post-approval edit is reported by name.

## Deployment Gates

- The deploy/skip question must be answered explicitly; no SSH before it.
- Local preflight: task committed, hash recorded, branch known, commit
  present on the expected remote, config consistent with the task
  (`deployment validate-config`, `deployment preflight`).
- Remote preflight (read-only): connection works, paths exist, branch
  expected, tree clean, remote commit present, fast-forward possible.
- Verification: server HEAD equals the task commit and every selected bench
  command succeeded, else the deployment is reported failed — never
  "mostly done".
