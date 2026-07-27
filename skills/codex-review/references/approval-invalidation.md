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
any content change ⇒ different fingerprint. Two categories are outside the
fingerprint by construction:

- Ignored files, and the entire `.claude/` directory (excluded by
  construction, independent of `.gitignore`) — state updates and review
  files never invalidate anything.
- The three categorized finalization files (`TASK_PLAN.md`,
  `FEATURE_CHANGELOG.md`, `PROJECT_CONTEXT.md`), excluded via Git
  pathspecs — so post-approval documentation finalization keeps the
  approval valid.

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

## Finalization-File Exception

Documentation-only finalization edits do not require re-review **only**
when both hold:

1. The files are exactly the categorized finalization files:
   `FEATURE_CHANGELOG.md`, `PROJECT_CONTEXT.md`, `TASK_PLAN.md`.
2. They cannot affect application behavior (they are documentation).

The fingerprint already excludes exactly these three paths, so the
deterministic comparison enforces this automatically: edits to them keep
the fingerprint stable, edits to **any** other file change it and fail the
finalization gate. The git-finalization skill additionally sanity-checks
`git diff --name-only` so a surprising post-approval edit is reported by
name, not just as a hash mismatch.
