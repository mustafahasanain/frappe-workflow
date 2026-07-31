# Review Prompt Generation

## Command

```bash
bin/frappe-workflow review bundle
```

creates `docs/ai-context/reviews/round-NNN-prompt.md` where NNN = highest existing
round + 1 (recounted from filenames — restart-safe). It aborts (exit 7)
when the bundle would contain a blocking secret.

## Bundle Contents (spec §21)

The generated prompt contains, in order:

- Reviewer instructions: review-only, no file modification, and the exact
  required result format (both APPROVED and CHANGES_REQUIRED shapes).
- The implementation fingerprint, branch, and HEAD.
- Full `docs/ai-context/TASK_PLAN.md` (includes plan deviations recorded
  in steps).
- Full implementation summary (test commands, test output summary,
  deviations, known limitations).
- `git status --porcelain`, changed files, untracked files.
- Full working-tree diff vs HEAD and the staged diff when present.

Template for reference: `templates/review/CODEX_REVIEW_PROMPT.md` (the CLI
builds the real one; the template documents the shape).

## After Generation

1. Record the bundle output in state:

```bash
bin/frappe-workflow state set codex_review.round <N> --json-value
bin/frappe-workflow state set codex_review.prompt_path docs/ai-context/reviews/round-NNN-prompt.md
bin/frappe-workflow state set codex_review.implementation_fingerprint <fingerprint>
bin/frappe-workflow state set codex_review.status awaiting_result
```

2. `bin/frappe-workflow state transition codex_review --reason "review prompt round NNN"`.
3. Tell the user: where the prompt file is, that they run it through Codex
   themselves, and that the verdict comes back via
   `/frappe-workflow:frappe-task apply-review`.

## Constraints

- One prompt per round; regenerating for the same implementation state
  creates the next round number (history is append-only).
- From this moment until a verdict arrives, implementation files must not
  change — any change desynchronizes the fingerprint and the approval will
  be rejected (see approval-invalidation.md).
