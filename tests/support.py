"""Shared helpers for the frappe-workflow test suite.

Importable as ``support`` because ``unittest discover -s tests`` puts the
tests directory on sys.path. Provides plugin-path setup, temp-bench
construction from the sample fixture, and no-network git repo helpers.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
FIXTURES_DIR = PLUGIN_ROOT / "tests" / "fixtures"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Test Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"fixture git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout


def make_temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="fw-test-"))


def make_bench(tmp: Path, app_git: bool = True) -> Path:
    """Copy the sample bench fixture into *tmp* and optionally git-init the app."""
    bench = tmp / "frappe-bench"
    shutil.copytree(FIXTURES_DIR / "sample-bench", bench)
    if app_git:
        app = bench / "apps" / "general_trading"
        init_repo(app, initial_commit=True)
    return bench


def init_repo(path: Path, initial_commit: bool = False) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    run_git(path, "init", "-q", "-b", "main")
    if initial_commit:
        (path / ".fixture-marker").write_text("fixture\n", encoding="utf-8")
        run_git(path, "add", "-A")
        run_git(path, "commit", "-q", "-m", "fixture: initial commit")
    return path


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def write_repo_file(repo: Path, relative: str, text: str) -> Path:
    """Write *text* to ``repo/relative``, creating parent directories.

    Managed files now live under ``docs/ai-context/``, so every test that
    places one has to create the directory first. Doing it here keeps the
    tests referring to the centralized ``project_files`` constants instead
    of repeating path literals.
    """
    path = Path(repo) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_fixture_file(repo: Path, relative: str, fixture_name: str) -> Path:
    """Copy a named fixture into ``repo/relative``."""
    return write_repo_file(repo, relative, read_fixture(fixture_name))


def synthetic_secret(*parts: str) -> str:
    """Assemble a credential-shaped test value at runtime.

    Tests need realistic-looking values to prove the security scanner
    blocks them, but no credential-shaped literal should exist anywhere in
    this repository — the plugin's own scanner runs over it, and a literal
    here would be indistinguishable from a real leak. Building the value
    from fragments satisfies both requirements.
    """
    return "".join(parts)
