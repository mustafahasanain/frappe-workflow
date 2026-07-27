"""Read-only Git inspection and the deterministic implementation fingerprint.

Every Git invocation uses subprocess argument arrays (never ``shell=True``)
and never mutates the repository.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Optional


class GitError(Exception):
    pass


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def _git_bytes(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
    )
    if result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.decode('utf-8', 'replace').strip()}"
        )
    return result.stdout


def is_git_repo(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def head_commit(repo: Path) -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None  # e.g. repository with no commits yet
    return result.stdout.strip()


def current_branch(repo: Path) -> str:
    return _git(repo, "branch", "--show-current").strip()


def status_porcelain(repo: Path) -> list[str]:
    return [line for line in _git(repo, "status", "--porcelain").splitlines() if line]


def changed_files(repo: Path) -> list[str]:
    """Tracked files with unstaged or staged modifications (unique, sorted)."""
    unstaged = _git(repo, "diff", "--name-only", "HEAD").splitlines() if head_commit(repo) else []
    return sorted({f for f in unstaged if f})


def staged_files(repo: Path) -> list[str]:
    if head_commit(repo) is None:
        out = _git(repo, "diff", "--cached", "--name-only")
    else:
        out = _git(repo, "diff", "--cached", "--name-only", "HEAD")
    return sorted({f for f in out.splitlines() if f})


def untracked_files(repo: Path) -> list[str]:
    out = _git(repo, "ls-files", "--others", "--exclude-standard")
    return sorted({f for f in out.splitlines() if f})


def remotes(repo: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in _git(repo, "remote", "-v").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] not in result:
            result[parts[0]] = parts[1]
    return result


def tracking_branch(repo: Path) -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def inspect(repo: Path) -> dict:
    """Full read-only snapshot used by `frappe-workflow git inspect`."""
    if not is_git_repo(repo):
        raise GitError(f"{repo} is not a Git repository")
    status = status_porcelain(repo)
    return {
        "branch": current_branch(repo),
        "head": head_commit(repo),
        "clean": not status,
        "status": status,
        "staged_files": staged_files(repo),
        "changed_files": changed_files(repo),
        "untracked_files": untracked_files(repo),
        "remotes": remotes(repo),
        "tracking_branch": tracking_branch(repo),
    }


def commit_files(repo: Path, commit: str) -> list[str]:
    """Files touched by *commit* (read-only)."""
    out = _git(repo, "show", "--name-only", "--pretty=format:", commit)
    return sorted({f for f in out.splitlines() if f})


# Documentation-only files edited during finalization. Excluded from the
# implementation fingerprint so post-approval finalization updates do not
# invalidate a valid approval (they cannot affect application behavior).
FINALIZATION_FILES = (
    "TASK_PLAN.md",
    "FEATURE_CHANGELOG.md",
    "PROJECT_CONTEXT.md",
)

# Workflow-internal files must never affect the fingerprint, even when the
# managed .gitignore block is not (yet) in place in the target repository.
FINGERPRINT_EXCLUDED_DIRS = (".claude",)


def implementation_fingerprint(
    repo: Path, untracked_paths: Optional[list[str]] = None
) -> str:
    """SHA-256 fingerprint of the current implementation state.

    Includes: ``git diff --binary HEAD``, the staged binary diff, and the
    sorted names + contents of relevant untracked (non-ignored) files.
    The categorized finalization files (:data:`FINALIZATION_FILES`) are
    excluded, so documentation-only finalization edits keep the fingerprint
    stable. Contains no timestamps, so it is stable while the working tree
    is unchanged and changes as soon as any included content changes.
    """
    hasher = hashlib.sha256()
    have_head = head_commit(repo) is not None
    excludes = [f":(exclude){name}" for name in FINALIZATION_FILES]
    excludes += [f":(exclude){name}/" for name in FINGERPRINT_EXCLUDED_DIRS]

    if have_head:
        hasher.update(b"--diff-head--\n")
        hasher.update(_git_bytes(repo, "diff", "--binary", "HEAD", "--", ".", *excludes))
        hasher.update(b"--diff-staged--\n")
        hasher.update(
            _git_bytes(repo, "diff", "--cached", "--binary", "HEAD", "--", ".", *excludes)
        )
    else:
        hasher.update(b"--no-head--\n")
        hasher.update(_git_bytes(repo, "diff", "--cached", "--binary", "--", ".", *excludes))

    if untracked_paths is None:
        untracked_paths = untracked_files(repo)
    untracked_paths = [
        p
        for p in untracked_paths
        if p not in FINALIZATION_FILES
        and not any(p.startswith(d + "/") for d in FINGERPRINT_EXCLUDED_DIRS)
    ]
    for rel in sorted(set(untracked_paths)):
        path = Path(repo) / rel
        hasher.update(b"--untracked--\n")
        hasher.update(rel.encode("utf-8") + b"\n")
        if path.is_file():
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def unrelated_staged_files(repo: Path, expected: list[str]) -> list[str]:
    """Staged files that are not in the expected task-related list."""
    expected_set = set(expected)
    return [f for f in staged_files(repo) if f not in expected_set]
