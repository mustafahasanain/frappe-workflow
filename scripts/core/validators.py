"""Deterministic validators for generated files and workflow gates.

Every validator returns a list of error strings; an empty list means valid.
Each error carries a bracketed rule identifier so skills and tests can match
on it. Validators never mutate anything.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from . import feature_registry, git_checks, project_files, security, workflow_state

# --------------------------------------------------------------------------
# PROJECT_CONTEXT.md
# --------------------------------------------------------------------------

PROJECT_CONTEXT_FRONTMATTER_KEYS = (
    "project_name",
    "context_version",
    "generated_at",
    "analyzed_commit",
)

PROJECT_CONTEXT_SECTIONS = (
    "Project Overview",
    "Application Structure",
    "Architecture",
    "Core DocTypes",
    "Business Logic",
    "Hooks and Overrides",
    "APIs and Integrations",
    "Background Jobs",
    "Permissions and Roles",
    "Testing and Development",
    "Deployment Notes",
    "Navigation Map",
    "Known Constraints",
)

COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
PLACEHOLDER_RE = re.compile(r"\b(TODO|FIXME|PLACEHOLDER|TBD)\b")


def validate_project_context(path: Path) -> list[str]:
    errors: list[str] = []
    path = Path(path)
    if not path.is_file():
        return [f"{path}: file not found [CTX_MISSING]"]
    text = path.read_text(encoding="utf-8")
    frontmatter, body = project_files.parse_frontmatter(text)
    if frontmatter is None:
        errors.append(f"{path}: missing frontmatter block [CTX_NO_FRONTMATTER]")
        body = text
    else:
        for key in PROJECT_CONTEXT_FRONTMATTER_KEYS:
            if key not in frontmatter or frontmatter[key] in (None, ""):
                errors.append(f"{path}: frontmatter missing '{key}' [CTX_FRONTMATTER_KEY]")
        commit = frontmatter.get("analyzed_commit")
        if isinstance(commit, str) and commit and not COMMIT_RE.match(commit):
            errors.append(
                f"{path}: analyzed_commit {commit!r} is not a commit hash [CTX_COMMIT_FORMAT]"
            )
    sections = project_files.extract_sections(body)
    for section in PROJECT_CONTEXT_SECTIONS:
        if section not in sections:
            errors.append(f"{path}: missing section '{section}' [CTX_SECTION]")
    if _is_placeholder_only(body):
        errors.append(f"{path}: content is placeholder-only [CTX_PLACEHOLDER]")
    return errors


def _is_placeholder_only(body: str) -> bool:
    meaningful = [
        line
        for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not meaningful:
        return True
    placeholderish = [line for line in meaningful if PLACEHOLDER_RE.search(line)]
    return len(placeholderish) == len(meaningful)


# --------------------------------------------------------------------------
# FEATURE_CHANGELOG.md
# --------------------------------------------------------------------------

def validate_feature_changelog(path: Path) -> list[str]:
    path = Path(path)
    if not path.is_file():
        return [f"{path}: file not found [REG_MISSING]"]
    text = path.read_text(encoding="utf-8")
    if "## Feature Index" not in text:
        return [f"{path}: missing '## Feature Index' section [REG_NO_INDEX]"]
    return [f"{path}: {e}" for e in feature_registry.validate_registry(text)]


# --------------------------------------------------------------------------
# TASK_PLAN.md
# --------------------------------------------------------------------------

TASK_TYPES = ("feature", "change", "bugfix", "integration", "refactor", "project")

TASK_PLAN_REQUIRED_FRONTMATTER = (
    "task_id",
    "task_title",
    "task_type",
    "status",
    "app_name",
)

TASK_PLAN_SECTIONS = (
    "Task Summary",
    "Objective",
    "Business Requirement",
    "Current Behavior",
    "Required Behavior",
    "Existing Feature Analysis",
    "Scope",
    "In Scope",
    "Out of Scope",
    "Assumptions",
    "Dependencies",
    "Repository Verification Required",
    "Implementation Plan",
    "Expected Files",
    "Data Model Changes",
    "Permissions and Security",
    "Backward Compatibility",
    "Migration and Deployment Requirements",
    "Testing Plan",
    "Acceptance Criteria",
    "Risks and Constraints",
)

STEP_STATUSES = ("Pending", "In Progress", "Completed", "Blocked")
TASK_ID_RE = re.compile(r"^TASK-\d{4}-\d{3,}$")

STEP_HEADING_RE = re.compile(r"^### \d+\.\s+.+$")
STEP_REQUIRED_FIELDS = ("Status", "Action", "Purpose", "Expected Result", "Validation", "Dependencies")


def parse_plan_steps(body: str) -> list[dict]:
    """Extract numbered implementation steps from the Implementation Plan section."""
    lines = body.splitlines()
    in_plan = False
    steps: list[dict] = []
    current: Optional[dict] = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_plan = stripped.lstrip("#").strip() == "Implementation Plan"
            if not in_plan and current:
                steps.append(current)
                current = None
            continue
        if not in_plan:
            continue
        if STEP_HEADING_RE.match(stripped):
            if current:
                steps.append(current)
            current = {"title": stripped.lstrip("#").strip(), "fields": {}}
            continue
        if current is not None:
            meta = re.match(r"^- \*\*([^:*]+):\*\*\s*(.*)$", stripped)
            if meta:
                key = meta.group(1).strip()
                if key not in current["fields"]:
                    current["fields"][key] = meta.group(2).strip()
    if current:
        steps.append(current)
    return steps


def validate_task_plan(path: Path) -> list[str]:
    errors: list[str] = []
    path = Path(path)
    if not path.is_file():
        return [f"{path}: file not found [PLAN_MISSING]"]
    text = path.read_text(encoding="utf-8")
    frontmatter, body = project_files.parse_frontmatter(text)
    if frontmatter is None:
        return [f"{path}: missing frontmatter block [PLAN_NO_FRONTMATTER]"]

    for key in TASK_PLAN_REQUIRED_FRONTMATTER:
        if key not in frontmatter or frontmatter[key] in (None, ""):
            errors.append(f"{path}: frontmatter missing '{key}' [PLAN_FRONTMATTER_KEY]")

    task_id = frontmatter.get("task_id")
    if isinstance(task_id, str) and task_id and not TASK_ID_RE.match(task_id):
        errors.append(f"{path}: task_id {task_id!r} is not TASK-YYYY-NNN [PLAN_TASK_ID]")

    task_type = frontmatter.get("task_type")
    if task_type and task_type not in TASK_TYPES:
        errors.append(f"{path}: unsupported task_type {task_type!r} [PLAN_TASK_TYPE]")

    status = frontmatter.get("status")
    if status and status not in workflow_state.TASK_PLAN_STATUSES[1:]:
        errors.append(f"{path}: unsupported status {status!r} [PLAN_STATUS]")

    sections = project_files.extract_sections(body)
    for section in TASK_PLAN_SECTIONS:
        if section not in sections:
            errors.append(f"{path}: missing section '{section}' [PLAN_SECTION]")

    steps = parse_plan_steps(body)
    if not steps:
        errors.append(f"{path}: Implementation Plan has no numbered steps [PLAN_NO_STEPS]")
    for step in steps:
        for field in STEP_REQUIRED_FIELDS:
            if field not in step["fields"] or not step["fields"][field]:
                errors.append(
                    f"{path}: step '{step['title']}' missing '{field}' [PLAN_STEP_FIELD]"
                )
        step_status = step["fields"].get("Status", "")
        if step_status and step_status not in STEP_STATUSES:
            errors.append(
                f"{path}: step '{step['title']}' has unsupported status "
                f"{step_status!r} [PLAN_STEP_STATUS]"
            )
        if step_status == "Blocked" and not step["fields"].get("Blocker"):
            errors.append(
                f"{path}: blocked step '{step['title']}' missing '- **Blocker:**' "
                "[PLAN_STEP_BLOCKER]"
            )
    return errors


# --------------------------------------------------------------------------
# Workflow state file
# --------------------------------------------------------------------------

def validate_workflow_state(repo_root: Path) -> list[str]:
    try:
        workflow_state.load_state(repo_root)
    except workflow_state.StateError as exc:
        return [str(exc)]
    return []


# --------------------------------------------------------------------------
# Completion gate (before Codex review) — spec §19
# --------------------------------------------------------------------------

def validate_completion_gate(repo_root: Path) -> list[str]:
    errors: list[str] = []
    repo_root = Path(repo_root)

    plan_path = repo_root / project_files.TASK_PLAN
    plan_errors = validate_task_plan(plan_path)
    if plan_errors:
        return plan_errors + ["completion gate: task plan invalid [GATE_PLAN_INVALID]"]

    text = plan_path.read_text(encoding="utf-8")
    _, body = project_files.parse_frontmatter(text)
    steps = parse_plan_steps(body)
    for step in steps:
        status = step["fields"].get("Status", "")
        if status != "Completed":
            errors.append(
                f"completion gate: step '{step['title']}' is {status or 'missing status'}, "
                "not Completed [GATE_STEP_INCOMPLETE]"
            )

    try:
        state = workflow_state.load_state(repo_root)
    except workflow_state.StateError as exc:
        return errors + [str(exc)]

    if state["current_stage"] not in ("implementation", "review_fixes"):
        errors.append(
            f"completion gate: stage is '{state['current_stage']}', expected "
            "'implementation' or 'review_fixes' [GATE_WRONG_STAGE]"
        )
    if state["blockers"]:
        errors.append(
            f"completion gate: {len(state['blockers'])} unresolved blocker(s) "
            "[GATE_BLOCKERS]"
        )

    summary_path = repo_root / project_files.IMPLEMENTATION_SUMMARY
    if not summary_path.is_file():
        errors.append(
            "completion gate: .claude/implementation-summary.md missing [GATE_NO_SUMMARY]"
        )

    # Security scan over changed + staged + untracked files.
    if git_checks.is_git_repo(repo_root):
        candidates = set(git_checks.changed_files(repo_root))
        candidates.update(git_checks.staged_files(repo_root))
        candidates.update(git_checks.untracked_files(repo_root))
        findings = security.blocking_findings(security.scan_files(repo_root, candidates))
        for finding in findings:
            errors.append(f"completion gate: {finding.render()} [GATE_SECRET]")
    else:
        errors.append("completion gate: target is not a Git repository [GATE_NO_GIT]")
    return errors


# --------------------------------------------------------------------------
# Finalization gate (after approval, before commit) — spec §22/§30
# --------------------------------------------------------------------------

# Stages from which finalization may legitimately run: accepting a valid
# Codex approval (codex_review) and preparing the commit (ready_for_commit).
FINALIZATION_STAGES = ("codex_review", "ready_for_commit")

# TASK_PLAN.md statuses that are acceptable at finalization time.
FINALIZATION_PLAN_STATUSES = ("codex_approved", "committed")


def validate_finalization_gate(repo_root: Path) -> list[str]:
    """Validate everything that must hold before a task commit is prepared.

    All checks accumulate so the caller sees every problem at once. Checks
    that require Git are skipped when the target is not a repository —
    their absence is reported once as ``FINAL_NO_GIT`` rather than silently
    passing, because an unverifiable fingerprint is not an approved one.
    """
    errors: list[str] = []
    repo_root = Path(repo_root)

    try:
        state = workflow_state.load_state(repo_root)
    except workflow_state.StateError as exc:
        return [str(exc)]

    stage = state["current_stage"]
    if stage not in FINALIZATION_STAGES:
        errors.append(
            f"finalization gate: stage is {stage!r}, expected 'codex_review' "
            "or 'ready_for_commit' [FINAL_WRONG_STAGE]"
        )

    # Without Git there is no diff to fingerprint and no file list to scan,
    # so approval cannot be tied to a specific implementation state.
    is_git_repo = git_checks.is_git_repo(repo_root)
    if not is_git_repo:
        errors.append(
            "finalization gate: target is not a Git repository; the "
            "implementation fingerprint cannot be verified [FINAL_NO_GIT]"
        )

    review = state["codex_review"]
    if review.get("status") != "approved":
        errors.append(
            f"finalization gate: codex_review.status is {review.get('status')!r}, "
            "not 'approved' [FINAL_NOT_APPROVED]"
        )
    recorded = review.get("implementation_fingerprint")
    if not recorded:
        errors.append(
            "finalization gate: no recorded implementation fingerprint [FINAL_NO_FINGERPRINT]"
        )
    elif is_git_repo:
        current = git_checks.implementation_fingerprint(repo_root)
        if current != recorded:
            errors.append(
                "finalization gate: implementation changed after approval "
                f"(recorded {recorded[:12]}…, current {current[:12]}…); another "
                "Codex review is required [FINAL_FINGERPRINT_MISMATCH]"
            )

    plan_path = repo_root / project_files.TASK_PLAN
    if not plan_path.is_file():
        errors.append("finalization gate: TASK_PLAN.md missing [FINAL_NO_PLAN]")
    else:
        # A present-but-malformed plan must not reach a commit: validate its
        # structure before trusting any field inside it.
        plan_errors = validate_task_plan(plan_path)
        if plan_errors:
            errors.extend(plan_errors)
            errors.append("finalization gate: task plan invalid [FINAL_PLAN_INVALID]")
        frontmatter, _ = project_files.parse_frontmatter(
            plan_path.read_text(encoding="utf-8")
        )
        if frontmatter is None:
            # validate_task_plan already reported PLAN_NO_FRONTMATTER; the
            # status is unknowable, so do not guess at it here.
            pass
        elif frontmatter.get("status") not in FINALIZATION_PLAN_STATUSES:
            errors.append(
                f"finalization gate: TASK_PLAN.md status is "
                f"{frontmatter.get('status')!r}, expected 'codex_approved' or "
                "'committed' [FINAL_PLAN_STATUS]"
            )

    if is_git_repo:
        candidates = set(git_checks.changed_files(repo_root))
        candidates.update(git_checks.staged_files(repo_root))
        candidates.update(git_checks.untracked_files(repo_root))
        for finding in security.blocking_findings(security.scan_files(repo_root, candidates)):
            errors.append(f"finalization gate: {finding.render()} [FINAL_SECRET]")
    return errors
