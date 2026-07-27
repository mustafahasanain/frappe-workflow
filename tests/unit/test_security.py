"""Unit tests for scripts/core/security.py.

Credential-shaped inputs are assembled at runtime via
``support.synthetic_secret`` so this file contains no literal that the
scanner would (correctly) flag as a leak. See that helper's docstring.
"""

import shutil
import unittest

import support
from core import security

TOKEN = support.synthetic_secret("sk_", "live_", "9a8b7c6d", "5e4f3g2h1i0j")
PROD_TOKEN = support.synthetic_secret("prod-", "9a8b7c6d", "5e4f3g2h1i0j")
KEY_HEADER = support.synthetic_secret("-----BEGIN ", "RSA PRIVATE", " KEY-----")
TELEGRAM = support.synthetic_secret(
    "8123456789", ":", "AAHsomeRealLookingValue123456789012a"
)
PASSWORD = support.synthetic_secret("s3cret", "value")
DB_URL = support.synthetic_secret("mysql://root", ":", "hunter22", "@localhost/db")
OBVIOUSLY_FAKE = support.synthetic_secret("fake-", "key-for-tests-", "0000000000")
DUMMY = support.synthetic_secret("dummy-", "value-for-unit-tests")


class PatternTests(unittest.TestCase):
    def test_detect_token_assignment(self):
        findings = security.scan_text("settings.py", f'api_key = "{TOKEN}"\n')
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern, "token assignment")
        self.assertTrue(findings[0].blocking)

    def test_detect_private_key(self):
        findings = security.scan_text("key.pem", f"{KEY_HEADER}\nMIIB...\n")
        self.assertTrue(findings)
        self.assertEqual(findings[0].pattern, "private key")

    def test_detect_telegram_token(self):
        findings = security.scan_text("bot.py", f"token = {TELEGRAM}\n")
        self.assertTrue(any(f.pattern == "telegram bot token" for f in findings))

    def test_detect_password_assignment(self):
        findings = security.scan_text("conf.py", f'db_password = "{PASSWORD}"\n')
        self.assertTrue(any(f.pattern == "password assignment" for f in findings))

    def test_detect_database_url(self):
        findings = security.scan_text("conf.py", f"url = {DB_URL}\n")
        self.assertTrue(
            any(f.pattern == "database url with credentials" for f in findings)
        )

    def test_detect_authorization_header(self):
        header = support.synthetic_secret(
            'Authorization: "Bearer ', "abcdefghijklmnopqrstuvwxyz012345", '"'
        )
        findings = security.scan_text("client.py", f"{header}\n")
        self.assertTrue(any(f.pattern == "authorization header" for f in findings))

    def test_ignore_safe_text(self):
        findings = security.scan_text(
            "readme.md",
            "Use SSH keys for authentication. The password field is never stored.\n"
            "def get_reserved_qty(item):\n    return item.qty\n",
        )
        self.assertEqual(findings, [])

    def test_fake_values_are_non_blocking(self):
        findings = security.scan_text("test_config.py", f'api_key = "{OBVIOUSLY_FAKE}"\n')
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0].blocking)


class PlaceholderTests(unittest.TestCase):
    """Interpolation placeholders are the shape of a value, not a value."""

    def test_placeholders_are_not_findings(self):
        for line in (
            'api_key = "{API_KEY}"',
            'api_key = "{{ api_key }}"',
            'password = "${DB_PASSWORD}"',
            "password = '$DB_PASSWORD'",
            'access_token = "%(token)s"',
            'client_secret = "<your client secret here>"',
        ):
            with self.subTest(line=line):
                self.assertEqual(security.scan_text("template.py", line + "\n"), [])

    def test_real_value_next_to_placeholder_style_still_caught(self):
        findings = security.scan_text("conf.py", f'api_key = "{TOKEN}"\n')
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].blocking)


class RedactionTests(unittest.TestCase):
    def test_redact_long_value(self):
        self.assertEqual(security.redact("abcdefghijklmnop"), "abc...nop")

    def test_redact_short_value(self):
        self.assertEqual(security.redact("short"), "***")

    def test_finding_render_never_contains_full_value(self):
        findings = security.scan_text("f.py", f'api_key = "{TOKEN}"\n')
        self.assertNotIn(TOKEN, findings[0].render())
        self.assertIn("...", findings[0].render())


class PathScanTests(unittest.TestCase):
    def test_env_file_blocked(self):
        finding = security.scan_path_name(".env.production")
        self.assertIsNotNone(finding)
        self.assertTrue(finding.blocking)

    def test_deployment_config_blocked(self):
        finding = security.scan_path_name(".claude/deployment.local.json")
        self.assertIsNotNone(finding)

    def test_ssh_key_blocked(self):
        self.assertIsNotNone(security.scan_path_name("keys/id_rsa"))

    def test_normal_path_allowed(self):
        self.assertIsNone(security.scan_path_name("general_trading/hooks.py"))


class FileScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_scan_files_reports_and_skips_binary(self):
        (self.tmp / "leak.py").write_text(
            f'secret_key = "{PROD_TOKEN}"\n', encoding="utf-8"
        )
        (self.tmp / "blob.bin").write_bytes(b"\x00\x01\x02secret")
        findings = security.scan_files(self.tmp, ["leak.py", "blob.bin", "missing.py"])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].path, "leak.py")

    def test_blocking_filter(self):
        (self.tmp / "test_fixture.py").write_text(
            f'api_key = "{DUMMY}"\n', encoding="utf-8"
        )
        (self.tmp / "real.py").write_text(
            f'api_key = "{PROD_TOKEN}"\n', encoding="utf-8"
        )
        findings = security.scan_files(self.tmp, ["test_fixture.py", "real.py"])
        blocking = security.blocking_findings(findings)
        self.assertEqual([f.path for f in blocking], ["real.py"])

    def test_forbidden_filename_flagged_even_when_content_is_clean(self):
        (self.tmp / ".env").write_text("HARMLESS=1\n", encoding="utf-8")
        findings = security.scan_files(self.tmp, [".env"])
        self.assertTrue(any(f.pattern == "forbidden file" for f in findings))


if __name__ == "__main__":
    unittest.main()
