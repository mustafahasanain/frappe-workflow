"""Unit tests for scripts/core/workflow_state.py."""

import json
import shutil
import unittest

import support
from core import project_files, workflow_state


class StateLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.repo = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.repo, True)

    def test_init_creates_valid_state(self):
        state = workflow_state.init_state(self.repo)
        self.assertEqual(state["current_stage"], "planning")
        loaded = workflow_state.load_state(self.repo)
        self.assertEqual(loaded["schema_version"], workflow_state.SCHEMA_VERSION)

    def test_init_refuses_overwrite(self):
        workflow_state.init_state(self.repo)
        with self.assertRaises(workflow_state.StateError):
            workflow_state.init_state(self.repo)
        # force is the controlled-reset path
        workflow_state.init_state(self.repo, overwrite=True)

    def test_state_lives_in_the_shared_ai_context_directory(self):
        workflow_state.init_state(self.repo)
        path = workflow_state.state_path(self.repo)
        self.assertEqual(
            path.relative_to(self.repo).as_posix(), project_files.WORKFLOW_STATE
        )
        self.assertTrue(path.is_file())

    def test_lock_stays_machine_local(self):
        workflow_state.init_state(self.repo)
        lock = workflow_state.lock_path(self.repo)
        self.assertEqual(
            lock.relative_to(self.repo).as_posix(), project_files.WORKFLOW_LOCK
        )
        # The lock must never be written next to the shared state file.
        self.assertNotIn(
            project_files.AI_CONTEXT_DIR, lock.relative_to(self.repo).as_posix()
        )

    def test_atomic_write_leaves_no_temp_files(self):
        workflow_state.init_state(self.repo)
        workflow_state.transition(self.repo, "implementation")
        for directory in (
            workflow_state.state_path(self.repo).parent,
            workflow_state.lock_path(self.repo).parent,
        ):
            leftovers = sorted(
                p.name for p in directory.iterdir() if p.name.endswith(".tmp")
            )
            self.assertEqual(leftovers, [], f"temp files left in {directory}")

    def test_save_rejects_invalid_state(self):
        state = workflow_state.default_state()
        state["current_stage"] = "nonsense"
        with self.assertRaises(workflow_state.StateError):
            workflow_state.save_state(self.repo, state)
        self.assertFalse(workflow_state.state_path(self.repo).exists())

    def test_load_rejects_corrupt_json(self):
        path = workflow_state.state_path(self.repo)
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(workflow_state.StateError):
            workflow_state.load_state(self.repo)

    def test_load_rejects_unsupported_schema(self):
        state = workflow_state.default_state()
        workflow_state.save_state(self.repo, state)
        raw = json.loads(workflow_state.state_path(self.repo).read_text(encoding="utf-8"))
        raw["schema_version"] = 99
        workflow_state.state_path(self.repo).write_text(
            json.dumps(raw), encoding="utf-8"
        )
        with self.assertRaises(workflow_state.StateError) as ctx:
            workflow_state.load_state(self.repo)
        self.assertIn("STATE_SCHEMA_VERSION", str(ctx.exception))

    def test_preserves_data_across_saves(self):
        state = workflow_state.init_state(self.repo)
        state["task_title"] = "Add Telegram reporting"
        workflow_state.save_state(self.repo, state)
        loaded = workflow_state.load_state(self.repo)
        self.assertEqual(loaded["task_title"], "Add Telegram reporting")


