"""Deployment configuration validation, preflight checks, and the Frappe
command matrix.

No function in this module opens an SSH connection by itself. Remote checks
are expressed as command argument arrays (``build_ssh_command``) or evaluated
from captured outputs, so unit tests never touch the network and the skill
layer decides when a command may actually run — only after explicit user
confirmation.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Optional

CONFIG_RELATIVE_PATH = Path(".claude") / "deployment.local.json"

REQUIRED_FIELDS = {
    "host": str,
    "ssh_user": str,
    "bench_path": str,
    "app_name": str,
    "target_site": str,
    "remote": str,
    "branch": str,
}
OPTIONAL_FIELDS = {"port": int, "identity_file": (str, type(None))}

SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._@-]+$")
SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
SAFE_SITE_RE = re.compile(r"^[A-Za-z0-9._-]+$")

SECRET_LIKE_KEYS = ("password", "passwd", "secret", "token", "key_data", "passphrase")


class DeploymentError(Exception):
    pass


def load_config(repo_root: Path) -> dict:
    path = Path(repo_root) / CONFIG_RELATIVE_PATH
    if not path.is_file():
        raise DeploymentError(
            f"Deployment configuration not found at {path}. Copy "
            "templates/state/deployment.local.json.example into "
            ".claude/deployment.local.json and edit it. [DEPLOY_NO_CONFIG]"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DeploymentError(f"Invalid JSON in {path}: {exc} [DEPLOY_BAD_JSON]") from exc
    if "demo_server" not in data or not isinstance(data["demo_server"], dict):
        raise DeploymentError(
            f"{path}: missing 'demo_server' object [DEPLOY_NO_SERVER]"
        )
    return data["demo_server"]


def validate_config(config: dict) -> list[str]:
    """Return validation errors for a demo_server config dict."""
    errors: list[str] = []
    for key in config:
        if any(marker in key.lower() for marker in SECRET_LIKE_KEYS):
            errors.append(
                f"config: field '{key}' looks like a stored credential; use SSH "
                "keys or ssh-agent instead [DEPLOY_STORED_SECRET]"
            )
    for field, expected in REQUIRED_FIELDS.items():
        value = config.get(field)
        if value is None or value == "":
            errors.append(f"config: missing required field '{field}' [DEPLOY_FIELD]")
        elif not isinstance(value, expected):
            errors.append(
                f"config: field '{field}' must be {expected.__name__} [DEPLOY_FIELD_TYPE]"
            )
    port = config.get("port", 22)
    if not isinstance(port, int) or isinstance(port, bool) or not (1 <= port <= 65535):
        errors.append(f"config: invalid port {port!r} (1-65535) [DEPLOY_PORT]")
    identity = config.get("identity_file")
    if identity is not None and not isinstance(identity, str):
        errors.append("config: identity_file must be a string or null [DEPLOY_IDENTITY]")

    if errors:
        return errors

    if not SAFE_NAME_RE.match(config["host"]):
        errors.append(f"config: unsafe host {config['host']!r} [DEPLOY_HOST]")
    if not SAFE_NAME_RE.match(config["ssh_user"]):
        errors.append(f"config: unsafe ssh_user {config['ssh_user']!r} [DEPLOY_USER]")
    if not SAFE_NAME_RE.match(config["remote"]):
        errors.append(f"config: unsafe remote name {config['remote']!r} [DEPLOY_REMOTE]")
    if not SAFE_BRANCH_RE.match(config["branch"]) or config["branch"].startswith("-"):
        errors.append(f"config: unsafe branch {config['branch']!r} [DEPLOY_BRANCH]")
    if not SAFE_SITE_RE.match(config["target_site"]):
        errors.append(f"config: unsafe target_site {config['target_site']!r} [DEPLOY_SITE]")
    if not SAFE_NAME_RE.match(config["app_name"].replace("_", "")):
        # app names are python package names; underscore already allowed above
        pass
    bench_path = config["bench_path"]
    if not bench_path.startswith("/") or ".." in Path(bench_path).parts:
        errors.append(
            f"config: bench_path must be absolute without '..' ({bench_path!r}) "
            "[DEPLOY_PATH]"
        )
    return errors


def check_task_consistency(config: dict, state: dict) -> list[str]:
    """Cross-check deployment config against the active task state."""
    errors: list[str] = []
    if state.get("app_name") and config.get("app_name") != state["app_name"]:
        errors.append(
            f"config app_name {config.get('app_name')!r} != task app "
            f"{state['app_name']!r} [DEPLOY_APP_MISMATCH]"
        )
    if state.get("branch") and config.get("branch") != state["branch"]:
        errors.append(
            f"config branch {config.get('branch')!r} != task branch "
            f"{state['branch']!r} [DEPLOY_BRANCH_MISMATCH]"
        )
    if state.get("commit", {}).get("status") != "created":
        errors.append("active task has no verified commit [DEPLOY_NO_COMMIT]")
    return errors


def build_ssh_command(config: dict, remote_args: list[str]) -> list[str]:
    """Build a safe SSH argument array for one remote command.

    *remote_args* is an argv list; it is shell-quoted for the remote side.
    Host-key checking is left at the SSH default (never disabled).
    """
    errors = validate_config(config)
    if errors:
        raise DeploymentError("; ".join(errors))
    command = ["ssh", "-p", str(config.get("port", 22))]
    if config.get("identity_file"):
        command += ["-i", str(config["identity_file"])]
    command += ["--", f"{config['ssh_user']}@{config['host']}"]
    command.append(" ".join(shlex.quote(arg) for arg in remote_args))
    return command


def remote_git_commands(config: dict) -> dict[str, list[str]]:
    """The read-only remote preflight command set (spec §25), as argv lists
    for the *remote* side. Nothing here mutates the server."""
    app_path = str(Path(config["bench_path"]) / "apps" / config["app_name"])
    return {
        "fetch": ["git", "-C", app_path, "fetch", config["remote"]],
        "status": ["git", "-C", app_path, "status", "--porcelain"],
        "branch": ["git", "-C", app_path, "branch", "--show-current"],
        "head": ["git", "-C", app_path, "rev-parse", "HEAD"],
        "remote_head": [
            "git", "-C", app_path, "rev-parse",
            f"{config['remote']}/{config['branch']}",
        ],
        "ff_possible": [
            "git", "-C", app_path, "merge-base", "--is-ancestor",
            "HEAD", f"{config['remote']}/{config['branch']}",
        ],
        "pull": [
            "git", "-C", app_path, "pull", "--ff-only",
            config["remote"], config["branch"],
        ],
    }


def evaluate_remote_preflight(
    config: dict,
    expected_commit: str,
    status_output: str,
    branch_output: str,
    remote_head_output: str,
    ff_exit_code: int,
) -> list[str]:
    """Judge remote preflight from captured command outputs (testable offline)."""
    errors: list[str] = []
    if status_output.strip():
        errors.append(
            "server working tree has local changes; refusing to deploy "
            "[PREFLIGHT_DIRTY]"
        )
    actual_branch = branch_output.strip()
    if actual_branch != config["branch"]:
        errors.append(
            f"server branch {actual_branch!r} != expected {config['branch']!r} "
            "[PREFLIGHT_BRANCH]"
        )
    remote_head = remote_head_output.strip()
    if not remote_head:
        errors.append("remote commit could not be resolved [PREFLIGHT_NO_REMOTE_HEAD]")
    elif expected_commit and not remote_head.startswith(expected_commit) and not expected_commit.startswith(remote_head):
        errors.append(
            f"remote head {remote_head[:12]} does not match expected task commit "
            f"{expected_commit[:12]} [PREFLIGHT_COMMIT_MISMATCH]"
        )
    if ff_exit_code != 0:
        errors.append(
            "fast-forward is not possible (history diverged) [PREFLIGHT_NO_FF]"
        )
    return errors


# --------------------------------------------------------------------------
# Frappe command matrix (spec §26)
# --------------------------------------------------------------------------

MIGRATE_PATTERNS = (
    re.compile(r"/doctype/[^/]+/[^/]+\.json$"),
    re.compile(r"(^|/)patches\.txt$"),
    re.compile(r"(^|/)patches/"),
    re.compile(r"(^|/)fixtures/"),
    re.compile(r"(^|/)custom/"),
    re.compile(r"(^|/)hooks\.py$"),
)
BUILD_PATTERNS = (
    re.compile(r"(^|/)public/js/"),
    re.compile(r"(^|/)public/css/"),
    re.compile(r"(^|/)public/scss/"),
    re.compile(r"\.(vue|jsx|tsx)$"),
    re.compile(r"(^|/)package\.json$"),
    re.compile(r"(^|/)webpack\.config\.js$"),
    re.compile(r"(^|/)build\.json$"),
)
RESTART_PATTERNS = (re.compile(r"\.py$"),)
SCHEDULER_HINT_PATTERNS = (
    re.compile(r"(^|/)tasks\.py$"),
    re.compile(r"scheduler"),
)


def required_frappe_commands(changed_paths: list[str], app_name: str, site: str) -> list[dict]:
    """Conservatively map changed files to the required bench commands.

    Returns ordered command descriptors: ``{"command": [...], "reason": str}``.
    Only commands justified by an actual changed file are included.
    """
    needs_migrate = False
    needs_build = False
    needs_restart = False
    scheduler_hint = False

    for path in changed_paths:
        if any(p.search(path) for p in MIGRATE_PATTERNS):
            needs_migrate = True
        if any(p.search(path) for p in BUILD_PATTERNS):
            needs_build = True
        if any(p.search(path) for p in RESTART_PATTERNS):
            needs_restart = True
        if any(p.search(path) for p in SCHEDULER_HINT_PATTERNS):
            scheduler_hint = True

    commands: list[dict] = []
    if needs_migrate:
        commands.append(
            {
                "command": ["bench", "--site", site, "migrate"],
                "reason": "schema-affecting files changed (doctype JSON, patches, fixtures, or hooks.py)",
            }
        )
    if needs_build:
        commands.append(
            {
                "command": ["bench", "build", "--app", app_name],
                "reason": "frontend assets changed (public/js, public/css, or bundle sources)",
            }
        )
    if needs_restart:
        commands.append(
            {
                "command": ["bench", "restart"],
                "reason": "backend Python changed; workers and web processes must reload",
            }
        )
    if scheduler_hint and not needs_restart:
        commands.append(
            {
                "command": ["bench", "restart"],
                "reason": "scheduled job definitions changed; scheduler must reload",
            }
        )
    return commands


def verify_deployment(expected_commit: str, server_head: str) -> Optional[str]:
    """Return an error string when the deployed commit does not match."""
    server_head = server_head.strip()
    if not server_head:
        return "server HEAD could not be read [VERIFY_NO_HEAD]"
    if not (server_head.startswith(expected_commit) or expected_commit.startswith(server_head)):
        return (
            f"server HEAD {server_head[:12]} != expected commit "
            f"{expected_commit[:12]} [VERIFY_MISMATCH]"
        )
    return None
