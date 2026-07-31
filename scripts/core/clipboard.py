"""Host-clipboard access for the Arabic testing-task hand-off.

The plugin is used from two different machines and the correct clipboard is
a different one on each:

* **WSL on a Windows host** — the useful clipboard is the *Windows* one, so
  the text has to cross the interop boundary and reach applications running
  outside WSL. ``powershell.exe`` + ``Set-Clipboard`` is the only mechanism
  used here; a Linux clipboard tool that happens to be installed inside the
  distribution would fill a clipboard nobody pastes from.
* **Native Ubuntu desktop** — the clipboard of the current display session:
  ``wl-copy`` under Wayland, otherwise ``xclip`` or ``xsel`` under X11.
  ``powershell.exe`` is never invoked here.

Detection happens on every call from runtime signals only; there is no
setting to configure and nothing is cached between invocations.

Safety properties this module guarantees:

* No ``shell=True`` anywhere — every command is an argument array.
* The Arabic text is passed as data (stdin, or Base64 for PowerShell) and
  is never interpolated into a script or a command line.
* Nothing is written to disk: no temporary files, no logging of clipboard
  contents. Only lengths and method names appear in results.
* The text copied is the *logical* Unicode string as generated. It is never
  reshaped or visually reordered.
* A session without a reachable clipboard produces a structured failure
  that names every method that was checked. Packages are never installed.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

# A clipboard helper either answers quickly or is broken.
COPY_TIMEOUT_SECONDS = 10

# --- WSL detection ---------------------------------------------------------

WSL_ENV_MARKERS = ("WSL_INTEROP", "WSL_DISTRO_NAME")
OSRELEASE_PATH = Path("/proc/sys/kernel/osrelease")
PROC_VERSION_PATH = Path("/proc/version")
WSL_KERNEL_MARKERS = ("microsoft", "wsl")

# --- Windows host clipboard ------------------------------------------------

POWERSHELL_EXE = "powershell.exe"
# Documented fallback for a distribution whose PATH omits the Windows
# interop directories. Resolved through the same ``which`` lookup, so an
# absolute path is only accepted when it is really an executable file.
POWERSHELL_FALLBACK = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"

# Guards the one place where a Python-built string becomes PowerShell
# source: only the Base64 alphabet may cross that boundary.
BASE64_ONLY = re.compile(r"\A[A-Za-z0-9+/]*={0,2}\Z")

# --- Native Linux desktop clipboards ---------------------------------------

# Ordered: Wayland first, then the two X11 tools. Each entry is
# (executable, session kind, required environment variable, arguments).
LINUX_METHODS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("wl-copy", "Wayland", "WAYLAND_DISPLAY", ()),
    ("xclip", "X11", "DISPLAY", ("-selection", "clipboard")),
    ("xsel", "X11", "DISPLAY", ("--clipboard", "--input")),
)

INSTALL_HINT_LINUX = (
    "Install one of them yourself — wl-clipboard for Wayland, xclip or xsel "
    "for X11. The plugin never installs packages."
)
INSTALL_HINT_WSL = (
    "powershell.exe must be reachable from this WSL distribution (Windows "
    "interop enabled, or the Windows System32 path present)."
)

NO_CLIPBOARD_LINUX = (
    "No desktop clipboard is available from this session (headless, SSH "
    "without clipboard forwarding, or no clipboard utility installed)."
)
NO_CLIPBOARD_WSL = (
    "The Windows host clipboard is not reachable from this WSL session."
)

# A tool was found and executed, but the copy itself did not succeed. That
# is a different problem from a missing tool and needs a different answer.
REFUSED_LINUX = "The clipboard utility ran but the copy did not succeed."
REFUSED_WSL = "Windows refused the clipboard operation."
HINT_REFUSED_LINUX = (
    "See the message above. A clipboard manager may be holding the "
    "selection, or the running tool does not match the session type "
    "(Wayland vs X11)."
)
HINT_REFUSED_WSL = (
    "The Windows clipboard is locked or unavailable to this session — "
    "typically another application holding it open, or a session with no "
    "interactive Windows desktop. Close clipboard-heavy applications and "
    "try again."
)


class ClipboardError(Exception):
    """Raised when a copy request itself is invalid (never for a missing tool)."""


@dataclass(frozen=True)
class Attempt:
    """One clipboard method and what happened to it."""

    method: str
    session: str
    status: str  # "used" | "unavailable" | "failed"
    detail: str

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "session": self.session,
            "status": self.status,
            "detail": self.detail,
        }

    def render(self) -> str:
        return f"{self.method} ({self.session}): {self.detail}"


@dataclass(frozen=True)
class CopyResult:
    """Outcome of a copy request. Never contains the copied text."""

    copied: bool
    platform: str  # "wsl" | "linux"
    method: str = ""
    target: str = ""
    characters: int = 0
    error: str = ""
    hint: str = ""
    attempts: tuple[Attempt, ...] = ()

    def to_dict(self) -> dict:
        return {
            "copied": self.copied,
            "platform": self.platform,
            "method": self.method,
            "target": self.target,
            "characters": self.characters,
            "error": self.error,
            "hint": self.hint,
            "checked": [a.to_dict() for a in self.attempts],
        }

    def render(self) -> str:
        if self.copied:
            return (
                f"Copied {self.characters} characters to the {self.target} "
                f"via {self.method}."
            )
        lines = [self.error, "Checked:"]
        lines += [f"  - {a.render()}" for a in self.attempts]
        if self.hint:
            lines.append(self.hint)
        return "\n".join(lines)


@dataclass(frozen=True)
class RunOutcome:
    ok: bool
    detail: str


@dataclass(frozen=True)
class _Candidate:
    method: str
    session: str
    target: str
    executable: Optional[str]
    unavailable: str
    kind: str  # "powershell" | "stdin"
    args: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# Platform detection
# --------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def is_wsl(env: Optional[Mapping[str, str]] = None) -> bool:
    """Return ``True`` when this process runs inside WSL.

    Environment markers are checked first because they are set by the WSL
    init itself; the kernel strings are the fallback for a shell that was
    started with a scrubbed environment.
    """
    env = os.environ if env is None else env
    if any(env.get(name) for name in WSL_ENV_MARKERS):
        return True
    for path in (OSRELEASE_PATH, PROC_VERSION_PATH):
        lowered = _read_text(path).lower()
        if any(marker in lowered for marker in WSL_KERNEL_MARKERS):
            return True
    return False


def _wsl_candidates(which: Callable[[str], Optional[str]]) -> list[_Candidate]:
    executable = which(POWERSHELL_EXE) or which(POWERSHELL_FALLBACK)
    return [
        _Candidate(
            method=POWERSHELL_EXE,
            session="Windows host",
            target="Windows host clipboard",
            executable=executable,
            unavailable=(
                ""
                if executable
                else f"not on PATH and not at {POWERSHELL_FALLBACK}"
            ),
            kind="powershell",
        )
    ]


def _linux_candidates(
    env: Mapping[str, str], which: Callable[[str], Optional[str]]
) -> list[_Candidate]:
    candidates = []
    for name, session, env_var, args in LINUX_METHODS:
        executable = None
        if not env.get(env_var):
            unavailable = f"{env_var} is not set"
        else:
            executable = which(name)
            unavailable = "" if executable else f"{env_var} is set but {name} is not installed"
        candidates.append(
            _Candidate(
                method=name,
                session=session,
                target="desktop clipboard",
                executable=executable,
                unavailable=unavailable,
                kind="stdin",
                args=args,
            )
        )
    return candidates


def candidates(
    env: Optional[Mapping[str, str]] = None,
    which: Callable[[str], Optional[str]] = shutil.which,
) -> list[_Candidate]:
    """Return the ordered clipboard methods for the detected platform."""
    env = os.environ if env is None else env
    if is_wsl(env):
        return _wsl_candidates(which)
    return _linux_candidates(env, which)


# --------------------------------------------------------------------------
# Command construction
# --------------------------------------------------------------------------

def powershell_script(text: str) -> str:
    """Build the ``Set-Clipboard`` script for *text*.

    The text crosses into PowerShell as Base64 only: it is encoded here, and
    PowerShell decodes it back to UTF-8 at runtime. No generated content —
    Arabic or otherwise — is ever part of the script source, so no quoting,
    escaping, or code-page conversion can corrupt or reinterpret it.
    """
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    if not BASE64_ONLY.match(payload):  # pragma: no cover - defensive
        raise ClipboardError("refusing to build a PowerShell command from non-Base64 data")
    return (
        "$ErrorActionPreference = 'Stop'; "
        "Set-Clipboard -Value ([Text.Encoding]::UTF8.GetString("
        f"[Convert]::FromBase64String('{payload}')))"
    )


def _command(candidate: _Candidate, text: str) -> tuple[list[str], Optional[bytes], bool]:
    """Return ``(argv, stdin_bytes, capture_stderr)`` for *candidate*."""
    if candidate.kind == "powershell":
        argv = [
            candidate.executable,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            powershell_script(text),
        ]
        return argv, None, True
    # wl-copy / xclip / xsel all read the text from stdin as UTF-8 bytes.
    # Their output is discarded: these tools fork a process that keeps the
    # selection alive and holds inherited pipes open, which would deadlock a
    # captured stdout.
    return [candidate.executable, *candidate.args], text.encode("utf-8"), False


def _run(argv: Sequence[str], stdin_bytes: Optional[bytes], capture_stderr: bool) -> RunOutcome:
    try:
        result = subprocess.run(
            list(argv),
            input=b"" if stdin_bytes is None else stdin_bytes,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture_stderr else subprocess.DEVNULL,
            timeout=COPY_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return RunOutcome(False, "executable disappeared before it could be run")
    except subprocess.TimeoutExpired:
        return RunOutcome(False, f"timed out after {COPY_TIMEOUT_SECONDS}s")
    except OSError as exc:
        return RunOutcome(False, f"could not be started: {exc.strerror or exc}")
    if result.returncode != 0:
        stderr = _first_line((result.stderr or b"").decode("utf-8", "replace"))
        detail = f"exited with status {result.returncode}"
        return RunOutcome(False, f"{detail}: {stderr}" if stderr else detail)
    return RunOutcome(True, "copied")


def _first_line(stderr: str, limit: int = 200) -> str:
    """Return the first, capped line of *stderr*.

    Only the leading diagnostic is kept. A PowerShell error report echoes
    the failing command on its later lines, which would put the Base64 of
    the copied text into the plugin's own output; a copy helper must not
    leak what it was asked to copy, not even encoded.
    """
    first = next((line.strip() for line in stderr.splitlines() if line.strip()), "")
    return first[:limit].rstrip() + "…" if len(first) > limit else first


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def copy(
    text: str,
    env: Optional[Mapping[str, str]] = None,
    which: Callable[[str], Optional[str]] = shutil.which,
    run: Callable[[Sequence[str], Optional[bytes], bool], RunOutcome] = _run,
) -> CopyResult:
    """Copy *text* to the clipboard of the detected environment.

    ``env``, ``which`` and ``run`` are injection points for tests; production
    callers pass nothing and get real detection.

    Returns a :class:`CopyResult`. A missing clipboard is a normal, reported
    outcome — not an exception — and ``copied`` is then ``False``. Callers
    must treat that as a failed hand-off: nothing has reached any clipboard.
    """
    env = os.environ if env is None else env
    platform = "wsl" if is_wsl(env) else "linux"

    payload = text.rstrip("\n")
    if not payload.strip():
        raise ClipboardError("refusing to copy empty text")

    attempts: list[Attempt] = []
    for candidate in candidates(env, which):
        if candidate.unavailable:
            attempts.append(
                Attempt(candidate.method, candidate.session, "unavailable", candidate.unavailable)
            )
            continue
        argv, stdin_bytes, capture_stderr = _command(candidate, payload)
        outcome = run(argv, stdin_bytes, capture_stderr)
        if outcome.ok:
            attempts.append(Attempt(candidate.method, candidate.session, "used", "copied"))
            return CopyResult(
                copied=True,
                platform=platform,
                method=candidate.method,
                target=candidate.target,
                characters=len(payload),
                attempts=tuple(attempts),
            )
        attempts.append(Attempt(candidate.method, candidate.session, "failed", outcome.detail))

    error, hint = _failure_summary(platform, attempts)
    return CopyResult(
        copied=False,
        platform=platform,
        error=error,
        hint=hint,
        attempts=tuple(attempts),
    )


def _failure_summary(platform: str, attempts: Sequence[Attempt]) -> tuple[str, str]:
    """Distinguish "no clipboard tool here" from "the copy was refused"."""
    executed = any(attempt.status == "failed" for attempt in attempts)
    if platform == "wsl":
        return (REFUSED_WSL, HINT_REFUSED_WSL) if executed else (NO_CLIPBOARD_WSL, INSTALL_HINT_WSL)
    return (
        (REFUSED_LINUX, HINT_REFUSED_LINUX)
        if executed
        else (NO_CLIPBOARD_LINUX, INSTALL_HINT_LINUX)
    )
