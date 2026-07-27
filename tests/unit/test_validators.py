"""Unit tests for scripts/core/validators.py."""

import shutil
import unittest

import support
from core import git_checks, project_files, validators, workflow_state


class ProjectContextValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = self.tmp / "PROJECT_CONTEXT.md"

    def test_valid_fixture_passes(self):
        self.path.write_text(
            support.read_fixture("sample-project-context.md"), encoding="utf-8"
        )
        self.assertEqual(validators.validate_project_context(self.path), [])

    def test_missing_file(self):
        errors = validators.validate_project_context(self.path)
        self.assertTrue(any("CTX_MISSING" in e for e in errors))

    def test_missing_section_detected(self):
        text = support.read_fixture("sample-project-context.md").replace(
            "# Navigation Map", "# Some Other Heading"
        )
        self.path.write_text(text, encoding="utf-8")
        errors = validators.validate_project_context(self.path)
        self.assertTrue(any("CTX_SECTION" in e and "Navigation Map" in e for e in errors))

    def test_missing_frontmatter_key(self):
        text = support.read_fixture("sample-project-context.md").replace(
            "analyzed_commit: 2f08f96\n", ""
        )
        self.path.write_text(text, encoding="utf-8")
        errors = validators.validate_project_context(self.path)
        self.assertTrue(any("CTX_FRONTMATTER_KEY" in e for e in errors))

    def test_bad_commit_format(self):
        text = support.read_fixture("sample-project-context.md").replace(
            "analyzed_commit: 2f08f96", "analyzed_commit: not-a-hash"
        )
        self.path.write_text(text, encoding="utf-8")
        errors = validators.validate_project_context(self.path)
        self.assertTrue(any("CTX_COMMIT_FORMAT" in e for e in errors))


class TaskPlanValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = self.tmp / "TASK_PLAN.md"

    def write(self, text):
        self.path.write_text(text, encoding="utf-8")

    def test_valid_fixture_passes(self):
        self.write(support.read_fixture("sample-task-plan.md"))
        self.assertEqual(validators.validate_task_plan(self.path), [])

    def test_invalid_task_type(self):
        self.write(
            support.read_fixture("sample-task-plan.md").replace(
                "task_type: integration", "task_type: epic"
            )
        )
        errors = validators.validate_task_plan(self.path)
        self.assertTrue(any("PLAN_TASK_TYPE" in e for e in errors))

    def test_invalid_step_status(self):
        self.write(
            support.read_fixture("sample-task-plan.md").replace(
                "- **Status:** Pending\n- **Action:** Create the sales summary",
                "- **Status:** Done\n- **Action:** Create the sales summary",
            )
        )
        errors = validators.validate_task_plan(self.path)
        self.assertTrue(any("PLAN_STEP_STATUS" in e for e in errors))

    def test_step_missing_validation_field(self):
        self.write(
            support.read_fixture("sample-task-plan.md").replace(
                "- **Validation:** Unit test with two fixture invoices asserts the total line.\n",
                "",
            )
        )
        errors = validators.validate_task_plan(self.path)
        self.assertTrue(any("PLAN_STEP_FIELD" in e and "Validation" in e for e in errors))

    def test_missing_section(self):
        self.write(
            support.read_fixture("sample-task-plan.md").replace(
                "## Acceptance Criteria", "## Acceptance Thoughts"
            )
        )
        errors = validators.validate_task_plan(self.path)
        self.assertTrue(any("PLAN_SECTION" in e and "Acceptance Criteria" in e for e in errors))

    def test_bad_task_id(self):
        self.write(
            support.read_fixture("sample-task-plan.md").replace(
                "task_id: TASK-2026-001", "task_id: T-1"
            )
        )
        errors = validators.validate_task_plan(self.path)
        self.assertTrue(any("PLAN_TASK_ID" in e for e in errors))

    def test_blocked_step_requires_blocker(self):
        self.write(
            support.read_fixture("sample-task-plan.md").replace(
                "- **Status:** Pending\n- **Action:** Register a daily scheduler",
                "- **Status:** Blocked\n- **Action:** Register a daily scheduler",
            )
        )
        errors = validators.validate_task_plan(self.path)
        self.assertTrue(any("PLAN_STEP_BLOCKER" in e for e in errors))


class WorkflowStateValidatorTests(unittest.TestCase):
    def setUp(self):
        self.repo = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.repo, True)

    def test_missing_state_reported(self):
        errors = validators.validate_workflow_state(self.repo)
        self.assertTrue(any("STATE_MISSING" in e for e in errors))

    def test_valid_state_passes(self):
        workflow_state.init_state(self.repo)
        self.assertEqual(validators.validate_workflow_state(self.repo), [])


class CompletionGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)
        workflow_state.init_state(self.repo)
        plan = support.read_fixture("sample-task-plan.md").replace(
            "- **Status:** Pending", "- **Status:** Completed"
        )
        (self.repo / "TASK_PLAN.md").write_text(plan, encoding="utf-8")
        summary = self.repo / project_files.IMPLEMENTATION_SUMMARY
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text("# Implementation Summary\n\nAll steps done.\n", encoding="utf-8")
        # completion gate expects the implementation stage
        workflow_state.transition(self.repo, "implementation")

    def test_gate_passes_when_all_complete(self):
        self.assertEqual(validators.validate_completion_gate(self.repo), [])

    def test_gate_fails_on_pending_step(self):
        plan = (self.repo / "TASK_PLAN.md").read_text(encoding="utf-8")
        plan = plan.replace(
            "- **Status:** Completed\n- **Action:** Create the sales summary",
            "- **Status:** Pending\n- **Action:** Create the sales summary",
        )
        (self.repo / "TASK_PLAN.md").write_text(plan, encoding="utf-8")
        errors = validators.validate_completion_gate(self.repo)
        self.assertTrue(any("GATE_STEP_INCOMPLETE" in e for e in errors))

    def test_gate_fails_on_blockers(self):
        workflow_state.add_blocker(self.repo, "step 2 blocked: fixture reason")
        errors = validators.validate_completion_gate(self.repo)
        self.assertTrue(any("GATE_BLOCKERS" in e for e in errors))

    def test_gate_fails_on_missing_summary(self):
        (self.repo / project_files.IMPLEMENTATION_SUMMARY).unlink()
        errors = validators.validate_completion_gate(self.repo)
        self.assertTrue(any("GATE_NO_SUMMARY" in e for e in errors))

    def test_gate_fails_on_wrong_stage(self):
        state = workflow_state.load_state(self.repo)
        state["current_stage"] = "planning"
        workflow_state.save_state(self.repo, state)
        errors = validators.validate_completion_gate(self.repo)
        self.assertTrue(any("GATE_WRONG_STAGE" in e for e in errors))

    def test_gate_fails_on_secret_in_untracked_file(self):
        token = support.synthetic_secret("sk_", "live_", "9a8b7c6d", "5e4f3g2h1i0j")
        (self.repo / "config_leak.py").write_text(
            f'api_key = "{token}"\n', encoding="utf-8"
        )
        errors = validators.validate_completion_gate(self.repo)
        self.assertTrue(any("GATE_SECRET" in e for e in errors))


class FinalizationGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)
        workflow_state.init_state(self.repo)
        self.plan_text = (
            support.read_fixture("sample-task-plan.md")
            .replace("- **Status:** Pending", "- **Status:** Completed")
            .replace("status: planned", "status: codex_approved")
        )
        (self.repo / "TASK_PLAN.md").write_text(self.plan_text, encoding="utf-8")
        self._advance_to("codex_review")

    def _advance_to(self, stage):
        """Walk the real transition table up to *stage*."""
        path = ["implementation", "codex_review", "ready_for_commit"]
        for step in path:
            workflow_state.transition(self.repo, step)
            if step == stage:
                return
        raise AssertionError(f"no transition path to {stage!r}")

    def _approve_current_state(self, repo=None):
        repo = repo or self.repo
        state = workflow_state.load_state(repo)
        state["codex_review"]["status"] = "approved"
        state["codex_review"]["implementation_fingerprint"] = (
            git_checks.implementation_fingerprint(repo)
            if git_checks.is_git_repo(repo)
            else "0" * 64
        )
        workflow_state.save_state(repo, state)

    # -- accepted states ---------------------------------------------------

    def test_gate_passes_in_codex_review(self):
        self._approve_current_state()
        self.assertEqual(validators.validate_finalization_gate(self.repo), [])

    def test_gate_passes_in_ready_for_commit(self):
        self._approve_current_state()
        workflow_state.transition(self.repo, "ready_for_commit")
        self._approve_current_state()  # refresh fingerprint after state write
        self.assertEqual(validators.validate_finalization_gate(self.repo), [])

    # -- stage ------------------------------------------------------------

    def test_gate_fails_on_wrong_stage(self):
        for stage in ("planning", "implementation", "review_fixes"):
            with self.subTest(stage=stage):
                repo = support.init_repo(
                    self.tmp / f"stage-{stage}", initial_commit=True
                )
                workflow_state.init_state(repo)
                (repo / "TASK_PLAN.md").write_text(self.plan_text, encoding="utf-8")
                if stage == "implementation":
                    workflow_state.transition(repo, "implementation")
                elif stage == "review_fixes":
                    workflow_state.transition(repo, "implementation")
                    workflow_state.transition(repo, "codex_review")
                    workflow_state.transition(repo, "review_fixes")
                self._approve_current_state(repo)
                errors = validators.validate_finalization_gate(repo)
                self.assertTrue(
                    any("FINAL_WRONG_STAGE" in e for e in errors),
                    f"stage {stage!r} should be rejected; got {errors}",
                )
                self.assertTrue(any(repr(stage) in e for e in errors))

    # -- Git --------------------------------------------------------------

    def test_gate_fails_when_not_a_git_repository(self):
        plain = self.tmp / "not-a-repo"
        plain.mkdir()
        workflow_state.init_state(plain)
        (plain / "TASK_PLAN.md").write_text(self.plan_text, encoding="utf-8")
        workflow_state.transition(plain, "implementation")
        workflow_state.transition(plain, "codex_review")
        self._approve_current_state(plain)

        self.assertFalse(git_checks.is_git_repo(plain))
        errors = validators.validate_finalization_gate(plain)
        self.assertTrue(
            any("FINAL_NO_GIT" in e for e in errors),
            f"non-Git target must be rejected; got {errors}",
        )

    # -- task plan --------------------------------------------------------

    def test_gate_fails_on_missing_plan(self):
        self._approve_current_state()
        (self.repo / "TASK_PLAN.md").unlink()
        self._approve_current_state()  # fingerprint changed by the deletion
        errors = validators.validate_finalization_gate(self.repo)
        self.assertTrue(any("FINAL_NO_PLAN" in e for e in errors))

    def test_gate_fails_on_plan_without_frontmatter(self):
        body = self.plan_text.split("---", 2)[2]
        (self.repo / "TASK_PLAN.md").write_text(body, encoding="utf-8")
        self._approve_current_state()
        errors = validators.validate_finalization_gate(self.repo)
        self.assertTrue(any("PLAN_NO_FRONTMATTER" in e for e in errors))
        self.assertTrue(
            any("FINAL_PLAN_INVALID" in e for e in errors),
            f"malformed plan must fail the gate; got {errors}",
        )

    def test_gate_fails_on_plan_missing_required_section(self):
        (self.repo / "TASK_PLAN.md").write_text(
            self.plan_text.replace("## Acceptance Criteria", "## Acceptance Notes"),
            encoding="utf-8",
        )
        self._approve_current_state()
        errors = validators.validate_finalization_gate(self.repo)
        self.assertTrue(any("PLAN_SECTION" in e for e in errors))
        self.assertTrue(any("FINAL_PLAN_INVALID" in e for e in errors))

    def test_gate_fails_on_plan_with_invalid_step_status(self):
        (self.repo / "TASK_PLAN.md").write_text(
            self.plan_text.replace(
                "- **Status:** Completed\n- **Action:** Create the sales summary",
                "- **Status:** Done\n- **Action:** Create the sales summary",
            ),
            encoding="utf-8",
        )
        self._approve_current_state()
        errors = validators.validate_finalization_gate(self.repo)
        self.assertTrue(any("PLAN_STEP_STATUS" in e for e in errors))
        self.assertTrue(any("FINAL_PLAN_INVALID" in e for e in errors))

    def test_gate_fails_on_wrong_plan_status(self):
        (self.repo / "TASK_PLAN.md").write_text(
            self.plan_text.replace("status: codex_approved", "status: in_progress"),
            encoding="utf-8",
        )
        self._approve_current_state()
        errors = validators.validate_finalization_gate(self.repo)
        self.assertTrue(any("FINAL_PLAN_STATUS" in e for e in errors))
        # A merely-wrong status is still a structurally valid plan.
        self.assertFalse(any("FINAL_PLAN_INVALID" in e for e in errors))

    # -- approval and fingerprint -----------------------------------------

    def test_gate_fails_without_approval(self):
        errors = validators.validate_finalization_gate(self.repo)
        self.assertTrue(any("FINAL_NOT_APPROVED" in e for e in errors))

    def test_gate_fails_without_recorded_fingerprint(self):
        state = workflow_state.load_state(self.repo)
        state["codex_review"]["status"] = "approved"
        workflow_state.save_state(self.repo, state)
        errors = validators.validate_finalization_gate(self.repo)
        self.assertTrue(any("FINAL_NO_FINGERPRINT" in e for e in errors))

    def test_gate_fails_on_fingerprint_mismatch(self):
        self._approve_current_state()
        (self.repo / "sneaky_change.py").write_text("X = 1\n", encoding="utf-8")
        errors = validators.validate_finalization_gate(self.repo)
        self.assertTrue(any("FINAL_FINGERPRINT_MISMATCH" in e for e in errors))

    def test_documentation_finalization_keeps_approval(self):
        self._approve_current_state()
        (self.repo / "FEATURE_CHANGELOG.md").write_text(
            "# Feature Changelog\n\n## Feature Index\n", encoding="utf-8"
        )
        errors = validators.validate_finalization_gate(self.repo)
        self.assertFalse(any("FINAL_FINGERPRINT_MISMATCH" in e for e in errors))

    # -- secrets ----------------------------------------------------------

    def test_gate_fails_on_secret(self):
        token = support.synthetic_secret("sk_", "live_", "9a8b7c6d", "5e4f3g2h1i0j")
        (self.repo / "leak.py").write_text(f'api_key = "{token}"\n', encoding="utf-8")
        self._approve_current_state()
        errors = validators.validate_finalization_gate(self.repo)
        self.assertTrue(any("FINAL_SECRET" in e for e in errors))
        self.assertFalse(any(token in e for e in errors))  # redacted


if __name__ == "__main__":
    unittest.main()
