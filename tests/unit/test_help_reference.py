"""Consistency tests for the canonical `help` output.

The help text is rendered by the model from
``skills/frappe-task/examples/help-output.md``, so it cannot be executed in
a unit test. What can be tested is that the canonical source stays complete
and consistent: every action documented, only canonical stages named, the
workflow chain in the right order, and no description truncated mid-thought
(the defect that made this file necessary).
"""

import re
import unittest

import support
from core import project_files, workflow_state

HELP_DOC = (
    support.PLUGIN_ROOT / "skills" / "frappe-task" / "examples" / "help-output.md"
)
SKILL_MD = support.PLUGIN_ROOT / "skills" / "frappe-task" / "SKILL.md"

ACTIONS = (
    "init",
    "start",
    "status",
    "review",
    "apply-review",
    "commit",
    "deploy",
    "testing",
    "reset",
    "help",
)

# Stage names that do not exist but are plausible inventions.
FORBIDDEN_STAGES = (
    "in_review",
    "awaiting_review",
    "in_progress",
    "done",
    "finished",
    "deploying",
    "reviewing",
    "pending_review",
)

WORKFLOW_CHAIN = (
    "planning",
    "→ implementation",
    "→ codex_review",
    "→ review_fixes when changes are required",
    "→ codex_review until approved",
    "→ ready_for_commit",
    "→ committed",
    "→ deployed or deployment_skipped",
    "→ completed",
)


def canonical_block() -> str:
    """Return the fenced ```text block that the help action prints."""
    text = HELP_DOC.read_text(encoding="utf-8")
    match = re.search(r"```text\n(.*?)```", text, re.S)
    assert match, "help-output.md must contain a ```text block"
    return match.group(1)


