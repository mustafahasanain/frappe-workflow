"""Unit tests for scripts/core/git_checks.py."""

import shutil
import unittest

import support
from core import git_checks


class GitInspectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)

    def test_inspect_clean_repo(self):
        info = git_checks.inspect(self.repo)
        self.assertEqual(info["branch"], "main")
        self.assertTrue(info["clean"])
        self.assertEqual(info["changed_files"], [])

    def test_detect_changed_files(self):
        (self.repo / "service.py").write_text("VALUE = 1\n", encoding="utf-8")
        support.run_git(self.repo, "add", "service.py")
        support.run_git(self.repo, "commit", "-q", "-m", "add service")
        (self.repo / "service.py").write_text("VALUE = 2\n", encoding="utf-8")
        self.assertEqual(git_checks.changed_files(self.repo), ["service.py"])

    def test_detect_staged_and_untracked(self):
        (self.repo / "staged.py").write_text("A = 1\n", encoding="utf-8")
        support.run_git(self.repo, "add", "staged.py")
        (self.repo / "loose.py").write_text("B = 2\n", encoding="utf-8")
        self.assertEqual(git_checks.staged_files(self.repo), ["staged.py"])
        self.assertEqual(git_checks.untracked_files(self.repo), ["loose.py"])

    def test_unrelated_staged_files(self):
        (self.repo / "mine.py").write_text("A = 1\n", encoding="utf-8")
        (self.repo / "other.py").write_text("B = 2\n", encoding="utf-8")
        support.run_git(self.repo, "add", "mine.py", "other.py")
        self.assertEqual(
            git_checks.unrelated_staged_files(self.repo, ["mine.py"]), ["other.py"]
        )

    def test_not_a_repo(self):
        outside = self.tmp / "plain"
        outside.mkdir()
        self.assertFalse(git_checks.is_git_repo(outside))
        with self.assertRaises(git_checks.GitError):
            git_checks.inspect(outside)


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = support.init_repo(self.tmp / "repo", initial_commit=True)

    def test_stable_when_unchanged(self):
        first = git_checks.implementation_fingerprint(self.repo)
        second = git_checks.implementation_fingerprint(self.repo)
        self.assertEqual(first, second)

    def test_changes_after_modification(self):
        before = git_checks.implementation_fingerprint(self.repo)
        (self.repo / "new_module.py").write_text("X = 1\n", encoding="utf-8")
        after = git_checks.implementation_fingerprint(self.repo)
        self.assertNotEqual(before, after)

    def test_untracked_content_included(self):
        (self.repo / "new_module.py").write_text("X = 1\n", encoding="utf-8")
        before = git_checks.implementation_fingerprint(self.repo)
        (self.repo / "new_module.py").write_text("X = 2\n", encoding="utf-8")
        after = git_checks.implementation_fingerprint(self.repo)
        self.assertNotEqual(before, after)

    def test_finalization_files_excluded(self):
        (self.repo / "TASK_PLAN.md").write_text("plan v1\n", encoding="utf-8")
        support.run_git(self.repo, "add", "TASK_PLAN.md")
        support.run_git(self.repo, "commit", "-q", "-m", "add plan")
        before = git_checks.implementation_fingerprint(self.repo)
        (self.repo / "TASK_PLAN.md").write_text("plan v2 (finalized)\n", encoding="utf-8")
        (self.repo / "FEATURE_CHANGELOG.md").write_text("# Feature Changelog\n", encoding="utf-8")
        after = git_checks.implementation_fingerprint(self.repo)
        self.assertEqual(before, after)

    def test_hex_sha256_format(self):
        fingerprint = git_checks.implementation_fingerprint(self.repo)
        self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
