"""Integration tests: run bin/frappe-workflow as a subprocess against
temporary repositories. No network, no SSH, no real Frappe installation."""

import json
import shutil
import subprocess
import unittest

import support
from core import project_files, workflow_state

CLI = support.PLUGIN_ROOT / "bin" / "frappe-workflow"


def run_cli(*args, cwd=None):
    return subprocess.run(
        [str(CLI), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=support.GIT_ENV,
    )


class CliBasicsTests(unittest.TestCase):
    def test_wrapper_is_executable_and_prints_help(self):
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("frappe-workflow", result.stdout)

    def test_invalid_usage_exit_code(self):
        result = run_cli("definitely-not-a-command")
        self.assertEqual(result.returncode, 2)


class DetectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bench = support.make_bench(self.tmp)
        self.app = self.bench / "apps" / "general_trading"

    def test_detect_json(self):
        result = run_cli("--json", "detect", cwd=self.app)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["app_name"], "general_trading")
        self.assertEqual(data["git"]["branch"], "main")
        self.assertEqual([s["name"] for s in data["sites"]], ["car.wash"])

    def test_detect_outside_bench_fails(self):
        outside = self.tmp / "plain"
        outside.mkdir()
        result = run_cli("detect", cwd=outside)
        self.assertEqual(result.returncode, 3)
        self.assertIn("error:", result.stderr)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)

    def test_state_init_show_transition(self):
        result = run_cli("state", "init", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

        result = run_cli("state", "show", cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["current_stage"], "planning")

        result = run_cli("state", "transition", "implementation", "--reason", "t", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

        result = run_cli("state", "transition", "committed", cwd=self.repo)
        self.assertEqual(result.returncode, 5)
        self.assertIn("TRANSITION_REJECTED", result.stderr)

    def test_blocker_add_and_clear(self):
        run_cli("state", "init", cwd=self.repo)
        result = run_cli("state", "blocker", "add", "step 1: fixture blocker", cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        state = json.loads(run_cli("state", "show", cwd=self.repo).stdout)
        self.assertEqual(len(state["blockers"]), 1)
        run_cli("state", "blocker", "clear", cwd=self.repo)
        state = json.loads(run_cli("state", "show", cwd=self.repo).stdout)
        self.assertEqual(state["blockers"], [])


class ValidatorExitCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)

    def test_task_plan_validation(self):
        result = run_cli("validate", "task-plan", cwd=self.repo)
        self.assertEqual(result.returncode, 1)  # missing file

        support.write_fixture_file(
            self.repo, project_files.TASK_PLAN, "sample-task-plan.md"
        )
        result = run_cli("validate", "task-plan", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_project_context_validation(self):
        support.write_fixture_file(
            self.repo, project_files.PROJECT_CONTEXT, "sample-project-context.md"
        )
        result = run_cli("validate", "project-context", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_workflow_state_validation_json(self):
        result = run_cli("--json", "validate", "workflow-state", cwd=self.repo)
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertFalse(data["valid"])


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)
        support.write_fixture_file(
            self.repo, project_files.FEATURE_CHANGELOG, "sample-feature-changelog.md"
        )

    def test_next_id(self):
        result = run_cli(
            "feature", "next-id", "--type", "FEATURE", "--module", "Stock", cwd=self.repo
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "FEAT-STOCK-002")

    def test_search_json(self):
        result = run_cli("--json", "feature", "search", "telegram reports", cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        results = json.loads(result.stdout)
        self.assertEqual(results[0]["id"], "INT-TELEGRAM-001")

    def test_validate_index(self):
        result = run_cli("feature", "validate-index", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)


class GitAndReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)

    def test_fingerprint_stable_and_sensitive(self):
        first = run_cli("git", "fingerprint", cwd=self.repo).stdout.strip()
        second = run_cli("git", "fingerprint", cwd=self.repo).stdout.strip()
        self.assertEqual(first, second)
        self.assertRegex(first, r"^[0-9a-f]{64}$")
        (self.repo / "x.py").write_text("X = 1\n", encoding="utf-8")
        third = run_cli("git", "fingerprint", cwd=self.repo).stdout.strip()
        self.assertNotEqual(first, third)

    def test_review_bundle_creation(self):
        support.write_fixture_file(
            self.repo, project_files.TASK_PLAN, "sample-task-plan.md"
        )
        support.write_repo_file(
            self.repo,
            project_files.IMPLEMENTATION_SUMMARY,
            "# Implementation Summary\n\nDone.\n",
        )
        result = run_cli("--json", "review", "bundle", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["round"], 1)
        prompt = self.repo / data["prompt_path"]
        self.assertTrue(prompt.is_file())
        self.assertIn("TASK-2026-001", prompt.read_text(encoding="utf-8"))

    def test_review_parse_result(self):
        result_file = self.repo / "result.md"
        result_file.write_text(
            support.read_fixture("sample-review-result.md"), encoding="utf-8"
        )
        result = run_cli("review", "parse-result", str(result_file), cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "CHANGES_REQUIRED")
        self.assertEqual(len(data["findings"]), 2)


class SecurityScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)

    def test_clean_repo_passes(self):
        result = run_cli("security", "scan", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_security_requires_subcommand(self):
        result = run_cli("security", cwd=self.repo)
        self.assertEqual(result.returncode, 2)

    def test_secret_blocks_with_exit_7(self):
        token = support.synthetic_secret("prod-", "9a8b7c6d", "5e4f3g2h1i0j")
        (self.repo / "leak.py").write_text(
            f'access_token = "{token}"\n', encoding="utf-8"
        )
        result = run_cli("--json", "security", "scan", cwd=self.repo)
        self.assertEqual(result.returncode, 7)
        data = json.loads(result.stdout)
        self.assertEqual(data["blocking"], 1)
        self.assertNotIn(token, result.stdout)


class DeploymentCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)

    def test_missing_config_exit_6(self):
        result = run_cli("deployment", "validate-config", cwd=self.repo)
        self.assertEqual(result.returncode, 6)
        self.assertIn("DEPLOY_NO_CONFIG", result.stderr)

    def test_valid_config_and_required_commands(self):
        support.write_repo_file(
            self.repo,
            project_files.DEPLOYMENT_CONFIG,
            (
                support.PLUGIN_ROOT / "templates/state/deployment.local.json.example"
            ).read_text(encoding="utf-8"),
        )

        result = run_cli("deployment", "validate-config", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

        (self.repo / "hooks.py").write_text("app_name = 'x'\n", encoding="utf-8")
        support.run_git(self.repo, "add", "hooks.py")
        result = run_cli("--json", "deployment", "required-commands", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = [item["command"] for item in json.loads(result.stdout)]
        self.assertIn(["bench", "--site", "car.wash", "migrate"], commands)

    def test_verify_matching_and_mismatching_head(self):
        support.write_repo_file(
            self.repo,
            project_files.DEPLOYMENT_CONFIG,
            (
                support.PLUGIN_ROOT / "templates/state/deployment.local.json.example"
            ).read_text(encoding="utf-8"),
        )
        ok = run_cli(
            "deployment", "verify",
            "--expected", "abc1234", "--server-head", "abc1234def56789",
            cwd=self.repo,
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        bad = run_cli(
            "deployment", "verify",
            "--expected", "abc1234", "--server-head", "fff9999",
            cwd=self.repo,
        )
        self.assertEqual(bad.returncode, 6)
        self.assertIn("VERIFY_MISMATCH", bad.stderr)


class StateSetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)
        run_cli("state", "init", cwd=self.repo)

    def test_set_string_and_typed_values(self):
        self.assertEqual(
            run_cli("state", "set", "task_id", "TASK-2026-007", cwd=self.repo).returncode,
            0,
        )
        self.assertEqual(
            run_cli(
                "state", "set", "codex_review.round", "2", "--json-value", cwd=self.repo
            ).returncode,
            0,
        )
        state = json.loads(run_cli("state", "show", cwd=self.repo).stdout)
        self.assertEqual(state["task_id"], "TASK-2026-007")
        self.assertEqual(state["codex_review"]["round"], 2)  # int, not "2"

    def test_stage_cannot_be_set_directly(self):
        result = run_cli("state", "set", "current_stage", "committed", cwd=self.repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("STATE_IMMUTABLE_FIELD", result.stderr)
        self.assertIn("state transition", result.stderr)

    def test_unknown_path_rejected(self):
        result = run_cli("state", "set", "codex_review.nope", "x", cwd=self.repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("STATE_UNKNOWN_PATH", result.stderr)


class FullWorkflowWalkthroughTests(unittest.TestCase):
    """Walk a task from planning to completed through the CLI only.

    Proves the state machine, the gates, the fingerprint, and the review
    bundle work together in sequence — not just individually. Runs entirely
    in a throwaway bench fixture; no network, no SSH, no real Frappe.
    """

    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bench = support.make_bench(self.tmp)
        self.app = self.bench / "apps" / "general_trading"

    def cli(self, *args):
        return run_cli(*args, cwd=self.app)

    def assert_ok(self, result, label):
        self.assertEqual(result.returncode, 0, f"{label} failed: {result.stderr}")
        return result

    def test_planning_to_completed(self):
        # 1. Environment detection
        detected = json.loads(self.assert_ok(self.cli("--json", "detect"), "detect").stdout)
        self.assertEqual(detected["app_name"], "general_trading")

        # 2. Project documentation in place and valid
        support.write_fixture_file(
            self.app, project_files.PROJECT_CONTEXT, "sample-project-context.md"
        )
        support.write_fixture_file(
            self.app, project_files.FEATURE_CHANGELOG, "sample-feature-changelog.md"
        )
        self.assert_ok(self.cli("validate", "project-context"), "validate context")
        self.assert_ok(self.cli("validate", "feature-changelog"), "validate changelog")

        # 3. Planning
        self.assert_ok(self.cli("state", "init"), "state init")
        plan_path = support.write_fixture_file(
            self.app, project_files.TASK_PLAN, "sample-task-plan.md"
        )
        self.assert_ok(self.cli("validate", "task-plan"), "validate plan")
        self.assert_ok(self.cli("state", "set", "task_id", "TASK-2026-001"), "set task id")
        self.assert_ok(
            self.cli("state", "set", "target_site", "car.wash"), "set target site"
        )

        # The completion gate must refuse while steps are still Pending.
        self.assert_ok(
            self.cli("state", "transition", "implementation"), "-> implementation"
        )
        early = self.cli("validate", "completion-gate")
        self.assertEqual(early.returncode, 1)
        self.assertIn("GATE_STEP_INCOMPLETE", early.stderr)

        # 4. Implementation: real file changes, steps completed, summary written
        (self.app / "general_trading" / "telegram").mkdir(parents=True)
        (self.app / "general_trading" / "telegram" / "sales_summary.py").write_text(
            "def build_summary(rows):\n    return f'Total: {sum(rows)}'\n", encoding="utf-8"
        )
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "- **Status:** Pending", "- **Status:** Completed"
            ),
            encoding="utf-8",
        )
        support.write_repo_file(
            self.app,
            project_files.IMPLEMENTATION_SUMMARY,
            "# Implementation Summary\n\n## Completed Task\n\nTASK-2026-001\n",
        )
        self.assert_ok(self.cli("validate", "completion-gate"), "completion gate")

        # 5. Review round 1
        bundle = json.loads(self.assert_ok(self.cli("--json", "review", "bundle"), "bundle").stdout)
        self.assertEqual(bundle["round"], 1)
        fingerprint = bundle["fingerprint"]
        self.assert_ok(
            self.cli("state", "set", "codex_review.implementation_fingerprint", fingerprint),
            "record fingerprint",
        )
        self.assert_ok(
            self.cli("state", "set", "codex_review.round", "1", "--json-value"),
            "record round",
        )
        self.assert_ok(self.cli("state", "transition", "codex_review"), "-> codex_review")

        # 6. Codex approves; fingerprint still matches
        result_file = support.write_repo_file(
            self.app,
            f"{project_files.REVIEWS_DIR}/round-001-result.md",
            "# Review Result\n\n- **Status:** APPROVED\n\n"
            "## Verified Items\n\n- All implementation steps match the plan.\n",
        )
        parsed = json.loads(
            self.assert_ok(
                self.cli("review", "parse-result", str(result_file)), "parse result"
            ).stdout
        )
        self.assertEqual(parsed["status"], "APPROVED")
        current = self.assert_ok(self.cli("review", "fingerprint"), "fingerprint").stdout.strip()
        self.assertEqual(current, fingerprint, "approval must match the reviewed state")

        # 7. Finalization: documentation updates do NOT invalidate approval
        self.assert_ok(
            self.cli("state", "set", "codex_review.status", "approved"), "mark approved"
        )
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "status: planned", "status: codex_approved"
            )
            + "\n## Review Result\n\n- **Reviewer:** Codex\n- **Status:** Approved\n"
            "- **Review Round:** 1\n- **Approved At:** 2026-07-27\n",
            encoding="utf-8",
        )
        self.assert_ok(self.cli("validate", "finalization-gate"), "finalization gate")
        self.assert_ok(
            self.cli("state", "transition", "ready_for_commit"), "-> ready_for_commit"
        )

        # 8. A code change after approval invalidates it
        (self.app / "general_trading" / "telegram" / "sales_summary.py").write_text(
            "def build_summary(rows):\n    return 'changed after approval'\n",
            encoding="utf-8",
        )
        invalidated = self.cli("validate", "finalization-gate")
        self.assertEqual(invalidated.returncode, 1)
        self.assertIn("FINAL_FINGERPRINT_MISMATCH", invalidated.stderr)
        self.assert_ok(
            self.cli("state", "transition", "review_fixes", "--reason", "invalidated"),
            "-> review_fixes",
        )

        # 9. Second round, approved, committed (throwaway fixture repo)
        self.assert_ok(self.cli("review", "bundle"), "bundle 2")
        new_fingerprint = self.cli("review", "fingerprint").stdout.strip()
        self.assertNotEqual(new_fingerprint, fingerprint)
        self.assert_ok(
            self.cli("state", "set", "codex_review.implementation_fingerprint", new_fingerprint),
            "record fingerprint 2",
        )
        self.assert_ok(self.cli("state", "transition", "codex_review"), "-> codex_review 2")
        self.assert_ok(self.cli("validate", "finalization-gate"), "finalization gate 2")
        self.assert_ok(
            self.cli("state", "transition", "ready_for_commit"), "-> ready_for_commit 2"
        )

        support.run_git(
            self.app, "add", "--",
            project_files.TASK_PLAN,
            project_files.PROJECT_CONTEXT,
            project_files.FEATURE_CHANGELOG,
            "general_trading/telegram/sales_summary.py",
        )
        support.run_git(
            self.app, "commit", "-q", "-m", "feat(telegram): add scheduled reporting"
        )
        commit_hash = support.run_git(self.app, "rev-parse", "HEAD").strip()
        self.assert_ok(self.cli("state", "set", "commit.status", "created"), "commit status")
        self.assert_ok(self.cli("state", "set", "commit.hash", commit_hash), "commit hash")
        self.assert_ok(
            self.cli("state", "set", "commit.subject", "feat(telegram): add scheduled reporting"),
            "commit subject",
        )
        self.assert_ok(self.cli("state", "transition", "committed"), "-> committed")

        # 10. Deployment skipped, then testing task, then completed
        self.assert_ok(
            self.cli("state", "set", "deployment.required", "false", "--json-value"),
            "deployment required",
        )
        self.assert_ok(self.cli("state", "set", "deployment.status", "skipped"), "skip")
        self.assert_ok(
            self.cli("state", "set", "deployment.skip_reason", "Skipped by user"), "reason"
        )
        self.assert_ok(
            self.cli("state", "transition", "deployment_skipped"), "-> deployment_skipped"
        )
        self.assert_ok(
            self.cli("state", "set", "testing_task.status", "generated"), "testing status"
        )
        self.assert_ok(
            self.cli("state", "set", "testing_task.generated_at", "2026-07-31T13:09:37Z"),
            "testing generated_at",
        )
        # The Arabic testing task is terminal output: there is no path field
        # to record, so setting one is an unknown-path error.
        no_path = self.cli(
            "state", "set", "testing_task.path", "docs/ai-context/testing-task-ar.md"
        )
        self.assertEqual(no_path.returncode, 1, no_path.stdout)
        self.assertIn("STATE_UNKNOWN_PATH", no_path.stderr)
        self.assert_ok(self.cli("state", "transition", "completed"), "-> completed")

        final = json.loads(self.cli("state", "show").stdout)
        self.assertEqual(final["current_stage"], "completed")
        self.assertEqual(final["commit"]["hash"], commit_hash)
        self.assertEqual(final["deployment"]["status"], "skipped")
        self.assertEqual(
            final["testing_task"],
            {"status": "generated", "generated_at": "2026-07-31T13:09:37Z"},
        )
        # Closing the workflow creates no testing-task file anywhere.
        for stale in (
            "docs/ai-context/testing-task-ar.md",
            ".claude/testing-task-ar.md",
        ):
            with self.subTest(stale=stale):
                self.assertFalse((self.app / stale).exists())
        stages = [record["to"] for record in final["transition_history"]]
        self.assertEqual(
            stages,
            [
                "implementation",
                "codex_review",
                "ready_for_commit",
                "review_fixes",
                "codex_review",
                "ready_for_commit",
                "committed",
                "deployment_skipped",
                "completed",
            ],
        )


class StateFileIsIgnoredByFingerprintTests(unittest.TestCase):
    """Regression: CLI state writes must never change the fingerprint."""

    def test_state_write_keeps_fingerprint(self):
        tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = support.init_repo(tmp / "repo", initial_commit=True)
        before = run_cli("git", "fingerprint", cwd=repo).stdout.strip()
        run_cli("state", "init", cwd=repo)
        run_cli("state", "transition", "implementation", cwd=repo)
        after = run_cli("git", "fingerprint", cwd=repo).stdout.strip()
        self.assertEqual(before, after)


class ProjectCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)

    def test_paths_reports_the_centralized_constants(self):
        result = run_cli("project", "paths", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["workflow_state"], project_files.WORKFLOW_STATE)
        self.assertEqual(data["reviews_dir"], project_files.REVIEWS_DIR)
        self.assertEqual(data["deployment_config"], project_files.DEPLOYMENT_CONFIG)
        self.assertEqual(
            data["tracked_shared_files"], list(project_files.TRACKED_SHARED_FILES)
        )

    def test_paths_reports_no_testing_task_file(self):
        """`testing` prints its result, so no path may be advertised."""
        result = run_cli("project", "paths", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("testing", result.stdout)
        data = json.loads(result.stdout)
        self.assertNotIn("testing_task_ar", data)
        for key in ("tracked_shared_files", "reset_paths"):
            with self.subTest(key=key):
                self.assertFalse([p for p in data[key] if "testing-task" in p])

    def test_ensure_gitignore_is_idempotent(self):
        first = run_cli("--json", "project", "ensure-gitignore", cwd=self.repo)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(json.loads(first.stdout)["changed"])
        second = run_cli("--json", "project", "ensure-gitignore", cwd=self.repo)
        self.assertEqual(json.loads(second.stdout)["action"], "unchanged")

    def test_migrate_moves_a_legacy_layout(self):
        support.write_repo_file(self.repo, "TASK_PLAN.md", "# Plan\n")
        support.write_repo_file(self.repo, ".claude/task-workflow.json", "{}\n")
        result = run_cli("--json", "project", "migrate", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(
            sorted(item["to"] for item in data["moved"]),
            sorted([project_files.TASK_PLAN, project_files.WORKFLOW_STATE]),
        )
        self.assertTrue((self.repo / project_files.TASK_PLAN).is_file())
        self.assertFalse((self.repo / "TASK_PLAN.md").exists())

    def test_init_side_commands_never_create_task_state(self):
        """The deterministic half of `init` must not start a task."""
        self.assertEqual(
            run_cli("project", "migrate", cwd=self.repo).returncode, 0
        )
        self.assertEqual(
            run_cli("project", "ensure-gitignore", cwd=self.repo).returncode, 0
        )
        for name in (
            project_files.WORKFLOW_STATE,
            project_files.TASK_PLAN,
            project_files.IMPLEMENTATION_SUMMARY,
        ):
            with self.subTest(name=name):
                self.assertFalse(
                    (self.repo / name).exists(), f"init must not create {name}"
                )
        # Nor may it recreate anything at an old location.
        for old_rel, _ in project_files.LEGACY_PATHS:
            with self.subTest(old=old_rel):
                self.assertFalse((self.repo / old_rel).exists())

    def test_migrate_conflict_exits_1(self):
        support.write_repo_file(self.repo, "TASK_PLAN.md", "old\n")
        support.write_repo_file(self.repo, project_files.TASK_PLAN, "new\n")
        result = run_cli("project", "migrate", cwd=self.repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("MIGRATE_CONFLICT", result.stderr)
        self.assertTrue((self.repo / "TASK_PLAN.md").is_file())


class SharedLayoutTrackingTests(unittest.TestCase):
    """docs/ai-context/ must stay committable, scanned, and fingerprint-free."""

    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)
        run_cli("project", "ensure-gitignore", cwd=self.repo)

    def test_shared_files_are_trackable_and_local_state_is_not(self):
        run_cli("state", "init", cwd=self.repo)
        support.write_fixture_file(
            self.repo, project_files.TASK_PLAN, "sample-task-plan.md"
        )
        support.write_repo_file(
            self.repo, project_files.IMPLEMENTATION_SUMMARY, "# Summary\n"
        )
        support.write_repo_file(
            self.repo, f"{project_files.REVIEWS_DIR}/round-001-prompt.md", "prompt\n"
        )
        support.write_repo_file(
            self.repo, project_files.DEPLOYMENT_CONFIG, '{"demo_server": {}}\n'
        )

        untracked = json.loads(
            run_cli("--json", "git", "changed-files", cwd=self.repo).stdout
        )["untracked"]

        for name in (
            project_files.WORKFLOW_STATE,
            project_files.TASK_PLAN,
            project_files.IMPLEMENTATION_SUMMARY,
            f"{project_files.REVIEWS_DIR}/round-001-prompt.md",
        ):
            with self.subTest(name=name):
                self.assertIn(name, untracked, f"{name} must be visible to Git")

        # Machine-local state stays out of Git entirely.
        self.assertNotIn(project_files.DEPLOYMENT_CONFIG, untracked)
        self.assertNotIn(project_files.WORKFLOW_LOCK, untracked)

    def test_committed_shared_state_survives_a_fresh_clone(self):
        """The cross-device path: commit the branch, clone it, resume there."""
        run_cli("state", "init", cwd=self.repo)
        run_cli("state", "set", "task_id", "TASK-2026-042", cwd=self.repo)
        support.write_fixture_file(
            self.repo, project_files.TASK_PLAN, "sample-task-plan.md"
        )
        support.run_git(self.repo, "add", "--", project_files.AI_CONTEXT_DIR)
        support.run_git(self.repo, "commit", "-q", "-m", "chore: checkpoint task")

        clone = self.tmp / "second-computer"
        support.run_git(self.tmp, "clone", "-q", str(self.repo), str(clone))

        state = json.loads(run_cli("state", "show", cwd=clone).stdout)
        self.assertEqual(state["task_id"], "TASK-2026-042")
        self.assertEqual(run_cli("validate", "task-plan", cwd=clone).returncode, 0)
        # The lock is machine-local, so it never travels with the branch.
        self.assertFalse((clone / project_files.WORKFLOW_LOCK).exists())

    def test_secrets_in_shared_ai_context_files_still_block(self):
        token = support.synthetic_secret("sk_", "live_", "9a8b7c6d", "5e4f3g2h1i0j")
        support.write_repo_file(
            self.repo,
            project_files.IMPLEMENTATION_SUMMARY,
            f'Pasted config: api_key = "{token}"\n',
        )
        result = run_cli("--json", "security", "scan", cwd=self.repo)
        self.assertEqual(result.returncode, 7, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["blocking"], 1)
        self.assertEqual(
            data["findings"][0]["path"], project_files.IMPLEMENTATION_SUMMARY
        )
        self.assertNotIn(token, result.stdout)


class ClipboardCommandTests(unittest.TestCase):
    """Surface-level checks only.

    A real `clipboard copy` would touch the clipboard of whatever machine
    runs the suite, so every platform branch is covered by the mocked unit
    tests instead. What is exercised here is the wiring that cannot reach a
    clipboard: the command exists, and empty input is rejected before any
    detection runs.
    """

    def run_clipboard(self, stdin_text: str, *args: str):
        return subprocess.run(
            [str(CLI), "clipboard", *args],
            input=stdin_text,
            capture_output=True,
            text=True,
            env=support.GIT_ENV,
        )

    def test_command_is_registered(self):
        result = self.run_clipboard("", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("copy", result.stdout)

    def test_empty_stdin_is_invalid_usage(self):
        result = self.run_clipboard("", "copy")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("empty", result.stderr)

    def test_whitespace_only_stdin_is_invalid_usage(self):
        result = self.run_clipboard("  \n\n", "copy")
        self.assertEqual(result.returncode, 2, result.stderr)


if __name__ == "__main__":
    unittest.main()
