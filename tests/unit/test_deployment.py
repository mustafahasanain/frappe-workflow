"""Unit tests for scripts/core/deployment.py. No SSH is ever run here."""

import json
import shutil
import unittest

import support
from core import deployment


def valid_config():
    return {
        "host": "a1-demo",
        "port": 22,
        "ssh_user": "e2next_user",
        "identity_file": None,
        "bench_path": "/home/e2next_user/frappe-bench",
        "app_name": "general_trading",
        "target_site": "car.wash",
        "remote": "upstream",
        "branch": "feature/example",
    }


class ConfigValidationTests(unittest.TestCase):
    def test_valid_config_passes(self):
        self.assertEqual(deployment.validate_config(valid_config()), [])

    def test_example_template_is_valid(self):
        example = json.loads(
            (support.PLUGIN_ROOT / "templates/state/deployment.local.json.example")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(deployment.validate_config(example["demo_server"]), [])

    def test_missing_field(self):
        config = valid_config()
        del config["target_site"]
        errors = deployment.validate_config(config)
        self.assertTrue(any("DEPLOY_FIELD" in e for e in errors))

    def test_invalid_port(self):
        for port in (0, 70000, "22", True):
            config = valid_config()
            config["port"] = port
            errors = deployment.validate_config(config)
            self.assertTrue(any("DEPLOY_PORT" in e for e in errors), f"port={port!r}")

    def test_unsafe_bench_path(self):
        for path in ("relative/path", "/home/../etc"):
            config = valid_config()
            config["bench_path"] = path
            errors = deployment.validate_config(config)
            self.assertTrue(any("DEPLOY_PATH" in e for e in errors), f"path={path!r}")

    def test_unsafe_branch(self):
        config = valid_config()
        config["branch"] = "--upload-pack=/bin/evil"
        errors = deployment.validate_config(config)
        self.assertTrue(any("DEPLOY_BRANCH" in e for e in errors))

    def test_unsafe_host(self):
        config = valid_config()
        config["host"] = "demo; rm -rf /"
        errors = deployment.validate_config(config)
        self.assertTrue(any("DEPLOY_HOST" in e for e in errors))

    def test_stored_credential_rejected(self):
        config = valid_config()
        config["ssh_password"] = "hunter2-example"
        errors = deployment.validate_config(config)
        self.assertTrue(any("DEPLOY_STORED_SECRET" in e for e in errors))


class TaskConsistencyTests(unittest.TestCase):
    def test_matching_task(self):
        state = {
            "app_name": "general_trading",
            "branch": "feature/example",
            "commit": {"status": "created", "hash": "abc"},
        }
        self.assertEqual(deployment.check_task_consistency(valid_config(), state), [])

    def test_branch_mismatch(self):
        state = {
            "app_name": "general_trading",
            "branch": "feature/other",
            "commit": {"status": "created", "hash": "abc"},
        }
        errors = deployment.check_task_consistency(valid_config(), state)
        self.assertTrue(any("DEPLOY_BRANCH_MISMATCH" in e for e in errors))

    def test_no_commit(self):
        state = {
            "app_name": "general_trading",
            "branch": "feature/example",
            "commit": {"status": "not_created", "hash": None},
        }
        errors = deployment.check_task_consistency(valid_config(), state)
        self.assertTrue(any("DEPLOY_NO_COMMIT" in e for e in errors))


class SshCommandTests(unittest.TestCase):
    def test_argv_array_with_quoting(self):
        command = deployment.build_ssh_command(
            valid_config(), ["git", "-C", "/path with space/repo", "status"]
        )
        self.assertEqual(command[0], "ssh")
        self.assertIn("--", command)
        self.assertIn("e2next_user@a1-demo", command)
        self.assertIn("'/path with space/repo'", command[-1])

    def test_invalid_config_refused(self):
        config = valid_config()
        config["host"] = "bad host"
        with self.assertRaises(deployment.DeploymentError):
            deployment.build_ssh_command(config, ["true"])

    def test_remote_git_commands_ff_only(self):
        commands = deployment.remote_git_commands(valid_config())
        self.assertIn("--ff-only", commands["pull"])
        self.assertIn("merge-base", commands["ff_possible"])


class RemotePreflightTests(unittest.TestCase):
    def test_clean_remote_passes(self):
        errors = deployment.evaluate_remote_preflight(
            valid_config(),
            expected_commit="abc1234",
            status_output="",
            branch_output="feature/example\n",
            remote_head_output="abc1234def5678\n",
            ff_exit_code=0,
        )
        self.assertEqual(errors, [])

    def test_dirty_remote_detected(self):
        errors = deployment.evaluate_remote_preflight(
            valid_config(),
            expected_commit="abc1234",
            status_output=" M apps/general_trading/hooks.py\n",
            branch_output="feature/example",
            remote_head_output="abc1234",
            ff_exit_code=0,
        )
        self.assertTrue(any("PREFLIGHT_DIRTY" in e for e in errors))

    def test_branch_mismatch_detected(self):
        errors = deployment.evaluate_remote_preflight(
            valid_config(),
            expected_commit="abc1234",
            status_output="",
            branch_output="develop",
            remote_head_output="abc1234",
            ff_exit_code=0,
        )
        self.assertTrue(any("PREFLIGHT_BRANCH" in e for e in errors))

    def test_diverged_history_detected(self):
        errors = deployment.evaluate_remote_preflight(
            valid_config(),
            expected_commit="abc1234",
            status_output="",
            branch_output="feature/example",
            remote_head_output="abc1234",
            ff_exit_code=1,
        )
        self.assertTrue(any("PREFLIGHT_NO_FF" in e for e in errors))

    def test_commit_mismatch_detected(self):
        errors = deployment.evaluate_remote_preflight(
            valid_config(),
            expected_commit="abc1234",
            status_output="",
            branch_output="feature/example",
            remote_head_output="fff9999",
            ff_exit_code=0,
        )
        self.assertTrue(any("PREFLIGHT_COMMIT_MISMATCH" in e for e in errors))


class CommandMatrixTests(unittest.TestCase):
    def commands_for(self, paths):
        return [
            item["command"]
            for item in deployment.required_frappe_commands(
                paths, "general_trading", "car.wash"
            )
        ]

    def test_doctype_json_requires_migrate(self):
        commands = self.commands_for(
            ["general_trading/doctype/reservation/reservation.json"]
        )
        self.assertIn(["bench", "--site", "car.wash", "migrate"], commands)

    def test_frontend_requires_build(self):
        commands = self.commands_for(["general_trading/public/js/sales.js"])
        self.assertIn(["bench", "build", "--app", "general_trading"], commands)
        self.assertNotIn(["bench", "--site", "car.wash", "migrate"], commands)

    def test_python_requires_restart(self):
        commands = self.commands_for(["general_trading/service.py"])
        self.assertIn(["bench", "restart"], commands)

    def test_hooks_requires_migrate_and_restart(self):
        commands = self.commands_for(["general_trading/hooks.py"])
        self.assertIn(["bench", "--site", "car.wash", "migrate"], commands)
        self.assertIn(["bench", "restart"], commands)

    def test_docs_require_nothing(self):
        self.assertEqual(self.commands_for(["README.md", "TASK_PLAN.md"]), [])


class VerificationTests(unittest.TestCase):
    def test_matching_head(self):
        self.assertIsNone(deployment.verify_deployment("abc1234", "abc1234def567\n"))

    def test_mismatched_head(self):
        error = deployment.verify_deployment("abc1234", "fff8888")
        self.assertIn("VERIFY_MISMATCH", error)

    def test_empty_head(self):
        error = deployment.verify_deployment("abc1234", "")
        self.assertIn("VERIFY_NO_HEAD", error)


class ConfigLoadingTests(unittest.TestCase):
    def setUp(self):
        self.repo = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.repo, True)

    def test_missing_config_reported(self):
        with self.assertRaises(deployment.DeploymentError) as ctx:
            deployment.load_config(self.repo)
        self.assertIn("DEPLOY_NO_CONFIG", str(ctx.exception))

    def test_load_valid_config(self):
        path = self.repo / ".claude" / "deployment.local.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({"demo_server": valid_config()}), encoding="utf-8"
        )
        config = deployment.load_config(self.repo)
        self.assertEqual(config["host"], "a1-demo")


if __name__ == "__main__":
    unittest.main()
