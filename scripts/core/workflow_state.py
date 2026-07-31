"""Atomic, validated workflow state stored in docs/ai-context/.

The state file is the primary logical workflow state and is tracked by Git so
an active task can continue across multiple development machines.

Git also verifies that the recorded state is still truthful. All writes are
atomic using a temporary file in the same directory, fsync, and os.replace.

The advisory lock remains machine-local under ``.claude/`` and is never part
of the shared workflow state.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import project_files

SCHEMA_VERSION = 1

STATE_RELATIVE_PATH = Path(project_files.WORKFLOW_STATE)
LOCK_RELATIVE_PATH = Path(project_files.WORKFLOW_LOCK)

STAGES = (
    "planning",
    "implementation",
    "codex_review",
    "review_fixes",
    "ready_for_commit",
    "committed",
    "deployment_skipped",
    "deployed",
    "completed",
)

ALLOWED_TRANSITIONS = {
    "planning": {"implementation"},
    "implementation": {"codex_review", "implementation"},
    "codex_review": {"review_fixes", "ready_for_commit"},
    "review_fixes": {"codex_review", "review_fixes"},
    "ready_for_commit": {"review_fixes", "committed"},
    "committed": {"deployed", "deployment_skipped"},
    "deployed": {"completed"},
    "deployment_skipped": {"completed"},
    "completed": set(),
}

TASK_PLAN_STATUSES = (
    "not_created",
    "planned",
    "approved",
    "in_progress",
    "implementation_complete",
    "codex_approved",
    "committed",
    "completed",
    "blocked",
)


class StateError(Exception):
    """Raised for invalid, unreadable, or unwritable state."""


class TransitionError(StateError):
    """Raised when a stage transition is not allowed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_state() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": None,
        "task_title": None,
        "task_type": None,
        "bench_path": None,
        "app_name": None,
        "app_path": None,
        "target_site": None,
        "branch": None,
        "base_commit": None,
        "current_stage": "planning",
        "task_plan_status": "not_created",
        "implementation_status": {
            "status": "pending",
            "total_steps": 0,
            "completed_steps": 0,
            "blocked_steps": 0,
        },
        "codex_review": {
            "status": "pending",
            "round": 0,
            "prompt_path": None,
            "result_path": None,
            "implementation_fingerprint": None,
            "approved_at": None,
        },
        "commit": {
            "status": "not_created",
            "hash": None,
            "subject": None,
        },
        "deployment": {
            "required": None,
            "status": "pending",
            "skip_reason": None,
            "server_commit": None,
            "deployed_at": None,
        },
        "testing_task": {
            "status": "pending",
            "path": None,
            "generated_at": None,
        },
        "blockers": [],
        "transition_history": [],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


REQUIRED_KEYS = (
    "schema_version",
    "current_stage",
    "task_plan_status",
    "implementation_status",
    "codex_review",
    "commit",
    "deployment",
    "testing_task",
    "blockers",
)


def validate_state(state: dict) -> list[str]:
    """Return validation error strings, or an empty list when valid."""
    errors = []

    if not isinstance(state, dict):
        return ["state: not a JSON object [STATE_NOT_OBJECT]"]

    for key in REQUIRED_KEYS:
        if key not in state:
            errors.append(f"state: missing required key '{key}' [STATE_MISSING_KEY]")

    if errors:
        return errors

    if state["schema_version"] != SCHEMA_VERSION:
        errors.append(
            f"state: unsupported schema_version {state['schema_version']!r}, "
            f"expected {SCHEMA_VERSION} [STATE_SCHEMA_VERSION]"
        )

    if state["current_stage"] not in STAGES:
        errors.append(
            f"state: invalid current_stage "
            f"{state['current_stage']!r} [STATE_INVALID_STAGE]"
        )

    if state["task_plan_status"] not in TASK_PLAN_STATUSES:
        errors.append(
            f"state: invalid task_plan_status {state['task_plan_status']!r} "
            "[STATE_INVALID_PLAN_STATUS]"
        )

    if not isinstance(state["blockers"], list):
        errors.append("state: blockers must be a list [STATE_BLOCKERS_TYPE]")

    for section in (
        "implementation_status",
        "codex_review",
        "commit",
        "deployment",
        "testing_task",
    ):
        if not isinstance(state[section], dict):
            errors.append(f"state: {section} must be an object [STATE_SECTION_TYPE]")

    stage = state["current_stage"]

    if stage in ("committed", "deployed", "deployment_skipped", "completed"):
        if state["commit"].get("status") != "created":
            errors.append(
                f"state: stage '{stage}' requires commit.status 'created' "
                "[STATE_STAGE_COMMIT_MISMATCH]"
            )

    if stage == "deployed" and state["deployment"].get("status") != "deployed":
        errors.append(
            "state: stage 'deployed' requires deployment.status 'deployed' "
            "[STATE_STAGE_DEPLOY_MISMATCH]"
        )

    if (
        stage == "deployment_skipped"
        and state["deployment"].get("status") != "skipped"
    ):
        errors.append(
            "state: stage 'deployment_skipped' requires deployment.status "
            "'skipped' [STATE_STAGE_SKIP_MISMATCH]"
        )

    return errors


