"""Unit tests for scripts/core/environment.py."""

import shutil
import unittest
from pathlib import Path

import support
from core import environment


class BenchDetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bench = support.make_bench(self.tmp)
        self.app = self.bench / "apps" / "general_trading"

    def test_detect_bench_from_app_root(self):
        self.assertEqual(environment.find_bench(self.app), self.bench)

    def test_detect_bench_from_app_subdirectory(self):
        sub = self.app / "general_trading" / "doctype"
        self.assertEqual(environment.find_bench(sub), self.bench)

    def test_reject_non_bench_directory(self):
        outside = self.tmp / "not-a-bench"
        outside.mkdir()
        with self.assertRaises(environment.DetectionError):
            environment.find_bench(outside)

    def test_partial_bench_layout_rejected(self):
        partial = self.tmp / "partial"
        (partial / "apps").mkdir(parents=True)
        (partial / "sites").mkdir()
        # no sites/apps.txt
        with self.assertRaises(environment.DetectionError):
            environment.find_bench(partial)


class AppDetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bench = support.make_bench(self.tmp)
        self.app = self.bench / "apps" / "general_trading"

    def test_detect_app_from_subdirectory(self):
        env = environment.detect_app(self.app / "general_trading" / "public")
        self.assertEqual(env.app_name, "general_trading")
        self.assertEqual(env.app_path, self.app)
        self.assertEqual(env.bench_path, self.bench)
        self.assertEqual(env.git_root, self.app)

    def test_app_must_be_listed_in_apps_txt(self):
        rogue = self.bench / "apps" / "rogue_app"
        rogue.mkdir()
        support.init_repo(rogue, initial_commit=True)
        with self.assertRaises(environment.DetectionError) as ctx:
            environment.detect_app(rogue)
        self.assertIn("apps.txt", str(ctx.exception))

    def test_app_must_be_git_repository(self):
        shutil.rmtree(self.app / ".git")
        with self.assertRaises(environment.DetectionError) as ctx:
            environment.detect_app(self.app)
        self.assertIn("Git repository", str(ctx.exception))

    def test_bench_root_is_ambiguous(self):
        with self.assertRaises(environment.DetectionError) as ctx:
            environment.detect_app(self.bench)
        self.assertIn("general_trading", str(ctx.exception))


class SiteDetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bench = support.make_bench(self.tmp)

    def test_single_site_detected(self):
        sites = environment.detect_sites(
            self.bench,
            "general_trading",
            list_apps=lambda bench, site: ["frappe", "general_trading"],
        )
        self.assertEqual([s.name for s in sites], ["car.wash"])
        self.assertTrue(sites[0].app_installed)

    def test_multiple_sites(self):
        second = self.bench / "sites" / "demo.local"
        second.mkdir()
        (second / "site_config.json").write_text("{}", encoding="utf-8")

        def fake_list(bench, site):
            return ["frappe", "general_trading"] if site == "car.wash" else ["frappe"]

        sites = environment.detect_sites(self.bench, "general_trading", list_apps=fake_list)
        by_name = {s.name: s.app_installed for s in sites}
        self.assertEqual(by_name, {"car.wash": True, "demo.local": False})

    def test_no_site_installed(self):
        sites = environment.detect_sites(
            self.bench, "general_trading", list_apps=lambda b, s: ["frappe"]
        )
        self.assertFalse(any(s.app_installed for s in sites))

    def test_non_site_entries_excluded(self):
        candidates = environment.list_site_candidates(self.bench)
        self.assertEqual(candidates, ["car.wash"])
        self.assertNotIn("assets", candidates)
        self.assertNotIn("apps.txt", candidates)

    def test_unknown_installation_status_when_bench_unavailable(self):
        sites = environment.detect_sites(
            self.bench, "general_trading", list_apps=lambda b, s: None
        )
        self.assertIsNone(sites[0].app_installed)


if __name__ == "__main__":
    unittest.main()
