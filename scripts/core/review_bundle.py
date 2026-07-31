"""Codex review bundle generation and review-result parsing.

The bundle is a single Markdown prompt containing everything Codex needs to
review the implementation against the plan. Bundle content is secret-scanned
and the current implementation fingerprint is embedded and recorded in state.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from . import git_checks, project_files, security

REVIEW_STATUSES = ("APPROVED", "CHANGES_REQUIRED")

STATUS_RE = re.compile(r"^\s*-\s*\*\*Status:\*\*\s*(APPROVED|CHANGES_REQUIRED)\s*$", re.M)
FINDING_HEADING_RE = re.compile(r"^### \d+\.\s+(.+)$")
FINDING_REQUIRED_FIELDS = ("Severity", "Issue", "Required Fix")
SEVERITIES = ("High", "Medium", "Low")


class ReviewError(Exception):
    pass


def reviews_dir(repo_root: Path) -> Path:
    return Path(repo_root) / project_files.REVIEWS_DIR


def next_round(repo_root: Path) -> int:
    """Next review round number = highest existing prompt round + 1."""
    directory = reviews_dir(repo_root)
    highest = 0
    if directory.is_dir():
        for entry in directory.iterdir():
            match = re.match(r"^round-(\d{3})-(?:prompt|result)\.md$", entry.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return highest + 1


def prompt_path(repo_root: Path, round_number: int) -> Path:
    return reviews_dir(repo_root) / f"round-{round_number:03d}-prompt.md"


def result_path(repo_root: Path, round_number: int) -> Path:
    return reviews_dir(repo_root) / f"round-{round_number:03d}-result.md"


def _read_or_note(path: Path, missing_note: str) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return f"({missing_note})"


def build_prompt(repo_root: Path, round_number: int, fingerprint: str) -> str:
    """Assemble the review prompt Markdown (spec §21). Read-only."""
    repo_root = Path(repo_root)
    plan = _read_or_note(
        repo_root / project_files.TASK_PLAN,
        f"{project_files.TASK_PLAN} missing",
    )
    summary = _read_or_note(
        repo_root / project_files.IMPLEMENTATION_SUMMARY,
        f"{project_files.IMPLEMENTATION_SUMMARY} missing",
    )
    inspect = git_checks.inspect(repo_root)
    diff = git_checks._git(repo_root, "diff", "HEAD") if inspect["head"] else ""
    staged = (
        git_checks._git(repo_root, "diff", "--cached", "HEAD") if inspect["head"] else ""
    )

    sections = [
        f"# Codex Review Request — Round {round_number:03d}",
        "",
        "You are Codex, acting as a code reviewer.",
        "",
        "Review the implementation below against the task plan.",
        "Do NOT modify any repository file. Review only.",
        "",
        "Reply using exactly this result format:",
        "",
        "```markdown",
        "# Review Result",
        "",
        "- **Status:** APPROVED | CHANGES_REQUIRED",
        "",
        "## Findings",
        "",
        "### 1. Finding title",
        "",
        "- **Severity:** High | Medium | Low",
        "- **Plan Reference:** Implementation Step N (when applicable)",
        "- **File:** `path/to/file.py` (when applicable)",
        "- **Issue:** Exact problem.",
        "- **Required Fix:** Exact correction required.",
        "",
        "## Verified Items",
        "",
        "- Verified behavior.",
        "```",
        "",
        f"- **Implementation Fingerprint:** `{fingerprint}`",
        f"- **Branch:** `{inspect['branch']}`",
        f"- **HEAD:** `{inspect['head']}`",
        "",
        "---",
        "",
        "## Task Plan",
        "",
        plan,
        "",
        "---",
        "",
        "## Implementation Summary",
        "",
        summary,
        "",
        "---",
        "",
        "## Git Status",
        "",
        "```",
        "\n".join(inspect["status"]) or "(clean)",
        "```",
        "",
        "## Changed Files",
        "",
        "\n".join(f"- `{f}`" for f in inspect["changed_files"]) or "(none)",
        "",
        "## Untracked Files",
        "",
        "\n".join(f"- `{f}`" for f in inspect["untracked_files"]) or "(none)",
        "",
        "## Diff (working tree vs HEAD)",
        "",
        "```diff",
        diff or "(empty)",
        "```",
        "",
        "## Staged Diff",
        "",
        "```diff",
        staged or "(empty)",
        "```",
        "",
    ]
    return "\n".join(sections)


def create_bundle(repo_root: Path) -> dict:
    """Create the next round's prompt file after a secret scan.

    Raises :class:`ReviewError` when the bundle would contain a blocking
    secret. Returns metadata: round, path, fingerprint.
    """
    repo_root = Path(repo_root)
    round_number = next_round(repo_root)
    fingerprint = git_checks.implementation_fingerprint(repo_root)
    content = build_prompt(repo_root, round_number, fingerprint)

    # Scan both the rendered bundle and the implementation files themselves
    # (untracked file contents are not part of the rendered diff).
    candidates = set(git_checks.changed_files(repo_root))
    candidates.update(git_checks.staged_files(repo_root))
    candidates.update(git_checks.untracked_files(repo_root))
    findings = security.blocking_findings(
        security.scan_text("(review bundle)", content)
        + security.scan_files(repo_root, candidates)
    )
    if findings:
        rendered = "\n".join(f.render() for f in findings)
        raise ReviewError(
            "Refusing to create review bundle: possible secrets detected.\n" + rendered
        )

    path = prompt_path(repo_root, round_number)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {
        "round": round_number,
        "prompt_path": str(path.relative_to(repo_root)),
        "fingerprint": fingerprint,
    }


def parse_result(text: str) -> dict:
    """Parse a Codex review result. Rejects malformed output (spec §21).

    Returns ``{"status": ..., "findings": [...], "verified_items": [...]}``.
    """
    match = STATUS_RE.search(text)
    if not match:
        raise ReviewError(
            "Review result is malformed: missing '- **Status:** APPROVED' or "
            "'- **Status:** CHANGES_REQUIRED' line [REVIEW_NO_STATUS]"
        )
    status = match.group(1)

    findings: list[dict] = []
    current: Optional[dict] = None
    in_findings = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_findings = stripped.lstrip("#").strip() == "Findings"
            if not in_findings and current:
                findings.append(current)
                current = None
            continue
        if not in_findings:
            continue
        heading = FINDING_HEADING_RE.match(stripped)
        if heading:
            if current:
                findings.append(current)
            current = {"title": heading.group(1).strip(), "fields": {}}
            continue
        if current is not None:
            meta = re.match(r"^- \*\*([^:*]+):\*\*\s*(.*)$", stripped)
            if meta:
                current["fields"][meta.group(1).strip()] = meta.group(2).strip()
    if current:
        findings.append(current)

    if status == "CHANGES_REQUIRED" and not findings:
        raise ReviewError(
            "Review result is malformed: CHANGES_REQUIRED with no findings "
            "[REVIEW_NO_FINDINGS]"
        )
    for finding in findings:
        for field in FINDING_REQUIRED_FIELDS:
            if field not in finding["fields"] or not finding["fields"][field]:
                raise ReviewError(
                    f"Finding '{finding['title']}' missing '{field}' "
                    "[REVIEW_FINDING_FIELD]"
                )
        severity = finding["fields"]["Severity"]
        if severity not in SEVERITIES:
            raise ReviewError(
                f"Finding '{finding['title']}' has invalid severity {severity!r} "
                "[REVIEW_FINDING_SEVERITY]"
            )

    verified: list[str] = []
    in_verified = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_verified = stripped.lstrip("#").strip() == "Verified Items"
            continue
        if in_verified and stripped.startswith("- "):
            verified.append(stripped[2:].strip())

    return {"status": status, "findings": findings, "verified_items": verified}
