# Incremental Analysis

Performed when `docs/ai-context/PROJECT_CONTEXT.md` exists. Never reread
the whole
repository unless the old context is missing, invalid, or clearly obsolete.

## Procedure

1. Read the frontmatter; get `analyzed_commit`.
2. `git rev-parse HEAD` — if equal to `analyzed_commit`, nothing to do.
3. Otherwise:

```bash
git diff --name-only <analyzed_commit>..HEAD
```

4. From the changed file list, read **only** files that may affect:
   - Architecture, navigation, core DocTypes, main services,
   - hooks/overrides (`hooks.py` changes always qualify),
   - integrations, testing workflow, deployment workflow.

   Ignore for context purposes: formatting-only changes, test-data tweaks,
   translations, minor CSS, files already accurately described.

5. Apply the update decision from
   [context-update-rules.md](context-update-rules.md) per affected section.
6. Update `analyzed_commit` to the new HEAD **even when no content changed**
   (that records "verified up to this commit"). Bump `context_version` only
   when content changed. Update `generated_at`.
7. `bin/frappe-workflow validate project-context` must pass.

## Failure Handling

- `analyzed_commit` not found in history (rebase, shallow clone): report
  it; fall back to a full re-analysis only if the content is visibly stale,
  otherwise update the sections related to the current task and set
  `analyzed_commit` to HEAD with a note in Known Constraints.
- Frontmatter unparseable: report; treat as "clearly obsolete" → full
  analysis.