class TestingTaskSectionTests(unittest.TestCase):
    """The testing task is printed, not saved — the state reflects that."""

    def setUp(self):
        self.repo = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.repo, True)

    def test_default_state_tracks_only_status_and_timestamp(self):
        section = workflow_state.default_state()["testing_task"]
        self.assertEqual(sorted(section), ["generated_at", "status"])
        self.assertEqual(section["status"], "pending")
        self.assertIsNone(section["generated_at"])

    def test_new_state_file_has_no_testing_task_path(self):
        workflow_state.init_state(self.repo)
        raw = workflow_state.state_path(self.repo).read_text(encoding="utf-8")
        self.assertNotIn("testing-task-ar", raw)
        self.assertNotIn(
            "path", json.loads(raw)["testing_task"]
        )

    def test_state_template_matches_the_default_state(self):
        template = json.loads(
            (support.PLUGIN_ROOT / "templates/state/task-workflow.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            template["testing_task"],
            {"status": "pending", "generated_at": None},
        )

    def test_generated_status_and_timestamp_are_recorded(self):
        workflow_state.init_state(self.repo)
        workflow_state.set_field(self.repo, "testing_task.status", "generated")
        state = workflow_state.set_field(
            self.repo, "testing_task.generated_at", "2026-07-31T13:09:37Z"
        )
        self.assertEqual(
            state["testing_task"],
            {"status": "generated", "generated_at": "2026-07-31T13:09:37Z"},
        )
        self.assertEqual(
            workflow_state.load_state(self.repo)["testing_task"]["generated_at"],
            "2026-07-31T13:09:37Z",
        )

    def test_setting_a_testing_task_path_is_rejected_on_a_new_state(self):
        workflow_state.init_state(self.repo)
        with self.assertRaises(workflow_state.StateError) as ctx:
            workflow_state.set_field(
                self.repo, "testing_task.path", "docs/ai-context/testing-task-ar.md"
            )
        self.assertIn("STATE_UNKNOWN_PATH", str(ctx.exception))

    def test_legacy_state_with_a_testing_task_path_still_loads(self):
        """Backward compatibility: an old state file must not break."""
        legacy = workflow_state.default_state()
        legacy["testing_task"] = {
            "status": "generated",
            "path": "docs/ai-context/testing-task-ar.md",
            "generated_at": "2026-07-01T10:00:00Z",
        }
        self.assertEqual(workflow_state.validate_state(legacy), [])

        workflow_state.save_state(self.repo, legacy)
        loaded = workflow_state.load_state(self.repo)
        self.assertEqual(loaded["testing_task"]["status"], "generated")
        # The obsolete key is carried along untouched, never acted on.
        self.assertEqual(
            loaded["testing_task"]["path"], "docs/ai-context/testing-task-ar.md"
        )

    def test_legacy_state_keeps_working_through_a_transition(self):
        legacy = workflow_state.default_state()
        legacy["testing_task"]["path"] = "docs/ai-context/testing-task-ar.md"
        legacy["commit"] = {"status": "created", "hash": "abc1234", "subject": "feat: x"}
        legacy["deployment"]["status"] = "skipped"
        legacy["current_stage"] = "deployment_skipped"
        workflow_state.save_state(self.repo, legacy)

        state = workflow_state.set_field(self.repo, "testing_task.status", "generated")
        self.assertEqual(state["testing_task"]["status"], "generated")
        state = workflow_state.transition(self.repo, "completed")
        self.assertEqual(state["current_stage"], "completed")
        self.assertEqual(
            state["testing_task"]["path"], "docs/ai-context/testing-task-ar.md"
        )


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.repo = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.repo, True)
        workflow_state.init_state(self.repo)

    def test_valid_transition(self):
        state = workflow_state.transition(self.repo, "implementation", reason="plan accepted")
        self.assertEqual(state["current_stage"], "implementation")
        self.assertEqual(state["transition_history"][-1]["from"], "planning")
        self.assertEqual(state["transition_history"][-1]["reason"], "plan accepted")

    def test_invalid_transition_rejected(self):
        with self.assertRaises(workflow_state.TransitionError):
            workflow_state.transition(self.repo, "committed")
        # state unchanged on rejection
        self.assertEqual(
            workflow_state.load_state(self.repo)["current_stage"], "planning"
        )

    def test_unknown_stage_rejected(self):
        with self.assertRaises(workflow_state.TransitionError):
            workflow_state.transition(self.repo, "shipping")

    def test_self_transition_only_where_allowed(self):
        workflow_state.transition(self.repo, "implementation")
        workflow_state.transition(self.repo, "implementation")  # allowed
        with self.assertRaises(workflow_state.TransitionError):
            # planning has no self-transition; force stage back first
            state = workflow_state.load_state(self.repo)
            state["current_stage"] = "planning"
            workflow_state.save_state(self.repo, state)
            workflow_state.transition(self.repo, "planning")

    def test_full_happy_path(self):
        commit_stage_updates = {
            "commit": {"status": "created", "hash": "abc1234", "subject": "feat: x"},
        }
        path = [
            "implementation",
            "codex_review",
            "review_fixes",
            "codex_review",
            "ready_for_commit",
            "committed",
            "deployed",
            "completed",
        ]
        for stage in path:
            if stage == "committed":
                state = workflow_state.load_state(self.repo)
                state.update(commit_stage_updates)
                workflow_state.save_state(self.repo, state)
            if stage == "deployed":
                state = workflow_state.load_state(self.repo)
                state["deployment"]["status"] = "deployed"
                workflow_state.save_state(self.repo, state)
            state = workflow_state.transition(self.repo, stage)
            self.assertEqual(state["current_stage"], stage)

    def test_completed_is_terminal(self):
        state = workflow_state.load_state(self.repo)
        state["current_stage"] = "completed"
        state["commit"] = {"status": "created", "hash": "abc", "subject": "s"}
        workflow_state.save_state(self.repo, state)
        with self.assertRaises(workflow_state.TransitionError):
            workflow_state.transition(self.repo, "planning")


