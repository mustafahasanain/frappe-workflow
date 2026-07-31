# Finalization Gate

Runs after approval, before commit preparation, in this order:

## 1. Documentation Finalization (this is the correct — and only — time)

1. `docs/ai-context/FEATURE_CHANGELOG.md`: apply the feature-changelog
   skill's update
   rules (new entry / extension / bugfix history / replacement), then
   `bin/frappe-workflow feature validate-index`.
2. `docs/ai-context/PROJECT_CONTEXT.md`: only when the update-decision
   question says yes
   (project-context skill); bump `analyzed_commit` will happen naturally on
   the next incremental run after commit.
3. `docs/ai-context/TASK_PLAN.md`: set frontmatter `status: codex_approved`,
   `updated_at`, and append the review record:

```markdown
## Review Result

- **Reviewer:** Codex
- **Status:** Approved
- **Review Round:** <N>
- **Approved At:** <YYYY-MM-DD>
```

## 2. Deterministic Gate

```bash
bin/frappe-workflow validate finalization-gate
```

checks, accumulating every failure in one run:

- stage is `codex_review` or `ready_for_commit` [`FINAL_WRONG_STAGE`];
- the target is a Git repository [`FINAL_NO_GIT`] — without it the
  fingerprint cannot be verified at all;
- approval status + recorded fingerprint [`FINAL_NOT_APPROVED`,
  `FINAL_NO_FINGERPRINT`];
- current fingerprint match [`FINAL_FINGERPRINT_MISMATCH`] (the fingerprint
  excludes the three finalization files, so step 1's edits do not trip it);
- `docs/ai-context/TASK_PLAN.md` present [`FINAL_NO_PLAN`] and
  structurally valid — the
  whole `validate task-plan` ruleset [`FINAL_PLAN_INVALID`];
- plan status [`FINAL_PLAN_STATUS`];
- secret scan [`FINAL_SECRET`].

## 3. Judgment Checks

- `git diff --name-only` since approval touched only implementation files
  present at approval + the three finalization files. Anything else →
  approval invalidated: `state transition review_fixes`, new round.
- No unrelated changes in the full diff (compare against the plan's
  Expected Files; investigate every surprise).
- No unrelated files already staged
  (`bin/frappe-workflow git changed-files` staged list) → stop and report
  if any.

## On Pass

`state transition ready_for_commit` (when coming from apply-review), then
prepare the commit per
[conventional-commits.md](conventional-commits.md) and
[task-file-staging.md](task-file-staging.md).

## Commit Verification (after user-requested execution)

1. Record old HEAD; run the prepared `git add`/`git commit` commands;
   read new HEAD.
2. Old ≠ new HEAD, and `git show --name-only <new>` lists exactly the
   approved task files (implementation + finalization docs).
3. Record the verified commit, then transition:

```bash
bin/frappe-workflow state set commit.status created
bin/frappe-workflow state set commit.hash <new HEAD>
bin/frappe-workflow state set commit.subject "<subject line>"
bin/frappe-workflow state transition committed --reason "commit <short hash>"
```

   Also set `docs/ai-context/TASK_PLAN.md` frontmatter `status: committed`.
4. Any verification failure → report exactly what differs; do not retry
   automatically and do not amend.
