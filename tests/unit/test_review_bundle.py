"""Unit tests for scripts/core/review_bundle.py."""

import shutil
import unittest

import support
from core import project_files, review_bundle


def make_review_repo(tmp):
    repo = support.init_repo(tmp / "repo", initial_commit=True)
    support.write_fixture_file(repo, project_files.TASK_PLAN, "sample-task-plan.md")
    support.write_repo_file(
        repo,
        project_files.IMPLEMENTATION_SUMMARY,
        "# Implementation Summary\n\nDone.\n",
    )
    (repo / "sales_summary.py").write_text("TOTAL = 0\n", encoding="utf-8")
    return repo


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = make_review_repo(self.tmp)

    def test_bundle_contains_required_sections(self):
        result = review_bundle.create_bundle(self.repo)
        prompt = (self.repo / result["prompt_path"]).read_text(encoding="utf-8")
        for heading in (
            "## Task Plan",
            "## Implementation Summary",
            "## Git Status",
            "## Changed Files",
            "## Untracked Files",
            "## Diff (working tree vs HEAD)",
            "## Staged Diff",
        ):
            self.assertIn(heading, prompt)
        self.assertIn("Do NOT modify any repository file", prompt)
        self.assertIn(result["fingerprint"], prompt)
        self.assertIn("TASK-2026-001", prompt)

    def test_round_numbers_increment(self):
        first = review_bundle.create_bundle(self.repo)
        second = review_bundle.create_bundle(self.repo)
        self.assertEqual(first["round"], 1)
        self.assertEqual(second["round"], 2)
        reviews = self.repo / project_files.REVIEWS_DIR
        self.assertTrue((reviews / "round-001-prompt.md").is_file())
        self.assertTrue((reviews / "round-002-prompt.md").is_file())

    def test_round_counts_results_too(self):
        directory = review_bundle.reviews_dir(self.repo)
        directory.mkdir(parents=True)
        (directory / "round-003-result.md").write_text("old\n", encoding="utf-8")
        result = review_bundle.create_bundle(self.repo)
        self.assertEqual(result["round"], 4)

    def test_bundle_blocks_on_secret(self):
        # Assembled at runtime so this file holds no credential-shaped literal.
        token = support.synthetic_secret(
            "8123456789", ":", "AAHrealLookingTokenValue1234567890x"
        )
        (self.repo / "leak.py").write_text(
            f'bot_token = "{token}"\n', encoding="utf-8"
        )
        with self.assertRaises(review_bundle.ReviewError) as ctx:
            review_bundle.create_bundle(self.repo)
        message = str(ctx.exception)
        self.assertIn("secret", message.lower())
        self.assertNotIn(token, message)  # redacted

    def test_fingerprint_recorded_matches_cli(self):
        from core import git_checks

        result = review_bundle.create_bundle(self.repo)
        self.assertEqual(
            result["fingerprint"], git_checks.implementation_fingerprint(self.repo)
        )


class ResultParsingTests(unittest.TestCase):
    def test_parse_changes_required_fixture(self):
        parsed = review_bundle.parse_result(
            support.read_fixture("sample-review-result.md")
        )
        self.assertEqual(parsed["status"], "CHANGES_REQUIRED")
        self.assertEqual(len(parsed["findings"]), 2)
        first = parsed["findings"][0]
        self.assertEqual(first["fields"]["Severity"], "High")
        self.assertIn("docstatus", first["fields"]["Required Fix"])
        self.assertEqual(len(parsed["verified_items"]), 2)

    def test_parse_approved(self):
        text = (
            "# Review Result\n\n- **Status:** APPROVED\n\n"
            "## Verified Items\n\n- All implementation steps match the plan.\n"
        )
        parsed = review_bundle.parse_result(text)
        self.assertEqual(parsed["status"], "APPROVED")
        self.assertEqual(parsed["findings"], [])

    def test_reject_missing_status(self):
        with self.assertRaises(review_bundle.ReviewError):
            review_bundle.parse_result("# Review Result\n\nLooks good to me!\n")

    def test_reject_unsupported_status(self):
        with self.assertRaises(review_bundle.ReviewError):
            review_bundle.parse_result("- **Status:** LGTM\n")

    def test_reject_changes_required_without_findings(self):
        with self.assertRaises(review_bundle.ReviewError) as ctx:
            review_bundle.parse_result("- **Status:** CHANGES_REQUIRED\n\n## Findings\n")
        self.assertIn("REVIEW_NO_FINDINGS", str(ctx.exception))

    def test_reject_finding_missing_required_fix(self):
        text = (
            "- **Status:** CHANGES_REQUIRED\n\n## Findings\n\n"
            "### 1. Broken thing\n\n- **Severity:** High\n- **Issue:** It is broken.\n"
        )
        with self.assertRaises(review_bundle.ReviewError) as ctx:
            review_bundle.parse_result(text)
        self.assertIn("Required Fix", str(ctx.exception))

    def test_reject_invalid_severity(self):
        text = (
            "- **Status:** CHANGES_REQUIRED\n\n## Findings\n\n"
            "### 1. Broken thing\n\n- **Severity:** Catastrophic\n"
            "- **Issue:** It is broken.\n- **Required Fix:** Fix it.\n"
        )
        with self.assertRaises(review_bundle.ReviewError) as ctx:
            review_bundle.parse_result(text)
        self.assertIn("REVIEW_FINDING_SEVERITY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