class BlockerTests(unittest.TestCase):
    def setUp(self):
        self.repo = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.repo, True)
        workflow_state.init_state(self.repo)

    def test_add_and_clear_blockers(self):
        workflow_state.add_blocker(self.repo, "step 2: migrate failed: missing column")
        state = workflow_state.load_state(self.repo)
        self.assertEqual(len(state["blockers"]), 1)
        self.assertIn("migrate failed", state["blockers"][0]["message"])
        workflow_state.clear_blockers(self.repo)
        self.assertEqual(workflow_state.load_state(self.repo)["blockers"], [])


class SetFieldTests(unittest.TestCase):
    def setUp(self):
        self.repo = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.repo, True)
        workflow_state.init_state(self.repo)

    def test_set_nested_field(self):
        workflow_state.set_field(self.repo, "codex_review.status", "approved")
        state = workflow_state.load_state(self.repo)
        self.assertEqual(state["codex_review"]["status"], "approved")

    def test_set_top_level_field(self):
        workflow_state.set_field(self.repo, "task_id", "TASK-2026-004")
        self.assertEqual(
            workflow_state.load_state(self.repo)["task_id"], "TASK-2026-004"
        )

    def test_set_typed_value(self):
        workflow_state.set_field(self.repo, "codex_review.round", 3)
        self.assertEqual(
            workflow_state.load_state(self.repo)["codex_review"]["round"], 3
        )

    def test_unknown_path_rejected(self):
        with self.assertRaises(workflow_state.StateError) as ctx:
            workflow_state.set_field(self.repo, "codex_review.reviewer_name", "Codex")
        self.assertIn("STATE_UNKNOWN_PATH", str(ctx.exception))

    def test_typo_in_parent_rejected(self):
        with self.assertRaises(workflow_state.StateError):
            workflow_state.set_field(self.repo, "codexreview.status", "approved")

    def test_immutable_paths_rejected(self):
        for path in (
            "current_stage",
            "schema_version",
            "blockers",
            "transition_history",
        ):
            with self.subTest(path=path):
                with self.assertRaises(workflow_state.StateError) as ctx:
                    workflow_state.set_field(self.repo, path, "x")
                self.assertIn("STATE_IMMUTABLE_FIELD", str(ctx.exception))

    def test_invalid_resulting_state_rejected(self):
        with self.assertRaises(workflow_state.StateError):
            workflow_state.set_field(self.repo, "task_plan_status", "not-a-status")
        # original value preserved
        self.assertEqual(
            workflow_state.load_state(self.repo)["task_plan_status"], "not_created"
        )


class ConsistencyValidationTests(unittest.TestCase):
    def test_committed_stage_requires_created_commit(self):
        state = workflow_state.default_state()
        state["current_stage"] = "committed"
        errors = workflow_state.validate_state(state)
        self.assertTrue(any("STATE_STAGE_COMMIT_MISMATCH" in e for e in errors))

    def test_deployed_stage_requires_deployed_status(self):
        state = workflow_state.default_state()
        state["current_stage"] = "deployed"
        state["commit"] = {"status": "created", "hash": "abc", "subject": "s"}
        errors = workflow_state.validate_state(state)
        self.assertTrue(any("STATE_STAGE_DEPLOY_MISMATCH" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
