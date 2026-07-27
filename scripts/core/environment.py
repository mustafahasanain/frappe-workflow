"""Bench, application, Site, and Git environment detection.

All detection is read-only. Nothing in this module mutates the repository,
the bench, or any Site. Site→app installation status requires running a
``bench`` command; that call is isolated in :func:`run_bench_list_apps` so
tests can replace it.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# Entries under sites/ that are never Sites.
NON_SITE_ENTRIES = {
    "assets",
    "common_site_config.json",
    "apps.txt",
    "apps.json",
    ".build",
    "currentsite.txt",
}


class DetectionError(Exception):
    """Raised when the environment cannot be detected safely."""


@dataclass
class Environment:
    bench_path: Path
    app_name: str
    app_path: Path
    git_root: Path
    sites: list = field(default_factory=list)  # list[SiteInfo]

    def to_dict(self) -> dict:
        return {
            "bench_path": str(self.bench_path),
            "app_name": self.app_name,
            "app_path": str(self.app_path),
            "git_root": str(self.git_root),
            "sites": [s.to_dict() for s in self.sites],
        }


@dataclass
class SiteInfo:
    name: str
    app_installed: Optional[bool]  # None = unknown (bench not queried)

    def to_dict(self) -> dict:
        return {"name": self.name, "app_installed": self.app_installed}


def find_bench(start: Path) -> Path:
    """Walk upward from *start* until a directory looks like a bench.

    A bench directory contains ``apps/``, ``sites/`` and ``sites/apps.txt``.
    Stops at the filesystem root. Raises :class:`DetectionError` when no
    bench is found.
    """
    current = Path(start).resolve()
    while True:
        if (
            (current / "apps").is_dir()
            and (current / "sites").is_dir()
            and (current / "sites" / "apps.txt").is_file()
        ):
            return current
        if current.parent == current:
            raise DetectionError(
                "No Frappe bench found. Walked up from "
                f"'{start}' to the filesystem root without finding a directory "
                "containing apps/, sites/ and sites/apps.txt."
            )
        current = current.parent


def read_apps_txt(bench_path: Path) -> list[str]:
    """Return the app names listed in ``sites/apps.txt`` (blank lines ignored)."""
    apps_txt = bench_path / "sites" / "apps.txt"
    try:
        text = apps_txt.read_text(encoding="utf-8")
    except OSError as exc:
        raise DetectionError(f"Cannot read {apps_txt}: {exc}") from exc
    return [line.strip() for line in text.splitlines() if line.strip()]


def detect_app(start: Path, bench_path: Optional[Path] = None) -> Environment:
    """Detect the current application from *start* (cwd or a subdirectory).

    Rules (spec §11.2): resolve the real path, require it to be inside
    ``<bench>/apps/``, take the first path component after ``apps/``,
    confirm the directory exists, is listed in ``sites/apps.txt``, and is a
    Git repository.
    """
    start = Path(start).resolve()
    bench = bench_path or find_bench(start)
    apps_dir = (bench / "apps").resolve()

    try:
        relative = start.relative_to(apps_dir)
    except ValueError:
        installed = read_apps_txt(bench)
        raise DetectionError(
            "Current directory is not inside an application. "
            f"Bench: {bench}. Installed applications: "
            f"{', '.join(installed) if installed else '(none)'}. "
            "Run from inside <bench>/apps/<app_name> or select an application."
        )

    if not relative.parts:
        raise DetectionError(
            f"Current directory is the apps/ directory itself ({apps_dir}); "
            "an application cannot be inferred. Change into a specific app."
        )

    app_name = relative.parts[0]
    app_path = apps_dir / app_name
    if not app_path.is_dir():
        raise DetectionError(f"Application directory does not exist: {app_path}")

    installed = read_apps_txt(bench)
    if app_name not in installed:
        raise DetectionError(
            f"Application '{app_name}' is not listed in sites/apps.txt "
            f"(listed: {', '.join(installed) if installed else '(none)'})."
        )

    git_root = _find_git_root(app_path)
    if git_root is None:
        raise DetectionError(
            f"Application '{app_name}' at {app_path} is not a Git repository."
        )

    return Environment(
        bench_path=bench,
        app_name=app_name,
        app_path=app_path,
        git_root=git_root,
    )


def _find_git_root(path: Path) -> Optional[Path]:
    current = path.resolve()
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent


def list_site_candidates(bench_path: Path) -> list[str]:
    """Return directory names under sites/ that look like Sites.

    A Site directory contains a ``site_config.json`` file. Known non-Site
    entries are excluded explicitly as well.
    """
    sites_dir = bench_path / "sites"
    candidates = []
    for entry in sorted(sites_dir.iterdir()):
        if entry.name in NON_SITE_ENTRIES:
            continue
        if not entry.is_dir():
            continue
        if (entry / "site_config.json").is_file():
            candidates.append(entry.name)
    return candidates


def run_bench_list_apps(bench_path: Path, site: str) -> Optional[list[str]]:
    """Run ``bench --site <site> list-apps`` and return the app list.

    Returns ``None`` when the bench executable is unavailable or the command
    fails; callers treat that as "installation status unknown". Isolated
    here so unit tests can substitute a fake.
    """
    bench_bin = shutil.which("bench")
    if bench_bin is None:
        return None
    try:
        result = subprocess.run(
            [bench_bin, "--site", site, "list-apps"],
            cwd=str(bench_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    apps = []
    for line in result.stdout.splitlines():
        # `bench list-apps` may print "app_name  <version> <branch>".
        token = line.strip().split()[0] if line.strip() else ""
        if token:
            apps.append(token)
    return apps


def detect_sites(
    bench_path: Path,
    app_name: str,
    list_apps: Callable[[Path, str], Optional[list]] = run_bench_list_apps,
) -> list[SiteInfo]:
    """Determine which Sites have *app_name* installed.

    ``app_installed`` is ``True``/``False`` when the per-site app list could
    be read, and ``None`` when it could not (no bench executable, command
    failure). Never creates a Site and never installs an app.
    """
    sites = []
    for name in list_site_candidates(bench_path):
        apps = list_apps(bench_path, name)
        installed = None if apps is None else (app_name in apps)
        sites.append(SiteInfo(name=name, app_installed=installed))
    return sites


def detect(start: Path, list_apps: Callable = run_bench_list_apps) -> Environment:
    """Full detection: bench, app, git root, and candidate Sites."""
    env = detect_app(start)
    env.sites = detect_sites(env.bench_path, env.app_name, list_apps=list_apps)
    return env
