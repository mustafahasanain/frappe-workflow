"""Unit tests for scripts/core/project_files.py.

Covers the centralized path constants, the managed ``.gitignore`` block,
and migration from the old root-level / ``.claude/`` layout.
"""

import shutil
import unittest

import support
from core import project_files


class PathConstantTests(unittest.TestCase):
    """The layout contract every other module depends on."""

    def test_shared_files_live_under_the_ai_context_directory(self):
        for name in (
            project_files.PROJECT_CONTEXT,
            project_files.FEATURE_CHANGELOG,
            project_files.TASK_PLAN,
            project_files.WORKFLOW_STATE,
            project_files.IMPLEMENTATION_SUMMARY,
            project_files.REVIEWS_DIR,
        ):
            with self.subTest(name=name):
                self.assertTrue(
                    name.startswith(project_files.AI_CONTEXT_DIR + "/"),
                    f"{name} must live under {project_files.AI_CONTEXT_DIR}/",
                )

    def test_exact_shared_paths(self):
        self.assertEqual(project_files.AI_CONTEXT_DIR, "docs/ai-context")
        self.assertEqual(
            project_files.PROJECT_CONTEXT, "docs/ai-context/PROJECT_CONTEXT.md"
        )
        self.assertEqual(
            project_files.FEATURE_CHANGELOG, "docs/ai-context/FEATURE_CHANGELOG.md"
        )
        self.assertEqual(project_files.TASK_PLAN, "docs/ai-context/TASK_PLAN.md")
        self.assertEqual(
            project_files.WORKFLOW_STATE, "docs/ai-context/task-workflow.json"
        )
        self.assertEqual(
            project_files.IMPLEMENTATION_SUMMARY,
            "docs/ai-context/implementation-summary.md",
        )
        self.assertEqual(project_files.REVIEWS_DIR, "docs/ai-context/reviews")

    def test_no_testing_task_path_constant_exists(self):
        """`testing` prints its output; there is no file to name."""
        self.assertFalse(hasattr(project_files, "TESTING_TASK_AR"))
        for name, value in vars(project_files).items():
            if name.isupper() and isinstance(value, str):
                with self.subTest(constant=name):
                    self.assertNotIn("testing-task", value)

    def test_machine_local_files_stay_under_claude(self):
        self.assertEqual(project_files.CLAUDE_DIR, ".claude")
        self.assertEqual(
            project_files.DEPLOYMENT_CONFIG, ".claude/deployment.local.json"
        )
        self.assertEqual(project_files.WORKFLOW_LOCK, ".claude/task-workflow.lock")

    def test_init_never_creates_task_artifacts(self):
        for name in (
            project_files.TASK_PLAN,
            project_files.WORKFLOW_STATE,
            project_files.IMPLEMENTATION_SUMMARY,
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, project_files.INIT_CREATED_FILES)

    def test_reset_preserves_project_documentation_and_deployment_config(self):
        for name in (
            project_files.PROJECT_CONTEXT,
            project_files.FEATURE_CHANGELOG,
            project_files.DEPLOYMENT_CONFIG,
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, project_files.RESET_PATHS)

    def test_reset_clears_every_active_task_artifact(self):
        self.assertEqual(
            sorted(project_files.RESET_PATHS),
            sorted(
                (
                    project_files.WORKFLOW_STATE,
                    project_files.TASK_PLAN,
                    project_files.IMPLEMENTATION_SUMMARY,
                    project_files.REVIEWS_DIR,
                )
            ),
        )

    def test_reset_never_lists_a_testing_task_file(self):
        """A legacy testing-task file is not an active workflow artifact."""
        for path in project_files.RESET_PATHS:
            with self.subTest(path=path):
                self.assertNotIn("testing-task", path)

    def test_tracked_shared_files_hold_no_testing_task_file(self):
        for path in project_files.TRACKED_SHARED_FILES:
            with self.subTest(path=path):
                self.assertNotIn("testing-task", path)


