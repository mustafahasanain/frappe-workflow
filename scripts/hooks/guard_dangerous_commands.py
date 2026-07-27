#!/usr/bin/env python3
"""PreToolUse hook: block clearly destructive Bash commands.

Reads the Claude Code hook payload as JSON from stdin. When the Bash command
matches a destructive pattern the workflow never needs, the hook denies the
call with an explanation. Anything unexpected (malformed input, other tools)
is allowed through silently — the hook fails safe and never crashes the
session, and it never logs command content anywhere.
"""

from __future__ import annotations

import json
import re
import sys

# Each entry: (compiled pattern, human explanation). Patterns tolerate extra
# whitespace and common flag orderings. Matching is done on the raw command
# string; obvious documentation contexts (echo/comment lines) are skipped.
DANGEROUS_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (
        re.compile(r"\bgit\b[^|;&]*\breset\b[^|;&]*--hard\b"),
        "git reset --hard discards local work; this workflow never needs it.",
    ),
    (
        re.compile(r"\bgit\b[^|;&]*\bclean\b[^|;&]*-[a-zA-Z]*[fdxX]"),
        "git clean deletes untracked files; this workflow never needs it.",
    ),
    (
        re.compile(r"\bgit\b[^|;&]*\bpush\b[^|;&]*(--force(-with-lease)?\b|\s-f\b)"),
        "Force-pushing rewrites remote history; this workflow forbids it.",
    ),
    (
        re.compile(r"\bgit\b[^|;&]*\bcheckout\b\s+--\s+\.(?:\s|$)"),
        "git checkout -- . discards all working-tree changes.",
    ),
    (
        re.compile(r"\bgit\b[^|;&]*\brestore\b\s+\.(?:\s|$)"),
        "git restore . discards all working-tree changes.",
    ),
    (
        re.compile(r"\brm\b[^|;&]*-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(/|/\*)(\s|$)"),
        "rm -rf on the filesystem root is destructive.",
    ),
    (
        re.compile(r"\brm\b[^|;&]*-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s+(/|/\*)(\s|$)"),
        "rm -rf on the filesystem root is destructive.",
    ),
    (
        re.compile(r"\bbench\b[^|;&]*\bdrop-site\b"),
        "bench drop-site deletes a Site and its database.",
    ),
    (
        re.compile(r"\bbench\b[^|;&]*\breinstall\b"),
        "bench reinstall wipes the Site database.",
    ),
    (
        re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE),
        "DROP DATABASE destroys a database.",
    ),
)

# Lines that are clearly documentation/output rather than execution.
DOC_LINE_RE = re.compile(r"^\s*(#|echo\s|printf\s)")


SEGMENT_SPLIT_RE = re.compile(r"(?:\|\||&&|;|\|)")


def command_is_dangerous(command: str):
    """Return (pattern_explanation | None) for a shell command string.

    Compound commands are split on ``&&``, ``||``, ``;`` and ``|`` so a
    dangerous command hidden behind a safe prefix (``echo ok && git reset
    --hard``) is still caught, while pure documentation segments
    (``echo "..."``, comments) are skipped.
    """
    if not command:
        return None
    for line in command.splitlines():
        for segment in SEGMENT_SPLIT_RE.split(line):
            segment = segment.strip()
            if not segment or DOC_LINE_RE.match(segment):
                continue
            for pattern, explanation in DANGEROUS_PATTERNS:
                if pattern.search(segment):
                    return explanation
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # fail safe: malformed input never blocks the session

    if not isinstance(payload, dict):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str):
        return 0

    explanation = command_is_dangerous(command)
    if explanation is None:
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "Blocked by frappe-workflow safety hook: "
                        + explanation
                        + " If this is genuinely required, the user must run it "
                        "manually outside the workflow."
                    ),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
