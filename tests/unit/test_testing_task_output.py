"""The `testing` action copies its result, prints it, and creates no file.

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

import cli  # noqa: E402  (scripts/ is on sys.path via support)

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


def flat(text: str) -> str:
    """Lowercase *text* with Markdown emphasis and line wrapping removed.

    These documents are prose: an assertion about what they say must not
    depend on where a sentence happened to wrap or on a pair of asterisks.
    """
    return re.sub(r"\s+", " ", text.replace("*", "").replace("`", "")).lower()


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

    def test_rules_require_the_clipboard_then_terminal_output(self):
        self.assertIn("Clipboard First, Then Terminal", self.rules)
        self.assertIn("clipboard copy --preview", self.rules)
        self.assertIn("Never a File", self.rules)

    def test_rules_stop_the_workflow_when_the_clipboard_is_unavailable(self):
        section = self.rules.split("### 3. On a missing clipboard")[1].split("\n### ")[0]
        self.assertIn("exit `8`", self.rules)
        for requirement in (
            "not** print the Arabic text",
            "do not record `testing_task`",
            "do not transition to `completed`",
            "Never** install a package",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, section)

    def test_rules_record_state_only_after_a_successful_copy(self):
        closing = self.rules.split("## Closing")[1]
        self.assertIn("Only after a successful copy", closing)

    def test_rules_record_only_status_and_timestamp(self):
        self.assertIn("state set testing_task.status generated", self.rules)
        self.assertIn("state set testing_task.generated_at", self.rules)
        self.assertNotIn("state set testing_task.path", self.rules)
        self.assertIn("state transition completed", self.rules)

    def test_skill_forbids_writing_a_file(self):
        self.assertIn("No file.", self.skill)
        self.assertIn("generated_at", self.skill)
        self.assertNotIn("path, generated_at", self.skill)

    def test_skill_gates_everything_on_the_clipboard_copy(self):
        section = self.skill.split("## Order of Operations")[1].split("\n## ")[0]
        self.assertIn("clipboard copy", section)
        self.assertIn("Exit code `0`", section)
        self.assertIn("Exit code `8`", section)
        # A failed copy must stop the workflow, not fall back to printing.
        self.assertIn("Print nothing of the Arabic", section)
        self.assertIn("record no state", section)
        self.assertIn("transition nothing", section)
        self.assertIn("Never install a package", section)

    def test_skill_forbids_completing_after_a_failed_copy(self):
        prohibited = self.skill.split("## Prohibited")[1].split("\n## ")[0]
        self.assertIn("failed clipboard copy", prohibited)
        self.assertIn("Installing a clipboard package", prohibited)

    def test_deployment_skipped_warning_is_still_english_and_separate(self):
        self.assertIn("Deployment was skipped.", self.skill)
        self.assertIn("Never embed the warning inside the Arabic description.", self.skill)

    def test_routing_copies_prints_and_transitions(self):
        routing = ROUTING_DOC.read_text(encoding="utf-8")
        testing_section = routing.split("## `testing`")[1].split("\n## ")[0]
        self.assertIn("clipboard copy", testing_section)
        self.assertIn("printed in the terminal", testing_section)
        self.assertIn("state transition completed", testing_section)
        self.assertIn("No file is written", testing_section)
        # The failure path must be routed too, not left to improvisation.
        self.assertIn("exits 8", testing_section)
        self.assertIn("print no Arabic text", testing_section)
        self.assertIn("transition nothing", testing_section)


class LogicalClipboardVersusVisualTerminalTests(unittest.TestCase):
    """The instructions must keep the two representations apart.

    The model is what executes them, so a document that blurs "copied" and
    "shown" is the same bug as code that copies the reordered text.
    """

    def setUp(self):
        self.skill = SKILL_DOC.read_text(encoding="utf-8")
        self.rules = RULES_DOC.read_text(encoding="utf-8")
        self.routing = ROUTING_DOC.read_text(encoding="utf-8")
        self.flat_skill = flat(self.skill)
        self.flat_rules = flat(self.rules)

    def test_every_instruction_uses_the_preview_flag(self):
        for name, text in (
            ("SKILL.md", self.skill),
            ("rules", self.rules),
            ("routing", self.routing),
        ):
            with self.subTest(document=name):
                self.assertIn("clipboard copy --preview", text)

    def test_rules_promise_the_clipboard_the_unmodified_logical_text(self):
        self.assertIn("logical Unicode order", self.rules)
        self.assertIn("not reordered, not reshaped, not reversed", self.rules)

    def test_rules_quote_the_output_the_command_actually_prints(self):
        # If the CLI wording changes, the instructions have to follow.
        self.assertIn(cli.PREVIEW_HEADLINE, self.rules)
        self.assertIn(cli.PREVIEW_FOOTER, self.rules)

    def test_the_logical_text_is_never_printed_and_the_preview_never_stored(self):
        for name, text in (
            ("SKILL.md", self.flat_skill),
            ("rules", self.flat_rules),
        ):
            with self.subTest(document=name):
                self.assertIn("never print the logical arabic", text)
                self.assertIn("workflow state", text)
        self.assertIn(
            "never put the preview on the clipboard, in a file, or in the "
            "workflow state",
            self.flat_rules,
        )

    def test_the_model_may_not_reorder_the_text_itself(self):
        prohibited = self.skill.split("## Prohibited")[1].split("\n## ")[0]
        self.assertIn("Reordering, reshaping, or reversing the text yourself", prohibited)
        self.assertIn("--preview", prohibited)

    def test_a_failed_preview_still_leaves_a_completed_hand_off(self):
        stopping = flat(self.skill.split("## Stopping Conditions")[1].split("\n## ")[0])
        self.assertIn("preview could not be formatted", stopping)
        self.assertIn("never print the logical arabic", stopping)
        self.assertIn("preview could not be formatted", self.flat_rules)

    def test_the_completed_retry_copies_and_previews_without_a_state_change(self):
        repeat = flat(
            self.skill.split("## Repeating After Completion")[1].split("\n## ")[0]
        )
        self.assertIn("copy it to the clipboard", repeat)
        self.assertIn("preview", repeat)
        for unchanged in ("no transition", "no state write", "no file"):
            with self.subTest(unchanged=unchanged):
                self.assertIn(unchanged, repeat)

    def test_the_deployment_skipped_warning_comes_after_the_preview(self):
        self.assertIn("after the preview", flat(self.skill) + flat(self.routing))

    def test_user_documentation_says_which_one_to_paste(self):
        usage = flat((PLUGIN_ROOT / "docs/usage.md").read_text(encoding="utf-8"))
        troubleshooting = flat(
            (PLUGIN_ROOT / "docs/troubleshooting.md").read_text(encoding="utf-8")
        )
        self.assertIn("paste from the clipboard, not from that preview.", usage)
        self.assertIn("original logical unicode order", usage)
        self.assertIn("terminal-only preview", usage)
        self.assertIn("the preview could not be formatted", troubleshooting)
        self.assertIn("always paste from the clipboard", troubleshooting)


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
