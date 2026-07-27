"""Conservative changed-file secret scanning with redacted findings.

The scanner never prints a full secret: matched values are redacted to the
first three and last three characters. A finding blocks review, commit, and
deployment until resolved or explicitly confirmed as a safe test fixture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# Obviously-fake markers used by test fixtures; matches containing one of
# these are reported at "info" level instead of blocking.
FAKE_MARKERS = ("example", "dummy", "fake", "sample", "your-", "changeme", "xxxx", "test-token")

# An interpolation placeholder is never a secret: it is the *shape* of a
# value, not a value. Covers Python format/f-strings, Jinja, shell/env
# expansion, printf-style, and angle-bracket templates — all of which appear
# in legitimate Frappe configuration and template files.
PLACEHOLDER_VALUE_RE = re.compile(
    r"""^(?:
          \{\{[^{}]*\}\}                 # {{ name }}
        | \{[^{}]*\}                     # {NAME}
        | \$\{[^{}]*\}                   # ${NAME}
        | \$[A-Za-z_][A-Za-z0-9_]*       # $NAME
        | %\([^()]*\)[sdifr]             # %(name)s
        | %[sdifr]                       # %s
        | <[^<>]*>                       # <placeholder>
    )$""",
    re.VERBOSE,
)

PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("telegram bot token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{33,45}\b")),
    ("aws access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    (
        "authorization header",
        re.compile(r"Authorization['\"]?\s*[:=]\s*['\"]?(?:Bearer|Basic)\s+[A-Za-z0-9._+/=-]{12,}", re.I),
    ),
    (
        "token assignment",
        re.compile(
            r"""(?ix)
            \b(api[_-]?key|api[_-]?token|access[_-]?token|auth[_-]?token|
               secret[_-]?key|client[_-]?secret|bot[_-]?token|private[_-]?key)
            \b\s*[:=]\s*["']([^"'\s]{12,})["']
            """
        ),
    ),
    (
        "password assignment",
        re.compile(
            r"""(?ix)
            \b(password|passwd|db[_-]?password|mysql[_-]?password|admin[_-]?password)
            \b\s*[:=]\s*["']([^"'\s]{6,})["']
            """
        ),
    ),
    (
        "database url with credentials",
        re.compile(r"\b(?:mysql|postgres(?:ql)?|mariadb|mongodb)://[^\s:@/]+:[^\s@/]+@", re.I),
    ),
)

# Files that must never be staged or bundled regardless of content.
FORBIDDEN_PATHS = (
    re.compile(r"(^|/)\.env(\..+)?$"),
    re.compile(r"(^|/)\.claude/deployment\.local\.json$"),
    re.compile(r"(^|/)id_(rsa|ed25519|ecdsa|dsa)(\.pub)?$"),
)


@dataclass
class Finding:
    path: str
    line: int
    pattern: str
    redacted: str
    blocking: bool

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "line": self.line,
            "pattern": self.pattern,
            "value": self.redacted,
            "blocking": self.blocking,
        }

    def render(self) -> str:
        level = "Possible secret detected" if self.blocking else "Non-blocking match"
        return (
            f"{level} in {self.path}:{self.line}\n"
            f"Pattern: {self.pattern}\n"
            f"Value: {self.redacted}"
        )


def redact(value: str) -> str:
    value = value.strip()
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}...{value[-3:]}"


def _looks_fake(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in FAKE_MARKERS)


def _is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_VALUE_RE.match(value.strip()))


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for name, pattern in PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            # Prefer the captured secret group when the pattern has one.
            value = match.group(match.lastindex) if match.lastindex else match.group(0)
            if _is_placeholder(value):
                continue  # a template placeholder, not a secret
            findings.append(
                Finding(
                    path=path,
                    line=lineno,
                    pattern=name,
                    redacted=redact(value),
                    blocking=not _looks_fake(line),
                )
            )
            break  # one finding per line is enough
    return findings


def scan_path_name(path: str) -> Optional[Finding]:
    """Flag forbidden filenames (private keys, .env, local deploy config)."""
    for pattern in FORBIDDEN_PATHS:
        if pattern.search(path):
            return Finding(
                path=path,
                line=0,
                pattern="forbidden file",
                redacted="(file must not be committed)",
                blocking=True,
            )
    return None


def scan_files(repo_root: Path, relative_paths: Iterable[str]) -> list[Finding]:
    """Scan files under *repo_root*; unreadable/binary files are skipped."""
    findings: list[Finding] = []
    for rel in sorted(set(relative_paths)):
        name_finding = scan_path_name(rel)
        if name_finding:
            findings.append(name_finding)
        full = Path(repo_root) / rel
        if not full.is_file():
            continue
        try:
            text = full.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_text(rel, text))
    return findings


def blocking_findings(findings: Iterable[Finding]) -> list[Finding]:
    return [f for f in findings if f.blocking]
