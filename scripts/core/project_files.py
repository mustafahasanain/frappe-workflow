"""Paths and helpers for files the plugin manages inside a target app repo.

Includes the idempotent managed .gitignore block and a small dependency-free
frontmatter parser used by the validators (a strict YAML subset: ``key: value``
scalars and ``- item`` lists).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

PROJECT_CONTEXT = "PROJECT_CONTEXT.md"
FEATURE_CHANGELOG = "FEATURE_CHANGELOG.md"
TASK_PLAN = "TASK_PLAN.md"
CLAUDE_DIR = ".claude"
IMPLEMENTATION_SUMMARY = ".claude/implementation-summary.md"
TESTING_TASK_AR = ".claude/testing-task-ar.md"
REVIEWS_DIR = ".claude/reviews"
DEPLOYMENT_CONFIG = ".claude/deployment.local.json"

GITIGNORE_BEGIN = "# BEGIN Frappe Workflow Plugin local state"
GITIGNORE_END = "# END Frappe Workflow Plugin local state"
GITIGNORE_ENTRIES = (
    ".claude/task-workflow.json",
    ".claude/deployment.local.json",
    ".claude/implementation-summary.md",
    ".claude/testing-task-ar.md",
    ".claude/reviews/",
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
    """Return all heading titles (any level) in *markdown*, in order."""
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
