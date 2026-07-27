# Codex Review Request — Round <NNN>

You are Codex, acting as a code reviewer.

Review the implementation below against the task plan.
Do NOT modify any repository file. Review only.

Reply using exactly this result format:

```markdown
# Review Result

- **Status:** APPROVED | CHANGES_REQUIRED

## Findings

### 1. Finding title

- **Severity:** High | Medium | Low
- **Plan Reference:** Implementation Step N (when applicable)
- **File:** `path/to/file.py` (when applicable)
- **Issue:** Exact problem.
- **Required Fix:** Exact correction required.

## Verified Items

- Verified behavior.
```

- **Implementation Fingerprint:** `<sha256>`
- **Branch:** `<branch>`
- **HEAD:** `<commit>`

---

## Task Plan

<full TASK_PLAN.md content>

---

## Implementation Summary

<full .claude/implementation-summary.md content>

---

## Git Status

```
<git status --porcelain output>
```

## Changed Files

- `<file>`

## Untracked Files

- `<file>`

## Diff (working tree vs HEAD)

```diff
<git diff HEAD output>
```

## Staged Diff

```diff
<git diff --cached HEAD output>
```