def state_path(repo_root: Path) -> Path:
    return Path(repo_root) / STATE_RELATIVE_PATH


def lock_path(repo_root: Path) -> Path:
    return Path(repo_root) / LOCK_RELATIVE_PATH


def load_state(repo_root: Path) -> dict:
    """Load and validate the state file. Raise StateError on any problem."""
    path = state_path(repo_root)

    if not path.is_file():
        raise StateError(f"No workflow state found at {path} [STATE_MISSING]")

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StateError(f"Cannot read {path}: {exc} [STATE_UNREADABLE]") from exc

    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateError(
            f"Invalid JSON in {path}: {exc} [STATE_INVALID_JSON]"
        ) from exc

    errors = validate_state(state)

    if errors:
        raise StateError("; ".join(errors))

    return state


def save_state(repo_root: Path, state: dict) -> Path:
    """Validate and atomically write the shared workflow state file.

    Content is written to a temporary file in the same directory, fsynced,
    and renamed over the target. The lock used during this operation remains
    local under ``.claude/``.
    """
    errors = validate_state(state)

    if errors:
        raise StateError("Refusing to save invalid state: " + "; ".join(errors))

    state = copy.deepcopy(state)
    state["updated_at"] = utc_now()

    path = state_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    local_lock_path = lock_path(repo_root)
    local_lock_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(state, indent=2, ensure_ascii=False) + "\n"

    lock_handle = _acquire_lock(local_lock_path)

    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=".task-workflow.",
            suffix=".tmp",
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    finally:
        _release_lock(lock_handle)

    return path


def _acquire_lock(lock_file: Path):
    try:
        import fcntl
    except ImportError:
        return None

    handle = open(lock_file, "w", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _release_lock(handle) -> None:
    if handle is None:
        return

    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def init_state(repo_root: Path, overwrite: bool = False) -> dict:
    """Create a fresh state file.

    Refuse to overwrite an existing state unless ``overwrite`` is enabled by
    the controlled reset operation.
    """
    path = state_path(repo_root)

    if path.exists() and not overwrite:
        raise StateError(
            f"Workflow state already exists at {path}; refusing to overwrite. "
            "Use the reset action for a controlled reset. [STATE_EXISTS]"
        )

    state = default_state()
    save_state(repo_root, state)
    return state


def transition(
    repo_root: Path,
    new_stage: str,
    reason: str = "",
    detail: Optional[dict] = None,
) -> dict:
    """Move the persisted state when the requested transition is allowed."""
    if new_stage not in STAGES:
        raise TransitionError(
            f"Unknown stage '{new_stage}' [TRANSITION_UNKNOWN_STAGE]"
        )

    state = load_state(repo_root)
    current = state["current_stage"]

    if new_stage not in ALLOWED_TRANSITIONS.get(current, set()):
        raise TransitionError(
            f"Transition '{current}' -> '{new_stage}' is not allowed "
            "[TRANSITION_REJECTED]"
        )

    record = {
        "from": current,
        "to": new_stage,
        "at": utc_now(),
        "reason": reason or "",
    }

    if detail:
        record.update(detail)

    state["current_stage"] = new_stage
    state.setdefault("transition_history", []).append(record)
    save_state(repo_root, state)
    return state


IMMUTABLE_PATHS = {
    "schema_version": "the schema version is fixed by the plugin",
    "current_stage": (
        "use 'state transition <stage>' so the transition table is enforced"
    ),
    "blockers": "use 'state blocker add' / 'state blocker clear'",
    "transition_history": (
        "transition history is append-only and managed by the engine"
    ),
}


def set_field(repo_root: Path, dotted_path: str, value) -> dict:
    """Set one existing state field atomically.

    Only schema paths that already exist may be changed. Immutable fields
    require their dedicated controlled operations.
    """
    parts = dotted_path.split(".")

    if parts[0] in IMMUTABLE_PATHS:
        raise StateError(
            f"'{dotted_path}' cannot be set directly: "
            f"{IMMUTABLE_PATHS[parts[0]]} [STATE_IMMUTABLE_FIELD]"
        )

    state = load_state(repo_root)
    cursor = state

    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            raise StateError(
                f"Unknown state path '{dotted_path}' [STATE_UNKNOWN_PATH]"
            )

        cursor = cursor[part]

    leaf = parts[-1]

    if not isinstance(cursor, dict) or leaf not in cursor:
        raise StateError(
            f"Unknown state path '{dotted_path}' [STATE_UNKNOWN_PATH]"
        )

    cursor[leaf] = value
    save_state(repo_root, state)
    return state


def add_blocker(repo_root: Path, message: str) -> dict:
    state = load_state(repo_root)
    state["blockers"].append(
        {
            "message": message,
            "recorded_at": utc_now(),
        }
    )
    save_state(repo_root, state)
    return state


def clear_blockers(repo_root: Path) -> dict:
    state = load_state(repo_root)
    state["blockers"] = []
    save_state(repo_root, state)
    return state