class GitignoreBlockTests(unittest.TestCase):
    def setUp(self):
        self.repo = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.path = self.repo / ".gitignore"

    def block(self) -> str:
        text = self.path.read_text(encoding="utf-8")
        begin = text.index(project_files.GITIGNORE_BEGIN)
        end = text.index(project_files.GITIGNORE_END) + len(project_files.GITIGNORE_END)
        return text[begin:end]

    def test_creates_file_when_missing(self):
        result = project_files.ensure_gitignore_block(self.repo)
        self.assertEqual(result, {"changed": True, "action": "created"})
        self.assertEqual(
            self.block(),
            "\n".join(
                [
                    project_files.GITIGNORE_BEGIN,
                    ".claude/deployment.local.json",
                    ".claude/task-workflow.lock",
                    project_files.GITIGNORE_END,
                ]
            ),
        )

    def test_block_contains_only_machine_local_entries(self):
        project_files.ensure_gitignore_block(self.repo)
        entries = [
            line
            for line in self.block().splitlines()
            if not line.startswith("#")
        ]
        self.assertEqual(
            entries,
            [project_files.DEPLOYMENT_CONFIG, project_files.WORKFLOW_LOCK],
        )

    def test_shared_files_are_not_ignored(self):
        project_files.ensure_gitignore_block(self.repo)
        text = self.path.read_text(encoding="utf-8")
        for name in (
            project_files.AI_CONTEXT_DIR,
            project_files.PROJECT_CONTEXT,
            project_files.FEATURE_CHANGELOG,
            project_files.TASK_PLAN,
            project_files.WORKFLOW_STATE,
            project_files.IMPLEMENTATION_SUMMARY,
            project_files.REVIEWS_DIR,
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, text)

    def test_idempotent(self):
        project_files.ensure_gitignore_block(self.repo)
        first = self.path.read_text(encoding="utf-8")
        result = project_files.ensure_gitignore_block(self.repo)
        self.assertEqual(result, {"changed": False, "action": "unchanged"})
        self.assertEqual(self.path.read_text(encoding="utf-8"), first)

    def test_appends_without_touching_user_content(self):
        self.path.write_text("node_modules/\n*.log\n", encoding="utf-8")
        result = project_files.ensure_gitignore_block(self.repo)
        self.assertEqual(result["action"], "appended")
        text = self.path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("node_modules/\n*.log\n"))
        self.assertIn(project_files.WORKFLOW_LOCK, text)

    def test_repair_drops_legacy_shared_entries(self):
        self.path.write_text(
            "\n".join(
                [
                    "node_modules/",
                    project_files.GITIGNORE_BEGIN,
                    *project_files.LEGACY_GITIGNORE_ENTRIES,
                    project_files.DEPLOYMENT_CONFIG,
                    project_files.GITIGNORE_END,
                    "*.log",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        result = project_files.ensure_gitignore_block(self.repo)
        self.assertEqual(result["action"], "repaired")
        text = self.path.read_text(encoding="utf-8")
        for legacy in project_files.LEGACY_GITIGNORE_ENTRIES:
            with self.subTest(legacy=legacy):
                self.assertNotIn(legacy, text)
        # user-managed lines on both sides of the block survive
        self.assertIn("node_modules/", text)
        self.assertIn("*.log", text)
        self.assertIn(project_files.WORKFLOW_LOCK, text)

    def test_duplicated_markers_reported_as_conflict(self):
        self.path.write_text(
            "\n".join(
                [
                    project_files.GITIGNORE_BEGIN,
                    project_files.GITIGNORE_END,
                    project_files.GITIGNORE_BEGIN,
                    project_files.GITIGNORE_END,
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        before = self.path.read_text(encoding="utf-8")
        result = project_files.ensure_gitignore_block(self.repo)
        self.assertEqual(result["action"], "conflict")
        self.assertFalse(result["changed"])
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)


class LegacyMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)

    def build_legacy_layout(self):
        support.write_repo_file(self.repo, "PROJECT_CONTEXT.md", "# Context\n")
        support.write_repo_file(self.repo, "FEATURE_CHANGELOG.md", "# Changelog\n")
        support.write_repo_file(self.repo, "TASK_PLAN.md", "# Plan\n")
        support.write_repo_file(self.repo, ".claude/task-workflow.json", "{}\n")
        support.write_repo_file(
            self.repo, ".claude/implementation-summary.md", "# Summary\n"
        )
        support.write_repo_file(self.repo, ".claude/testing-task-ar.md", "# Testing\n")
        support.write_repo_file(
            self.repo, ".claude/reviews/round-001-prompt.md", "prompt one\n"
        )
        support.write_repo_file(
            self.repo, ".claude/reviews/round-001-result.md", "result one\n"
        )
        support.write_repo_file(
            self.repo, project_files.DEPLOYMENT_CONFIG, '{"demo_server": {}}\n'
        )

    def test_migrates_every_old_path(self):
        self.build_legacy_layout()
        result = project_files.migrate_legacy_layout(self.repo)

        self.assertTrue(result["changed"])
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(
            sorted(item["to"] for item in result["moved"]),
            sorted(
                (
                    project_files.PROJECT_CONTEXT,
                    project_files.FEATURE_CHANGELOG,
                    project_files.TASK_PLAN,
                    project_files.WORKFLOW_STATE,
                    project_files.IMPLEMENTATION_SUMMARY,
                    project_files.REVIEWS_DIR,
                )
            ),
        )

        for old_rel, new_rel in project_files.LEGACY_PATHS:
            with self.subTest(old=old_rel):
                self.assertFalse((self.repo / old_rel).exists())
                self.assertTrue((self.repo / new_rel).exists())

    def test_preserves_contents_and_review_history(self):
        self.build_legacy_layout()
        project_files.migrate_legacy_layout(self.repo)

        self.assertEqual(
            (self.repo / project_files.TASK_PLAN).read_text(encoding="utf-8"),
            "# Plan\n",
        )
        reviews = self.repo / project_files.REVIEWS_DIR
        self.assertEqual(
            sorted(p.name for p in reviews.iterdir()),
            ["round-001-prompt.md", "round-001-result.md"],
        )
        self.assertEqual(
            (reviews / "round-001-result.md").read_text(encoding="utf-8"),
            "result one\n",
        )

    def test_never_moves_the_deployment_config(self):
        self.build_legacy_layout()
        project_files.migrate_legacy_layout(self.repo)
        self.assertTrue((self.repo / project_files.DEPLOYMENT_CONFIG).is_file())
        self.assertFalse(
            (self.repo / project_files.AI_CONTEXT_DIR / "deployment.local.json").exists()
        )

    def test_never_moves_a_legacy_testing_task_file(self):
        """The testing task is terminal output; its old file is not managed."""
        self.build_legacy_layout()
        result = project_files.migrate_legacy_layout(self.repo)

        self.assertNotIn(
            ".claude/testing-task-ar.md",
            [item["from"] for item in result["moved"]],
        )
        legacy = self.repo / ".claude/testing-task-ar.md"
        self.assertTrue(legacy.is_file(), "a legacy testing task must be left alone")
        self.assertEqual(legacy.read_text(encoding="utf-8"), "# Testing\n")
        self.assertFalse(
            (self.repo / "docs/ai-context/testing-task-ar.md").exists(),
            "migration must not create a testing-task file at the new location",
        )

    def test_leaves_an_already_migrated_testing_task_file_untouched(self):
        """An app migrated by an older version keeps its docs/ copy as-is."""
        self.build_legacy_layout()
        support.write_repo_file(
            self.repo, "docs/ai-context/testing-task-ar.md", "# Old Arabic task\n"
        )

        result = project_files.migrate_legacy_layout(self.repo)

        # It is not a managed path, so it cannot cause a migration conflict.
        self.assertEqual(result["conflicts"], [])
        self.assertTrue(result["changed"])
        self.assertEqual(
            (self.repo / "docs/ai-context/testing-task-ar.md").read_text(
                encoding="utf-8"
            ),
            "# Old Arabic task\n",
        )

    def test_updates_the_managed_gitignore_block(self):
        self.build_legacy_layout()
        support.write_repo_file(
            self.repo,
            ".gitignore",
            "\n".join(
                [
                    project_files.GITIGNORE_BEGIN,
                    *project_files.LEGACY_GITIGNORE_ENTRIES,
                    project_files.DEPLOYMENT_CONFIG,
                    project_files.GITIGNORE_END,
                ]
            )
            + "\n",
        )
        project_files.migrate_legacy_layout(self.repo)
        text = (self.repo / ".gitignore").read_text(encoding="utf-8")
        for legacy in project_files.LEGACY_GITIGNORE_ENTRIES:
            with self.subTest(legacy=legacy):
                self.assertNotIn(legacy, text)
        self.assertIn(project_files.WORKFLOW_LOCK, text)

    def test_idempotent_on_repeat(self):
        self.build_legacy_layout()
        project_files.migrate_legacy_layout(self.repo)
        second = project_files.migrate_legacy_layout(self.repo)
        self.assertFalse(second["changed"])
        self.assertEqual(second["moved"], [])
        self.assertEqual(second["conflicts"], [])

    def test_no_op_on_a_current_layout(self):
        support.write_repo_file(self.repo, project_files.TASK_PLAN, "# Plan\n")
        result = project_files.migrate_legacy_layout(self.repo)
        self.assertFalse(result["changed"])
        self.assertEqual(result["moved"], [])
        self.assertEqual(result["conflicts"], [])

    def test_conflict_stops_without_touching_anything(self):
        support.write_repo_file(self.repo, "TASK_PLAN.md", "old plan\n")
        support.write_repo_file(self.repo, project_files.TASK_PLAN, "new plan\n")
        support.write_repo_file(self.repo, ".claude/testing-task-ar.md", "old ar\n")

        result = project_files.migrate_legacy_layout(self.repo)

        self.assertEqual(
            result["conflicts"],
            [{"from": "TASK_PLAN.md", "to": project_files.TASK_PLAN}],
        )
        self.assertFalse(result["changed"])
        # Nothing moved at all: an ambiguous repository is reported, not guessed at.
        self.assertEqual(result["moved"], [])
        self.assertEqual(
            (self.repo / "TASK_PLAN.md").read_text(encoding="utf-8"), "old plan\n"
        )
        self.assertEqual(
            (self.repo / project_files.TASK_PLAN).read_text(encoding="utf-8"),
            "new plan\n",
        )
        self.assertTrue((self.repo / ".claude/testing-task-ar.md").is_file())
        self.assertFalse((self.repo / ".gitignore").exists())

    def test_dry_run_reports_without_moving(self):
        self.build_legacy_layout()
        result = project_files.migrate_legacy_layout(self.repo, dry_run=True)
        self.assertTrue(result["changed"])
        self.assertEqual(len(result["moved"]), len(project_files.LEGACY_PATHS))
        for old_rel, new_rel in project_files.LEGACY_PATHS:
            with self.subTest(old=old_rel):
                self.assertTrue((self.repo / old_rel).exists())
                self.assertFalse((self.repo / new_rel).exists())


class FrontmatterTests(unittest.TestCase):
    def test_scalars_and_lists(self):
        data, body = project_files.parse_frontmatter(
            "---\n"
            "task_id: TASK-2026-001\n"
            "count: 3\n"
            "done: true\n"
            "missing: null\n"
            "tags:\n"
            "  - stock\n"
            "  - telegram\n"
            "---\n"
            "# Body\n"
        )
        self.assertEqual(data["task_id"], "TASK-2026-001")
        self.assertEqual(data["count"], "3")
        self.assertIs(data["done"], True)
        self.assertIsNone(data["missing"])
        self.assertEqual(data["tags"], ["stock", "telegram"])
        self.assertEqual(body.strip(), "# Body")

    def test_missing_frontmatter(self):
        data, body = project_files.parse_frontmatter("# Just a heading\n")
        self.assertIsNone(data)
        self.assertEqual(body, "# Just a heading\n")

    def test_unterminated_frontmatter(self):
        text = "---\ntask_id: TASK-2026-001\n# no closing marker\n"
        data, body = project_files.parse_frontmatter(text)
        self.assertIsNone(data)
        self.assertEqual(body, text)


class ExtractSectionsTests(unittest.TestCase):
    def test_headings_in_order_and_code_blocks_skipped(self):
        sections = project_files.extract_sections(
            "# Top\n"
            "\n"
            "```python\n"
            "# not a heading\n"
            "```\n"
            "\n"
            "## Second\n"
            "### Third\n"
        )
        self.assertEqual(sections, ["Top", "Second", "Third"])


if __name__ == "__main__":
    unittest.main()
