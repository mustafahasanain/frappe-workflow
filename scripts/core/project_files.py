"""Paths and helpers for files the plugin manages inside a target app repo.

This module is the single source of truth for every managed location. No
other module, skill, or test may spell one of these paths out.

Shareable AI context and workflow files live under ``docs/ai-context/`` so
they can be tracked by Git and used across multiple development machines.
Machine-specific configuration remains under ``.claude/`` and is the only
thing the managed ``.gitignore`` block excludes.

Also here: the idempotent managed ``.gitignore`` block, migration from the
old root-level / ``.claude/`` layout, and a small dependency-free
frontmatter parser used by the validators. The parser supports a strict
YAML subset: ``key: value`` scalars and ``- item`` lists.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional, Tuple

AI_CONTEXT_DIR = "docs/ai-context"

PROJECT_CONTEXT = f"{AI_CONTEXT_DIR}/PROJECT_CONTEXT.md"
FEATURE_CHANGELOG = f"{AI_CONTEXT_DIR}/FEATURE_CHANGELOG.md"
TASK_PLAN = f"{AI_CONTEXT_DIR}/TASK_PLAN.md"
WORKFLOW_STATE = f"{AI_CONTEXT_DIR}/task-workflow.json"
IMPLEMENTATION_SUMMARY = f"{AI_CONTEXT_DIR}/implementation-summary.md"
REVIEWS_DIR = f"{AI_CONTEXT_DIR}/reviews"

# The Arabic testing task is terminal output only: the `testing` action
# prints the title and description for the user to copy, and writes no file.
# There is deliberately no path constant for it. Older plugin versions did
# save `.claude/testing-task-ar.md` (and later
# `docs/ai-context/testing-task-ar.md`); such files are legacy artifacts —
# never created, read, staged, migrated, or deleted by the plugin, and left
# exactly where they are.

CLAUDE_DIR = ".claude"
DEPLOYMENT_CONFIG = f"{CLAUDE_DIR}/deployment.local.json"
WORKFLOW_LOCK = f"{CLAUDE_DIR}/task-workflow.lock"

# Shared files that belong to the application repository and are meant to be
# committed, so an active task can continue on another computer.
TRACKED_SHARED_FILES = (
    PROJECT_CONTEXT,
    FEATURE_CHANGELOG,
    TASK_PLAN,
    WORKFLOW_STATE,
    IMPLEMENTATION_SUMMARY,
)

# Files created by `init` / the project documentation skills. The task-level
# artifacts (plan, state, summary, reviews) are deliberately absent: `init`
# never starts a task.
INIT_CREATED_FILES = (
    PROJECT_CONTEXT,
    FEATURE_CHANGELOG,
)

# Active-task artifacts a confirmed `reset` clears. PROJECT_CONTEXT.md,
# FEATURE_CHANGELOG.md, and the machine-local deployment config are not here
# and must never be removed by a reset. A legacy `testing-task-ar.md` left
# by an older plugin version is not an active workflow file either, so reset
# leaves it alone.
RESET_PATHS = (
    WORKFLOW_STATE,
    TASK_PLAN,
    IMPLEMENTATION_SUMMARY,
    REVIEWS_DIR,
)

GITIGNORE_BEGIN = "# BEGIN Frappe Workflow Plugin local state"
GITIGNORE_END = "# END Frappe Workflow Plugin local state"

# Only genuinely machine-specific state is ignored. Everything under
# docs/ai-context/ is shared and must stay trackable.
GITIGNORE_ENTRIES = (
    DEPLOYMENT_CONFIG,
    WORKFLOW_LOCK,
)

# Entries earlier plugin versions wrote into the managed block. They are
# listed only so the block repair can recognize and drop them; nothing else
# should reference them. `.claude/testing-task-ar.md` is kept here for that
# single purpose — the plugin no longer produces such a file at all.
LEGACY_GITIGNORE_ENTRIES = (
    f"{CLAUDE_DIR}/task-workflow.json",
    f"{CLAUDE_DIR}/implementation-summary.md",
    f"{CLAUDE_DIR}/testing-task-ar.md",
    f"{CLAUDE_DIR}/reviews/",
)

# Old layout → new layout. Used by the migration helper and by nothing else:
# no runtime code may read from an old path. Only files the plugin still
# manages are migrated; `.claude/testing-task-ar.md` is intentionally absent
# because no testing-task file is part of the workflow any more.
LEGACY_PATHS: tuple[tuple[str, str], ...] = (
    ("PROJECT_CONTEXT.md", PROJECT_CONTEXT),
    ("FEATURE_CHANGELOG.md", FEATURE_CHANGELOG),
    ("TASK_PLAN.md", TASK_PLAN),
    (f"{CLAUDE_DIR}/task-workflow.json", WORKFLOW_STATE),
    (f"{CLAUDE_DIR}/implementation-summary.md", IMPLEMENTATION_SUMMARY),
    (f"{CLAUDE_DIR}/reviews", REVIEWS_DIR),
)


def managed_block_lines() -> list[str]:
    return [GITIGNORE_BEGIN, *GITIGNORE_ENTRIES, GITIGNORE_END]


def ensure_gitignore_block(repo_root: Path) -> dict:
    """Idempotently ensure the managed block exists in ``.gitignore``.

    Never replaces the whole file; preserves every existing line. Returns a
    dict describing what happened: ``{"changed": bool, "action": str}``.
    """
    path = Path(repo_root) / ".gitignore"
    block = managed_block_lines()

    if not path.exists():
        path.write_text("\n".join(block) + "\n", encoding="utf-8")
        return {"changed": True, "action": "created"}

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    begin_indexes = [i for i, line in enumerate(lines) if line.strip() == GITIGNORE_BEGIN]
    end_indexes = [i for i, line in enumerate(lines) if line.strip() == GITIGNORE_END]

    if begin_indexes and end_indexes and len(begin_indexes) == 1 and len(end_indexes) == 1:
        begin, end = begin_indexes[0], end_indexes[0]
        if begin < end:
            existing = [line.strip() for line in lines[begin : end + 1]]
            if existing == block:
                return {"changed": False, "action": "unchanged"}

            # Repair only the managed block; everything else is preserved.
            new_lines = lines[:begin] + block + lines[end + 1 :]
            path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            return {"changed": True, "action": "repaired"}

    if begin_indexes or end_indexes:
        # Unbalanced or duplicated markers: do not guess, report instead.
        return {
            "changed": False,
            "action": "conflict",
            "detail": (
                ".gitignore contains unbalanced or duplicated managed-block "
                "markers; repair it manually before rerunning."
            ),
        }

    suffix = "" if text.endswith("\n") or text == "" else "\n"
    appended = text + suffix + "\n".join(block) + "\n"
    path.write_text(appended, encoding="utf-8")
    return {"changed": True, "action": "appended"}


# --------------------------------------------------------------------------
# Legacy layout migration
# --------------------------------------------------------------------------

def migrate_legacy_layout(repo_root: Path, dry_run: bool = False) -> dict:
    """Move an old-layout application onto ``docs/ai-context/``.

    Applications initialized before the shared-context layout keep their
    files at the repository root and under ``.claude/``. Each old path is
    moved to its new path when — and only when — the new path does not yet
    exist; contents (including the whole review history) are preserved.

    A path that exists in *both* layouts is a conflict: the two versions
    cannot be merged safely. The whole plan is computed before anything is
    touched, so a single conflict aborts the migration entirely — a
    half-migrated repository would be harder to reason about than the
    original one. ``.claude/deployment.local.json`` stays machine-local and
    is never part of the plan.

    The operation is idempotent: a repository already on the new layout
    reports no moves and no conflicts.

    Returns ``{"changed": bool, "moved": [...], "conflicts": [...]}`` where
    each entry is ``{"from": old, "to": new}``.
    """
    repo_root = Path(repo_root)
    planned: list[dict] = []
    conflicts: list[dict] = []

    for old_rel, new_rel in LEGACY_PATHS:
        old_path = repo_root / old_rel
        new_path = repo_root / new_rel

        if not old_path.exists():
            continue

        if new_path.exists():
            conflicts.append({"from": old_rel, "to": new_rel})
            continue

        planned.append({"from": old_rel, "to": new_rel})

    if conflicts:
        return {
            "changed": False,
            "moved": [],
            "conflicts": conflicts,
            "gitignore": {"changed": False, "action": "skipped"},
        }

    if dry_run:
        return {
            "changed": bool(planned),
            "moved": planned,
            "conflicts": [],
            "gitignore": {"changed": False, "action": "skipped"},
        }

    for item in planned:
        new_path = repo_root / item["to"]
        new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(repo_root / item["from"]), str(new_path))

    return {
        "changed": bool(planned),
        "moved": planned,
        "conflicts": [],
        "gitignore": ensure_gitignore_block(repo_root),
    }


def parse_frontmatter(text: str) -> Tuple[Optional[dict], str]:
    """Parse a leading ``---`` frontmatter block.

    Returns ``(mapping_or_None, body)``. Supports scalar ``key: value`` pairs
    and simple ``- item`` lists nested one level under a key. Anything more
    complex is intentionally unsupported.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text

    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, text

    data: dict = {}
    current_list_key: Optional[str] = None

    for line in lines[1:end]:
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- ") and current_list_key is not None:
            data[current_list_key].append(stripped[2:].strip())
            continue

        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if value == "":
                data[key] = []
                current_list_key = key
            else:
                data[key] = _coerce(value)
                current_list_key = None
        else:
            current_list_key = None

    body = "\n".join(lines[end + 1 :])
    return data, body


def _coerce(value: str):
    if value in ("null", "~"):
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def extract_sections(markdown: str) -> list[str]:
    """Return all heading titles, at any level, in *markdown*, in order."""
    sections = []
    in_code = False

    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue

        if in_code:
            continue

        stripped = line.strip()
        if stripped.startswith("#"):
            sections.append(stripped.lstrip("#").strip())

    return sections
