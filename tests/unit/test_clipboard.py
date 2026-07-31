"""Unit tests for scripts/core/clipboard.py.

The same plugin runs on a Windows host through WSL and on a native Ubuntu
desktop, and the correct clipboard differs between them. Every test here is
fully mocked: the environment, the executable lookup, and the command runner
are all injected, and ``setUpModule`` replaces ``subprocess.run`` inside the
clipboard module with a tripwire, so no test in this file can reach the real
host clipboard of whichever machine runs the suite.
"""

from __future__ import annotations

import base64
import io
import json
import shutil
import unittest
from pathlib import Path
from unittest import mock

import support
from core import clipboard, exit_codes, workflow_state

import cli  # noqa: E402  (scripts/ is on sys.path via support)

# Realistic payload: the shape the testing-task skill produces.
ARABIC = "العنوان:\nاختبار نظام حجز المخزون المؤقت\n\nالوصف:\nيرجى اختبار منطق حجز الكميات مؤقتاً.\n"

_real_subprocess_run = clipboard.subprocess.run


def _forbidden_run(*args, **kwargs):  # pragma: no cover - only fires on a bug
    raise AssertionError(
        "a clipboard test tried to spawn a real process: "
        f"{args[0] if args else kwargs.get('args')}"
    )


def setUpModule():
    clipboard.subprocess.run = _forbidden_run


def tearDownModule():
    clipboard.subprocess.run = _real_subprocess_run


def fake_which(*available: str):
    """Return a ``shutil.which`` replacement that knows only *available*."""
    known = set(available)

    def which(name: str):
        if name not in known:
            return None
        return name if name.startswith("/") else f"/usr/bin/{name}"

    return which


class Runner:
    """Records every command instead of executing it."""

    def __init__(self, failures: tuple[str, ...] = ()):
        self.calls: list[dict] = []
        self.failures = failures

    def __call__(self, argv, stdin_bytes, capture_stderr):
        self.calls.append(
            {
                "argv": list(argv),
                "stdin": stdin_bytes,
                "capture_stderr": capture_stderr,
            }
        )
        name = Path(argv[0]).name
        if name in self.failures:
            return clipboard.RunOutcome(False, "exited with status 1")
        return clipboard.RunOutcome(True, "copied")

    @property
    def executables(self) -> list[str]:
        return [Path(call["argv"][0]).name for call in self.calls]

    def all_argv_text(self) -> str:
        return "\n".join(arg for call in self.calls for arg in call["argv"])


def no_wsl_kernel():
    """Patch the kernel probes so a *real* WSL machine tests as native Linux."""
    missing = Path("/nonexistent/frappe-workflow-test/osrelease")
    return mock.patch.multiple(
        clipboard, OSRELEASE_PATH=missing, PROC_VERSION_PATH=missing
    )


WAYLAND_ENV = {"WAYLAND_DISPLAY": "wayland-0", "XDG_SESSION_TYPE": "wayland"}
X11_ENV = {"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"}


class WslDetectionTests(unittest.TestCase):
    def test_env_markers_identify_wsl(self):
        for marker in clipboard.WSL_ENV_MARKERS:
            with self.subTest(marker=marker), no_wsl_kernel():
                self.assertTrue(clipboard.is_wsl({marker: "Ubuntu"}))

    def test_kernel_osrelease_identifies_wsl_without_env_markers(self):
        tmp = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, tmp, True)
        osrelease = tmp / "osrelease"
        osrelease.write_text("5.15.167.4-microsoft-standard-WSL2\n", encoding="utf-8")
        with mock.patch.multiple(
            clipboard,
            OSRELEASE_PATH=osrelease,
            PROC_VERSION_PATH=tmp / "absent",
        ):
            self.assertTrue(clipboard.is_wsl({}))

    def test_native_linux_is_not_wsl(self):
        with no_wsl_kernel():
            self.assertFalse(clipboard.is_wsl(X11_ENV))

    def test_unreadable_kernel_files_do_not_raise(self):
        with no_wsl_kernel():
            self.assertFalse(clipboard.is_wsl({}))


