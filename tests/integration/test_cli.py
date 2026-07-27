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

        (self.repo / "TASK_PLAN.md").write_text(
            support.read_fixture("sample-task-plan.md"), encoding="utf-8"
        )
        result = run_cli("validate", "task-plan", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_project_context_validation(self):
        (self.repo / "PROJECT_CONTEXT.md").write_text(
            support.read_fixture("sample-project-context.md"), encoding="utf-8"
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
        (self.repo / "FEATURE_CHANGELOG.md").write_text(
            support.read_fixture("sample-feature-changelog.md"), encoding="utf-8"
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
        (self.repo / "TASK_PLAN.md").write_text(
            support.read_fixture("sample-task-plan.md"), encoding="utf-8"
        )
        summary = self.repo / project_files.IMPLEMENTATION_SUMMARY
        summary.parent.mkdir(parents=True)
        summary.write_text("# Implementation Summary\n\nDone.\n", encoding="utf-8")
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
        config_path = self.repo / ".claude" / "deployment.local.json"
        config_path.parent.mkdir(parents=True)
        example = (
            support.PLUGIN_ROOT / "templates/state/deployment.local.json.example"
        ).read_text(encoding="utf-8")
        config_path.write_text(example, encoding="utf-8")

        result = run_cli("deployment", "validate-config", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

        (self.repo / "hooks.py").write_text("app_name = 'x'\n", encoding="utf-8")
        support.run_git(self.repo, "add", "hooks.py")
        result = run_cli("--json", "deployment", "required-commands", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = [item["command"] for item in json.loads(result.stdout)]
        self.assertIn(["bench", "--site", "car.wash", "migrate"], commands)

    def test_verify_matching_and_mismatching_head(self):
        config_path = self.repo / ".claude" / "deployment.local.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            (support.PLUGIN_ROOT / "templates/state/deployment.local.json.example")
            .read_text(encoding="utf-8"),
            encoding="utf-8",
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
        (self.app / "PROJECT_CONTEXT.md").write_text(
            support.read_fixture("sample-project-context.md"), encoding="utf-8"
        )
        (self.app / "FEATURE_CHANGELOG.md").write_text(
            support.read_fixture("sample-feature-changelog.md"), encoding="utf-8"
        )
        self.assert_ok(self.cli("validate", "project-context"), "validate context")
        self.assert_ok(self.cli("validate", "feature-changelog"), "validate changelog")

        # 3. Planning
        self.assert_ok(self.cli("state", "init"), "state init")
        plan_path = self.app / "TASK_PLAN.md"
        plan_path.write_text(support.read_fixture("sample-task-plan.md"), encoding="utf-8")
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
        summary = self.app / project_files.IMPLEMENTATION_SUMMARY
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(
            "# Implementation Summary\n\n## Completed Task\n\nTASK-2026-001\n",
            encoding="utf-8",
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
        result_file = self.app / ".claude" / "reviews" / "round-001-result.md"
        result_file.write_text(
            "# Review Result\n\n- **Status:** APPROVED\n\n"
            "## Verified Items\n\n- All implementation steps match the plan.\n",
            encoding="utf-8",
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

        support.run_git(self.app, "add", "--", "TASK_PLAN.md", "PROJECT_CONTEXT.md",
                        "FEATURE_CHANGELOG.md",
                        "general_trading/telegram/sales_summary.py")
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
        self.assert_ok(self.cli("state", "transition", "completed"), "-> completed")

        final = json.loads(self.cli("state", "show").stdout)
        self.assertEqual(final["current_stage"], "completed")
        self.assertEqual(final["commit"]["hash"], commit_hash)
        self.assertEqual(final["deployment"]["status"], "skipped")
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


if __name__ == "__main__":
    unittest.main()
