"""The `testing` action prints its result and creates no file.

The Arabic title and description are produced by the model, so the skill
instructions *are* the implementation. What can be tested deterministically
is that nothing in the plugin still promises, describes, or prepares a
testing-task file: no path constant, no template, no instruction to save
one, and no documentation claiming one is generated.

Historical changelog entries are exempt on purpose — they describe what an
older release did — and every remaining mention elsewhere has to be an
explicit backward-compatibility statement.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import support
from core import project_files, workflow_state

PLUGIN_ROOT = support.PLUGIN_ROOT
STATUS_DOC = PLUGIN_ROOT / "skills/frappe-task/examples/status-output.md"
HELP_DOC = PLUGIN_ROOT / "skills/frappe-task/examples/help-output.md"
SKILL_DOC = PLUGIN_ROOT / "skills/testing-task/SKILL.md"
RULES_DOC = PLUGIN_ROOT / "skills/testing-task/references/arabic-testing-task-rules.md"
ROUTING_DOC = PLUGIN_ROOT / "skills/frappe-task/references/command-routing.md"
LIFECYCLE_DOC = PLUGIN_ROOT / "references/file-lifecycle.md"

# Directories whose content the model reads as instructions, plus the two
# top-level documents. tests/ is excluded: these very assertions live there.
SEARCHED_DIRS = ("skills", "references", "docs", "templates", "scripts", "bin", "hooks")
SEARCHED_FILES = ("README.md",)

# Files allowed to describe the old behavior in the past tense.
HISTORY_FILES = {"CHANGELOG.md"}

TESTING_FILE_PATTERN = re.compile(r"testing-task-ar|TESTING_TASK_AR")

# A mention that survives must sit in a paragraph that marks it as history
# or as an explicit prohibition.
LEGACY_MARKERS = (
    "legacy",
    "older",
    "old ",
    "no longer",
    "never",
    "not ",
    "ignored",
    "untouched",
    "must not",
    "absent",
    "there is no",
)


def searched_documents() -> list[Path]:
    paths: list[Path] = []
    for name in SEARCHED_DIRS:
        for path in sorted((PLUGIN_ROOT / name).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                paths.append(path)
    for name in SEARCHED_FILES:
        paths.append(PLUGIN_ROOT / name)
    return paths


def paragraphs(text: str) -> list[str]:
    return re.split(r"\n\s*\n", text)


class NoTestingTaskFileIsPromisedTests(unittest.TestCase):
    """Nothing outside the changelog may present the file as current."""

    def test_every_remaining_mention_is_a_backward_compatibility_note(self):
        for path in searched_documents():
            if path.name in HISTORY_FILES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for block in paragraphs(text):
                if not TESTING_FILE_PATTERN.search(block):
                    continue
                relative = path.relative_to(PLUGIN_ROOT)
                with self.subTest(path=str(relative)):
                    lowered = block.lower()
                    self.assertTrue(
                        any(marker in lowered for marker in LEGACY_MARKERS),
                        f"{relative} still presents a testing-task file as "
                        f"current behavior:\n{block}",
                    )

    def test_no_template_for_a_testing_task_file_remains(self):
        templates = PLUGIN_ROOT / "templates"
        self.assertFalse((templates / "output" / "TESTING_TASK_AR.md").exists())
        for path in templates.rglob("*"):
            if path.is_file():
                with self.subTest(path=str(path.relative_to(PLUGIN_ROOT))):
                    self.assertFalse(
                        TESTING_FILE_PATTERN.search(
                            path.read_text(encoding="utf-8")
                        ),
                        f"{path} still describes a testing-task file",
                    )

    def test_runtime_modules_expose_no_testing_task_path(self):
        self.assertFalse(hasattr(project_files, "TESTING_TASK_AR"))
        for group in (
            project_files.TRACKED_SHARED_FILES,
            project_files.INIT_CREATED_FILES,
            project_files.RESET_PATHS,
        ):
            for path in group:
                with self.subTest(path=path):
                    self.assertNotIn("testing-task", path)
        for old_rel, new_rel in project_files.LEGACY_PATHS:
            with self.subTest(old=old_rel):
                self.assertNotIn("testing-task", old_rel)
                self.assertNotIn("testing-task", new_rel)

    def test_changelog_states_the_current_behavior(self):
        text = (PLUGIN_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        unreleased = text.split("## [0.1.0]")[0]
        self.assertIn("terminal", unreleased.lower())
        self.assertIn("no longer generated", unreleased)
        # The historical entry describing the old behavior stays untouched.
        self.assertIn(".claude/testing-task-ar.md", text.split("## [0.1.0]")[1])


class TestingSkillInstructionsTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL_DOC.read_text(encoding="utf-8")
        self.rules = RULES_DOC.read_text(encoding="utf-8")

    def test_output_shape_is_the_arabic_labels(self):
        for label in ("العنوان:", "الوصف:"):
            with self.subTest(label=label):
                self.assertIn(label, self.rules)

    def test_rules_require_terminal_output(self):
        self.assertRegex(self.rules, r"print(ed)?\s+them\s+directly\s+in\s+the\s+terminal")
        self.assertIn("Terminal Output Only", self.rules)

    def test_rules_record_only_status_and_timestamp(self):
        self.assertIn("state set testing_task.status generated", self.rules)
        self.assertIn("state set testing_task.generated_at", self.rules)
        self.assertNotIn("state set testing_task.path", self.rules)
        self.assertIn("state transition completed", self.rules)

    def test_skill_forbids_writing_a_file(self):
        self.assertIn("No file.", self.skill)
        self.assertIn("generated_at", self.skill)
        self.assertNotIn("path, generated_at", self.skill)

    def test_deployment_skipped_warning_is_still_english_and_separate(self):
        self.assertIn("Deployment was skipped.", self.skill)
        self.assertIn("Never embed the warning inside the Arabic description.", self.skill)

    def test_routing_prints_and_transitions(self):
        routing = ROUTING_DOC.read_text(encoding="utf-8")
        testing_section = routing.split("## `testing`")[1].split("\n## ")[0]
        self.assertIn("printed in the terminal", testing_section)
        self.assertIn("state transition completed", testing_section)
        self.assertIn("No file is written", testing_section)


class StatusOutputTests(unittest.TestCase):
    def setUp(self):
        self.status = STATUS_DOC.read_text(encoding="utf-8")

    def test_pending_form_is_unchanged(self):
        self.assertIn("Testing task: pending", self.status)

    def test_generated_form_shows_a_timestamp_and_no_path(self):
        match = re.search(r"^Testing task: generated \((.+)\)$", self.status, re.M)
        self.assertIsNotNone(
            match, "status-output.md must show the generated testing-task line"
        )
        self.assertRegex(match.group(1), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        for line in self.status.splitlines():
            if line.startswith("Testing task:"):
                with self.subTest(line=line):
                    self.assertNotIn(".md", line)
                    self.assertNotIn("/", line)


class ResetAndLifecycleDocumentationTests(unittest.TestCase):
    def test_reset_list_in_routing_matches_the_reset_paths(self):
        routing = ROUTING_DOC.read_text(encoding="utf-8")
        reset_section = routing.split("## `reset`")[1].split("\n## ")[0]
        cleared = reset_section.split("2. State what is")[0]
        for path in project_files.RESET_PATHS:
            with self.subTest(path=path):
                self.assertIn(path, cleared)
        self.assertNotIn("testing-task-ar.md", cleared)

    def test_lifecycle_documents_the_legacy_file_policy(self):
        lifecycle = LIFECYCLE_DOC.read_text(encoding="utf-8")
        self.assertIn("Legacy Testing-Task Files", lifecycle)
        # The lifecycle table must not list a testing-task file as managed.
        table_rows = [
            line for line in lifecycle.splitlines() if line.startswith("| `docs/")
        ]
        for row in table_rows:
            with self.subTest(row=row):
                self.assertNotIn("testing-task-ar", row)

    def test_state_schema_documentation_has_no_path_field(self):
        section = workflow_state.default_state()["testing_task"]
        self.assertEqual(sorted(section), ["generated_at", "status"])


if __name__ == "__main__":
    unittest.main()
