# Approval Invalidation

Codex approval applies to one specific implementation state, identified by
the implementation fingerprint.

## The Fingerprint

Computed by `bin/frappe-workflow review fingerprint`
(`scripts/core/git_checks.implementation_fingerprint`): SHA-256 over

- `git diff --binary HEAD` (working tree),
- the staged binary diff,
- sorted names **and contents** of untracked non-ignored files.

No timestamps, stable path order → identical tree ⇒ identical fingerprint;
any content change ⇒ different fingerprint. The fingerprint represents
**application implementation changes only**, so these are outside it by
construction:

- Ignored files.
- The entire `docs/ai-context/` directory — the plan, the workflow state,
  the implementation summary, the review history, and the
  AI documentation. These are tracked by Git for cross-device continuation,
  but they are not application behavior, so writing them never invalidates
  an approval. Untracked files inside the directory are excluded too.
- The entire `.claude/` directory — machine-local state.

Both directories are excluded by Git pathspec **and** in the untracked-file
scan, independently of `.gitignore`, so the rule holds even in a repository
whose managed block is missing. An untracked application file outside those
two directories still changes the fingerprint, as it must.

## Recorded When

Each `review bundle` embeds and records the fingerprint in
`codex_review.implementation_fingerprint`.

## Checked When

- **Accepting APPROVED** — recomputed and compared; mismatch rejects the
  approval (the approval belongs to code that no longer exists).
- **Finalization gate** — `[FINAL_FINGERPRINT_MISMATCH]` fails commit
  preparation.
- **Resume/no-action in `ready_for_commit`** — consistency check.

## After Approval

Any code or behavior change while in `ready_for_commit` invalidates the
approval:

```bash
bin/frappe-workflow state transition review_fixes --reason "approval invalidated: implementation changed"
```

then the fix loop produces a new round.

## Shared-Context Exception

Documentation and workflow edits do not require re-review **only** when
both hold:

1. The files are under `docs/ai-context/` — in practice
   `docs/ai-context/FEATURE_CHANGELOG.md`,
   `docs/ai-context/PROJECT_CONTEXT.md`, `docs/ai-context/TASK_PLAN.md`,
   `docs/ai-context/task-workflow.json`,
   `docs/ai-context/implementation-summary.md`, and
   `docs/ai-context/reviews/`.
2. They cannot affect application behavior.

The fingerprint already excludes that directory, so the deterministic
comparison enforces this automatically: edits inside it keep the
fingerprint stable, edits to **any** application file change it and fail
the finalization gate. Excluding the directory from the *fingerprint* is
not the same as excluding it from *security scanning* — the shared files
are still scanned for accidentally pasted secrets before staging and
completion. The git-finalization skill additionally sanity-checks
`git diff --name-only` so a surprising post-approval edit is reported by
name, not just as a hash mismatch.