class HelpDocumentTests(unittest.TestCase):
    def setUp(self):
        self.block = canonical_block()

    def test_document_exists(self):
        self.assertTrue(HELP_DOC.is_file())

    def test_every_action_is_documented(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                self.assertIsNotNone(
                    re.search(rf"^  {re.escape(action)} {{2,}}\S", self.block, re.M),
                    f"'{action}' is missing from the canonical help output",
                )

    def test_no_undocumented_action_entries(self):
        listed = re.findall(r"^  ([a-z][a-z-]*) {2,}\S", self.block, re.M)
        self.assertEqual(sorted(set(listed)), sorted(ACTIONS))

    def test_all_canonical_stages_listed(self):
        for stage in workflow_state.STAGES:
            with self.subTest(stage=stage):
                self.assertIn(stage, self.block)

    def test_no_invented_stages(self):
        for stage in FORBIDDEN_STAGES:
            with self.subTest(stage=stage):
                self.assertNotIn(stage, self.block)

    def test_workflow_chain_in_order(self):
        position = -1
        for fragment in WORKFLOW_CHAIN:
            found = self.block.find(fragment, position + 1)
            self.assertGreater(
                found, position, f"workflow chain out of order at '{fragment}'"
            )
            position = found

    def test_no_action_resume_is_stated(self):
        self.assertRegex(self.block, r"no action resumes the active task")
        self.assertIn(project_files.WORKFLOW_STATE, self.block)

    def test_shared_paths_are_shown_in_full(self):
        for name in (
            project_files.WORKFLOW_STATE,
            project_files.PROJECT_CONTEXT,
            project_files.FEATURE_CHANGELOG,
            project_files.TASK_PLAN,
        ):
            with self.subTest(name=name):
                self.assertIn(name, self.block)

    def test_no_stale_shared_locations(self):
        """The old locations must not be advertised anywhere in help."""
        for stale in (
            ".claude/task-workflow.json",
            ".claude/implementation-summary.md",
            ".claude/testing-task-ar.md",
            "docs/ai-context/testing-task-ar.md",
            ".claude/reviews",
        ):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, self.block)

    def test_testing_action_is_described_as_clipboard_and_terminal_output(self):
        """Help must promise the clipboard, and no file the plugin never writes."""
        self.assertNotIn("testing-task-ar", self.block)
        description = re.search(
            r"^  testing {2,}(.+?)\n\n", self.block, re.S | re.M
        ).group(1)
        self.assertRegex(description, r"clipboard")
        # The terminal shows a preview; the clipboard is what gets pasted.
        self.assertRegex(description, r"preview")
        self.assertRegex(description, r"[Nn]othing is saved to a file")

    def test_cross_device_continuation_is_explained(self):
        self.assertIn(project_files.AI_CONTEXT_DIR, self.block)
        self.assertRegex(self.block, r"tracked by Git")
        self.assertRegex(self.block, r"another\s+computer")
        # Deployment config is explicitly per-computer.
        self.assertIn(project_files.DEPLOYMENT_CONFIG, self.block)

    def test_help_is_declared_read_only(self):
        self.assertRegex(self.block, r"help {2,}Show this message\. Read-only\.")

    def test_key_facts_are_accurate(self):
        # init must not be described as starting a task.
        self.assertIn("Does not start a task", self.block)
        # review must not imply Codex runs automatically.
        self.assertIn("Codex is not run automatically", self.block)
        # apply-review must name both recognized results.
        self.assertIn("APPROVED or CHANGES_REQUIRED", self.block)
        # testing must name the Arabic title and description.
        self.assertIn("Arabic testing-team title and", self.block)
        # start must name the plan artifact.
        self.assertIn("TASK_PLAN.md", self.block)

    def test_no_description_is_truncated(self):
        """Every action description must be a complete sentence.

        Guards the original defect, where an improvised description was cut
        mid-word ('continue fr...').
        """
        descriptions: dict[str, list[str]] = {}
        current = None
        for line in self.block.splitlines():
            start = re.match(r"^  ([a-z][a-z-]*) {2,}(\S.*)$", line)
            if start:
                current = start.group(1)
                descriptions[current] = [start.group(2).rstrip()]
                continue
            if current and re.match(r"^ {16,}\S", line):
                descriptions[current].append(line.strip())
                continue
            if not line.strip():
                current = None
        self.assertEqual(sorted(descriptions), sorted(ACTIONS))
        for action, parts in descriptions.items():
            with self.subTest(action=action):
                joined = " ".join(parts)
                self.assertTrue(
                    joined.endswith("."),
                    f"'{action}' description looks truncated: ...{joined[-40:]!r}",
                )


class SkillConsistencyTests(unittest.TestCase):
    """The skill body and the canonical help must agree on the action list."""

    def setUp(self):
        self.skill = SKILL_MD.read_text(encoding="utf-8")

    def test_argument_hint_lists_every_action(self):
        match = re.search(r"^argument-hint:\s*\"(.+)\"$", self.skill, re.M)
        self.assertIsNotNone(match, "SKILL.md must declare an argument-hint")
        hint = match.group(1)
        listed = re.search(r"\[([^\]]+)\]", hint).group(1).split("|")
        self.assertEqual(sorted(listed), sorted(ACTIONS))

    def test_recognized_actions_line_matches(self):
        section = re.search(
            r"Recognized actions:(.+?)\n\n", self.skill, re.S
        ).group(1)
        listed = re.findall(r"`([a-z][a-z-]*)`", section)
        self.assertEqual(sorted(listed), sorted(ACTIONS))

    def test_routing_table_covers_every_action(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                self.assertIsNotNone(
                    re.search(rf"^\|\s*`{re.escape(action)}`\s*\|", self.skill, re.M),
                    f"'{action}' missing from the SKILL.md routing table",
                )

    def test_skill_lists_only_canonical_stages(self):
        for stage in FORBIDDEN_STAGES:
            with self.subTest(stage=stage):
                self.assertNotIn(stage, self.skill)


if __name__ == "__main__":
    unittest.main()