class WslClipboardTests(unittest.TestCase):
    """Inside WSL the target is the Windows host clipboard, always."""

    def test_powershell_wins_even_when_linux_tools_are_installed(self):
        runner = Runner()
        result = clipboard.copy(
            ARABIC,
            env={"WSL_DISTRO_NAME": "Ubuntu", **WAYLAND_ENV, **X11_ENV},
            which=fake_which("powershell.exe", "wl-copy", "xclip", "xsel"),
            run=runner,
        )
        self.assertTrue(result.copied, result.render())
        self.assertEqual(result.platform, "wsl")
        self.assertEqual(result.method, "powershell.exe")
        self.assertEqual(result.target, "Windows host clipboard")
        self.assertEqual(runner.executables, ["powershell.exe"])

    def test_text_reaches_powershell_as_base64_decoded_to_utf8(self):
        runner = Runner()
        clipboard.copy(
            ARABIC,
            env={"WSL_INTEROP": "/run/WSL/8_interop"},
            which=fake_which("powershell.exe"),
            run=runner,
        )
        argv = runner.calls[0]["argv"]
        self.assertEqual(argv[1:4], ["-NoProfile", "-NonInteractive", "-Command"])
        script = argv[4]
        expected = base64.b64encode(ARABIC.rstrip("\n").encode("utf-8")).decode("ascii")
        self.assertIn(expected, script)
        self.assertIn("[Convert]::FromBase64String(", script)
        self.assertIn("[Text.Encoding]::UTF8.GetString(", script)
        self.assertIn("Set-Clipboard -Value ", script)

    def test_no_raw_arabic_is_embedded_in_the_powershell_source(self):
        runner = Runner()
        clipboard.copy(
            ARABIC,
            env={"WSL_DISTRO_NAME": "Ubuntu"},
            which=fake_which("powershell.exe"),
            run=runner,
        )
        for argument in runner.calls[0]["argv"]:
            with self.subTest(argument=argument[:40]):
                self.assertTrue(argument.isascii(), "generated text leaked into argv")
        self.assertNotIn("العنوان", runner.all_argv_text())
        # The payload travels in the command, never on stdin.
        self.assertIsNone(runner.calls[0]["stdin"])

    def test_clip_exe_is_never_used(self):
        runner = Runner()
        clipboard.copy(
            ARABIC,
            env={"WSL_DISTRO_NAME": "Ubuntu"},
            which=fake_which("powershell.exe", "clip.exe"),
            run=runner,
        )
        self.assertNotIn("clip.exe", runner.all_argv_text())
        source = (support.PLUGIN_ROOT / "scripts/core/clipboard.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("clip.exe", source, "clipboard.py must not reference clip.exe")

    def test_system32_path_is_the_documented_fallback(self):
        runner = Runner()
        result = clipboard.copy(
            ARABIC,
            env={"WSL_DISTRO_NAME": "Ubuntu"},
            which=fake_which(clipboard.POWERSHELL_FALLBACK),
            run=runner,
        )
        self.assertTrue(result.copied, result.render())
        self.assertEqual(runner.calls[0]["argv"][0], clipboard.POWERSHELL_FALLBACK)

    def test_missing_powershell_fails_without_falling_back_to_linux_tools(self):
        runner = Runner()
        result = clipboard.copy(
            ARABIC,
            env={"WSL_DISTRO_NAME": "Ubuntu", **X11_ENV},
            which=fake_which("xclip", "xsel", "wl-copy"),
            run=runner,
        )
        self.assertFalse(result.copied)
        self.assertEqual(runner.calls, [])
        self.assertIn("Windows host clipboard is not reachable", result.error)
        self.assertEqual([a.method for a in result.attempts], ["powershell.exe"])


class NativeLinuxClipboardTests(unittest.TestCase):
    def copy(self, env, which, runner):
        with no_wsl_kernel():
            return clipboard.copy(ARABIC, env=env, which=which, run=runner)

    def test_wayland_selects_wl_copy(self):
        runner = Runner()
        result = self.copy(WAYLAND_ENV, fake_which("wl-copy", "xclip", "xsel"), runner)
        self.assertTrue(result.copied, result.render())
        self.assertEqual(result.platform, "linux")
        self.assertEqual(result.method, "wl-copy")
        self.assertEqual(runner.executables, ["wl-copy"])
        self.assertEqual(runner.calls[0]["argv"], ["/usr/bin/wl-copy"])

    def test_x11_selects_xclip(self):
        runner = Runner()
        result = self.copy(X11_ENV, fake_which("xclip", "xsel"), runner)
        self.assertTrue(result.copied, result.render())
        self.assertEqual(result.method, "xclip")
        self.assertEqual(
            runner.calls[0]["argv"], ["/usr/bin/xclip", "-selection", "clipboard"]
        )

    def test_x11_falls_back_to_xsel_when_xclip_is_not_installed(self):
        runner = Runner()
        result = self.copy(X11_ENV, fake_which("xsel"), runner)
        self.assertTrue(result.copied, result.render())
        self.assertEqual(result.method, "xsel")
        self.assertEqual(runner.executables, ["xsel"])
        self.assertEqual(
            runner.calls[0]["argv"], ["/usr/bin/xsel", "--clipboard", "--input"]
        )
        unavailable = {a.method: a.detail for a in result.attempts if a.status == "unavailable"}
        self.assertIn("xclip", unavailable)
        self.assertIn("not installed", unavailable["xclip"])

    def test_x11_falls_back_to_xsel_when_xclip_fails(self):
        runner = Runner(failures=("xclip",))
        result = self.copy(X11_ENV, fake_which("xclip", "xsel"), runner)
        self.assertTrue(result.copied, result.render())
        self.assertEqual(result.method, "xsel")
        self.assertEqual(runner.executables, ["xclip", "xsel"])

    def test_x11_is_used_when_wayland_tool_is_missing(self):
        runner = Runner()
        result = self.copy({**WAYLAND_ENV, **X11_ENV}, fake_which("xclip"), runner)
        self.assertTrue(result.copied, result.render())
        self.assertEqual(result.method, "xclip")

    def test_text_is_passed_as_utf8_on_stdin(self):
        runner = Runner()
        self.copy(WAYLAND_ENV, fake_which("wl-copy"), runner)
        self.assertEqual(runner.calls[0]["stdin"], ARABIC.rstrip("\n").encode("utf-8"))

    def test_powershell_is_never_invoked_on_a_native_desktop(self):
        for env in (WAYLAND_ENV, X11_ENV, {}):
            with self.subTest(session=sorted(env)):
                runner = Runner()
                self.copy(
                    env,
                    fake_which("wl-copy", "xclip", "xsel", "powershell.exe"),
                    runner,
                )
                self.assertNotIn("powershell.exe", runner.all_argv_text())
                with no_wsl_kernel():
                    planned = [
                        a.method
                        for a in clipboard.candidates(env, fake_which("powershell.exe"))
                    ]
                self.assertNotIn("powershell.exe", planned)


class HeadlessFailureTests(unittest.TestCase):
    """No display and no tools: a clear, structured failure — never a claim of success."""

    def failure(self, env, which):
        runner = Runner()
        with no_wsl_kernel():
            result = clipboard.copy(ARABIC, env=env, which=which, run=runner)
        self.assertEqual(runner.calls, [], "nothing may be executed without a clipboard")
        return result

    def test_headless_session_reports_every_checked_method(self):
        result = self.failure({}, fake_which("wl-copy", "xclip", "xsel"))
        self.assertFalse(result.copied)
        self.assertEqual(result.method, "")
        self.assertIn("No desktop clipboard is available", result.error)
        self.assertEqual(
            [a.method for a in result.attempts], ["wl-copy", "xclip", "xsel"]
        )
        for attempt in result.attempts:
            with self.subTest(method=attempt.method):
                self.assertEqual(attempt.status, "unavailable")
                self.assertIn("is not set", attempt.detail)

    def test_missing_packages_report_the_missing_tools(self):
        result = self.failure({**WAYLAND_ENV, **X11_ENV}, fake_which())
        self.assertFalse(result.copied)
        details = {a.method: a.detail for a in result.attempts}
        self.assertIn("wl-copy is not installed", details["wl-copy"])
        self.assertIn("xclip is not installed", details["xclip"])
        self.assertIn("xsel is not installed", details["xsel"])

    def test_failure_names_the_packages_but_installs_nothing(self):
        result = self.failure({}, fake_which())
        rendered = result.render()
        self.assertIn("wl-clipboard", rendered)
        self.assertIn("xclip", rendered)
        self.assertIn("xsel", rendered)
        self.assertIn("never installs packages", rendered)
        for verb in ("apt-get install", "apt install", "sudo "):
            with self.subTest(verb=verb):
                self.assertNotIn(verb, rendered)

    def test_render_does_not_claim_success(self):
        rendered = self.failure({}, fake_which()).render()
        self.assertNotIn("Copied", rendered)

    def test_empty_text_is_refused_before_any_detection(self):
        for text in ("", "\n\n", "   \n"):
            with self.subTest(text=repr(text)), no_wsl_kernel():
                with self.assertRaises(clipboard.ClipboardError):
                    clipboard.copy(text, env=WAYLAND_ENV, which=fake_which("wl-copy"))


class RefusedCopyTests(unittest.TestCase):
    """A tool that runs and fails is a different problem from a missing tool."""

    def test_windows_refusing_the_clipboard_is_reported_as_such(self):
        runner = Runner(failures=("powershell.exe",))
        result = clipboard.copy(
            ARABIC,
            env={"WSL_DISTRO_NAME": "Ubuntu"},
            which=fake_which("powershell.exe"),
            run=runner,
        )
        self.assertFalse(result.copied)
        self.assertEqual(result.error, clipboard.REFUSED_WSL)
        self.assertIn("locked", result.hint)
        # Not the "install something" answer: powershell.exe was found.
        self.assertNotIn("interop", result.hint)
        self.assertEqual([a.status for a in result.attempts], ["failed"])

    def test_every_linux_tool_failing_is_reported_as_a_refusal(self):
        runner = Runner(failures=("wl-copy", "xclip", "xsel"))
        with no_wsl_kernel():
            result = clipboard.copy(
                ARABIC,
                env={**WAYLAND_ENV, **X11_ENV},
                which=fake_which("wl-copy", "xclip", "xsel"),
                run=runner,
            )
        self.assertFalse(result.copied)
        self.assertEqual(result.error, clipboard.REFUSED_LINUX)
        self.assertEqual(runner.executables, ["wl-copy", "xclip", "xsel"])

    def test_missing_tools_keep_the_install_answer(self):
        with no_wsl_kernel():
            result = clipboard.copy(
                ARABIC, env=X11_ENV, which=fake_which(), run=Runner()
            )
        self.assertEqual(result.error, clipboard.NO_CLIPBOARD_LINUX)
        self.assertEqual(result.hint, clipboard.INSTALL_HINT_LINUX)


class StderrHandlingTests(unittest.TestCase):
    """Tool errors are surfaced, but never carry the payload back out."""

    def test_only_the_first_line_of_a_tool_error_is_kept(self):
        payload = base64.b64encode(ARABIC.encode("utf-8")).decode("ascii")
        # Shape of a real PowerShell error report: the diagnostic first, then
        # an echo of the failing command.
        stderr = (
            "Set-Clipboard : Requested Clipboard operation did not succeed.\n"
            "At line:1 char:34\n"
            f"+ ... Set-Clipboard -Value ([Convert]::FromBase64String('{payload}'\n"
        )
        detail = clipboard._first_line(stderr)
        self.assertEqual(
            detail, "Set-Clipboard : Requested Clipboard operation did not succeed."
        )
        self.assertNotIn(payload, detail)

    def test_a_long_single_line_error_is_capped(self):
        detail = clipboard._first_line("x" * 500)
        self.assertLessEqual(len(detail), 201)
        self.assertTrue(detail.endswith("…"))

    def test_empty_stderr_is_dropped(self):
        self.assertEqual(clipboard._first_line("\n  \n"), "")


class ResultPayloadTests(unittest.TestCase):
    def test_result_never_carries_the_copied_text(self):
        runner = Runner()
        with no_wsl_kernel():
            result = clipboard.copy(
                ARABIC, env=WAYLAND_ENV, which=fake_which("wl-copy"), run=runner
            )
        payload = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertNotIn("العنوان", payload)
        self.assertNotIn("اختبار", payload)
        self.assertEqual(result.characters, len(ARABIC.rstrip("\n")))
        self.assertIn("Copied", result.render())


class ClipboardCliTests(unittest.TestCase):
    """The CLI surface: exit codes, and no workflow state is touched."""

    def setUp(self):
        self.repo = support.make_temp_dir()
        self.addCleanup(shutil.rmtree, self.repo, True)
        workflow_state.init_state(self.repo)
        self.state_path = workflow_state.state_path(self.repo)
        self.before = self.state_path.read_bytes()

    def run_cli(self, stdin_text: str, *args: str) -> tuple[int, str, str]:
        stdin = io.TextIOWrapper(io.BytesIO(stdin_text.encode("utf-8")))
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(cli.sys, "stdin", stdin), mock.patch.object(
            cli.sys, "stdout", out
        ), mock.patch.object(cli.sys, "stderr", err):
            code = cli.main(["clipboard", "copy", *args])
        return code, out.getvalue(), err.getvalue()

    def assert_state_untouched(self):
        self.assertEqual(self.state_path.read_bytes(), self.before)
        state = workflow_state.load_state(self.repo)
        self.assertEqual(state["current_stage"], "planning")
        self.assertEqual(state["testing_task"]["status"], "pending")

    def test_headless_failure_exits_with_the_clipboard_code(self):
        result = clipboard.CopyResult(
            copied=False,
            platform="linux",
            error=clipboard.NO_CLIPBOARD_LINUX,
            hint=clipboard.INSTALL_HINT_LINUX,
            attempts=(clipboard.Attempt("xclip", "X11", "unavailable", "DISPLAY is not set"),),
        )
        with mock.patch.object(clipboard, "copy", return_value=result):
            code, out, err = self.run_cli(ARABIC)
        self.assertEqual(code, exit_codes.CLIPBOARD_UNAVAILABLE)
        self.assertEqual(out, "")
        self.assertIn("No desktop clipboard is available", err)
        self.assertIn("DISPLAY is not set", err)
        self.assert_state_untouched()

    def test_missing_packages_exit_with_the_clipboard_code(self):
        result = clipboard.CopyResult(
            copied=False,
            platform="linux",
            error=clipboard.NO_CLIPBOARD_LINUX,
            hint=clipboard.INSTALL_HINT_LINUX,
            attempts=(
                clipboard.Attempt("xclip", "X11", "unavailable", "DISPLAY is set but xclip is not installed"),
            ),
        )
        with mock.patch.object(clipboard, "copy", return_value=result):
            code, _out, err = self.run_cli(ARABIC)
        self.assertEqual(code, exit_codes.CLIPBOARD_UNAVAILABLE)
        self.assertIn("not installed", err)
        self.assert_state_untouched()

    def test_successful_copy_exits_zero_without_echoing_the_text(self):
        result = clipboard.CopyResult(
            copied=True,
            platform="wsl",
            method="powershell.exe",
            target="Windows host clipboard",
            characters=len(ARABIC.rstrip("\n")),
        )
        with mock.patch.object(clipboard, "copy", return_value=result):
            code, out, err = self.run_cli(ARABIC)
        self.assertEqual(code, exit_codes.SUCCESS)
        self.assertIn("Windows host clipboard", out)
        self.assertNotIn("العنوان", out)
        self.assertEqual(err, "")
        self.assert_state_untouched()

    def test_empty_stdin_is_invalid_usage(self):
        code, _out, err = self.run_cli("   \n")
        self.assertEqual(code, exit_codes.INVALID_USAGE)
        self.assertIn("empty", err)
        self.assert_state_untouched()

    def test_json_output_reports_the_checked_methods(self):
        result = clipboard.CopyResult(
            copied=False,
            platform="linux",
            error=clipboard.NO_CLIPBOARD_LINUX,
            hint=clipboard.INSTALL_HINT_LINUX,
            attempts=(clipboard.Attempt("wl-copy", "Wayland", "unavailable", "WAYLAND_DISPLAY is not set"),),
        )
        with mock.patch.object(clipboard, "copy", return_value=result), mock.patch.object(
            cli.sys, "argv", ["frappe-workflow"]
        ):
            stdin = io.TextIOWrapper(io.BytesIO(ARABIC.encode("utf-8")))
            out = io.StringIO()
            with mock.patch.object(cli.sys, "stdin", stdin), mock.patch.object(
                cli.sys, "stdout", out
            ):
                code = cli.main(["--json", "clipboard", "copy"])
        self.assertEqual(code, exit_codes.CLIPBOARD_UNAVAILABLE)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["copied"])
        self.assertEqual(payload["checked"][0]["method"], "wl-copy")
        self.assert_state_untouched()


class NoRealClipboardAccessTests(unittest.TestCase):
    def test_the_tripwire_is_installed(self):
        """Proves the guard that makes every test above hermetic."""
        self.assertIs(clipboard.subprocess.run, _forbidden_run)
        with self.assertRaises(AssertionError):
            clipboard._run(["xclip"], b"x", False)


if __name__ == "__main__":
    unittest.main()
