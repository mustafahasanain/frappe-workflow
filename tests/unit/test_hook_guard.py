"""Unit tests for scripts/hooks/guard_dangerous_commands.py."""

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout

import support

_spec = importlib.util.spec_from_file_location(
    "guard_dangerous_commands",
    support.PLUGIN_ROOT / "scripts" / "hooks" / "guard_dangerous_commands.py",
)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def run_hook(payload_text: str):
    """Feed *payload_text* to the hook's main(); return (exit_code, stdout)."""
    stdin = sys.stdin
    sys.stdin = io.StringIO(payload_text)
    try:
        out = io.StringIO()
        with redirect_stdout(out):
            code = guard.main()
        return code, out.getvalue()
    finally:
        sys.stdin = stdin


def bash_payload(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


class DangerousCommandTests(unittest.TestCase):
    BLOCKED = [
        "git reset --hard",
        "git reset   --hard HEAD~3",
        "git clean -fd",
        "git clean -fdx",
        "git clean  -xfd",
        "git push --force origin main",
        "git push -f origin main",
        "git push origin main --force-with-lease",
        "git checkout -- .",
        "git restore .",
        "rm -rf /",
        "rm -rf /*",
        "sudo rm -fr /",
        "bench drop-site car.wash",
        "bench --site car.wash reinstall",
        'mysql -e "DROP DATABASE production"',
        "echo safe && git reset --hard",
    ]

    ALLOWED = [
        "git status --porcelain",
        "git diff --cached HEAD",
        "git log --oneline -5",
        "git pull --ff-only upstream feature/example",
        "git add -- path/to/file.py",
        "git commit -m 'feat(stock): add reservation'",
        "git restore --staged file.py",
        "git checkout -b feature/new-branch",
        "rm -rf .claude/reviews",
        "bench --site car.wash migrate",
        "bench build --app general_trading",
        "python3 -m unittest discover -s tests",
        "grep -R 'git reset --hard' docs/",  # mentions, does not run... blocked? see below
    ]

    def test_blocked_commands(self):
        for command in self.BLOCKED:
            explanation = guard.command_is_dangerous(command)
            self.assertIsNotNone(explanation, f"should block: {command}")

    def test_allowed_commands(self):
        for command in self.ALLOWED[:-1]:  # last entry asserted separately below
            explanation = guard.command_is_dangerous(command)
            self.assertIsNone(explanation, f"should allow: {command}")

    def test_documentation_lines_not_blocked(self):
        self.assertIsNone(
            guard.command_is_dangerous('echo "never run git reset --hard"')
        )
        self.assertIsNone(guard.command_is_dangerous("# git clean -fd is forbidden"))

    def test_grep_for_pattern_is_conservatively_blocked(self):
        # A grep whose argument contains the dangerous string is blocked: the
        # guard prefers a false positive over parsing shell quoting. Documented
        # in docs/troubleshooting.md.
        self.assertIsNotNone(
            guard.command_is_dangerous("grep -R 'git reset --hard' docs/")
        )


class HookIoTests(unittest.TestCase):
    def test_deny_output_shape(self):
        code, out = run_hook(bash_payload("git reset --hard"))
        self.assertEqual(code, 0)
        payload = json.loads(out)
        decision = payload["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("frappe-workflow safety hook", decision["permissionDecisionReason"])

    def test_safe_command_produces_no_output(self):
        code, out = run_hook(bash_payload("git status"))
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_malformed_json_fails_safe(self):
        code, out = run_hook("{this is not json")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_non_bash_tool_ignored(self):
        code, out = run_hook(
            json.dumps({"tool_name": "Write", "tool_input": {"content": "git reset --hard"}})
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_missing_command_field_ignored(self):
        code, out = run_hook(json.dumps({"tool_name": "Bash", "tool_input": {}}))
        self.assertEqual(code, 0)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
