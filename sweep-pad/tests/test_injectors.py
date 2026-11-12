import ctypes
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from injectors import get_injector, validate
from injectors import linux, macos, windows


class LinuxInjectorTests(unittest.TestCase):
    def test_x11_command_and_no_shell(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":1"}, clear=True), patch.object(linux.shutil, "which", return_value="/usr/bin/xdotool"), patch.object(linux.subprocess, "run") as run:
            linux.inject_keys("yhmbc", 9)
        run.assert_called_once_with(["xdotool", "key", "--clearmodifiers", "--delay", "9", "y", "h", "m", "b", "c"], check=True, capture_output=True, text=True)

    def test_wayland_commands(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}, clear=True):
            self.assertEqual(linux.build_command("az", 8), ["ydotool", "key", "--key-delay", "8", "30:1", "30:0", "44:1", "44:0"])
        with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=True):
            self.assertTrue(linux.is_wayland())

    def test_separator_keys(self):
        with patch.dict(os.environ, {'XDG_SESSION_TYPE': 'x11'}, clear=True):
            self.assertEqual(linux.build_command("a'b c")[-5:], ['a', 'apostrophe', 'b', 'space', 'c'])
        with patch.dict(os.environ, {'XDG_SESSION_TYPE': 'wayland'}, clear=True):
            self.assertEqual(linux.build_command(" '")[-4:], ['57:1', '57:0', '40:1', '40:0'])
        self.assertEqual((macos.KEY_CODES[' '], macos.KEY_CODES["'"]), (49, 39))
        api = Mock()
        api.MapVirtualKeyW.return_value = 40
        api.SendInput.return_value = 1
        with patch.object(windows, '_api', return_value=api), patch.object(windows.time, 'sleep'):
            windows.inject_keys(" '")
        self.assertEqual(api.MapVirtualKeyW.call_args_list,
                         [unittest.mock.call(32, 0), unittest.mock.call(0xDE, 0)])

    def test_missing_tool_and_display(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(linux.shutil, "which", return_value=None):
            self.assertFalse(linux.availability()[0])
            with self.assertRaisesRegex(RuntimeError, "Missing xdotool"):
                linux.inject_keys("a")
        with patch.dict(os.environ, {}, clear=True), patch.object(linux.shutil, "which", return_value="xdotool"):
            self.assertIn("DISPLAY", linux.availability()[1])

    def test_subprocess_failure_is_clear(self):
        with patch.object(linux, "availability", return_value=(True, "ok")), patch.object(linux.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "ydotool")):
            with self.assertRaisesRegex(RuntimeError, "injection failed"):
                linux.inject_keys("a")


class LinuxCommitTests(unittest.TestCase):
    def test_x11_commit_uses_xdotool_type(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":1"}, clear=True), patch.object(linux.shutil, "which", return_value="/usr/bin/xdotool"), patch.object(linux.subprocess, "run") as run:
            linux.commit_text("顏值")
        run.assert_called_once_with(["xdotool", "type", "--clearmodifiers", "--delay", "12", "--", "顏值"], check=True, capture_output=True, text=True, timeout=30)

    def test_text_starting_with_dash_is_not_an_option(self):
        self.assertEqual(linux.build_commit_command("-x", 5)[-2:], ["--", "-x"])

    def test_missing_tools_are_named(self):
        with patch.dict(os.environ, {"DISPLAY": ":1"}, clear=True), patch.object(linux.shutil, "which", return_value=None), patch.object(linux.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "install xdotool"):
                linux.commit_text("顏")
        with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=True), patch.object(linux.shutil, "which", side_effect=lambda t: None if t == "wl-copy" else "/usr/bin/" + t):
            ok, msg = linux.commit_availability()
            self.assertFalse(ok)
            self.assertIn("wl-copy", msg)
            self.assertIn("wl-clipboard", msg)
        with patch.dict(os.environ, {}, clear=True), patch.object(linux.shutil, "which", return_value="/usr/bin/xdotool"):
            self.assertIn("DISPLAY", linux.commit_availability()[1])
        run.assert_not_called()

    def test_wayland_paste_restores_clipboard(self):
        calls = []
        def run(cmd, **kw):
            calls.append((cmd, kw.get("input")))
            return subprocess.CompletedProcess(cmd, 0, stdout=b"old", stderr=b"")
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}, clear=True), patch.object(linux.shutil, "which", return_value="/usr/bin/x"), patch.object(linux.subprocess, "run", side_effect=run), patch.object(linux.time, "sleep"):
            linux.commit_text("顏值")
        self.assertEqual([c[0] for c in calls], [["wl-paste", "--no-newline"], ["wl-copy", "--", "顏值"],
                                                 ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], ["wl-copy"]])
        self.assertEqual(calls[-1][1], b"old")

    def test_failure_is_clear(self):
        with patch.object(linux, "commit_availability", return_value=(True, "ok")), patch.object(linux, "is_wayland", return_value=False), patch.object(linux.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "xdotool")):
            with self.assertRaisesRegex(RuntimeError, "Text commit failed"):
                linux.commit_text("顏")

    def test_rejects_control_characters(self):
        for module in (linux, windows, macos):
            for text in ("a\nb", "\x1b", None, "x" * 257):
                with self.subTest(module=module.__name__, text=text), self.assertRaises(ValueError):
                    module.commit_text(text)
            module.commit_text("")  # empty never injects


class WindowsInjectorTests(unittest.TestCase):
    def test_commit_text_alias(self):
        self.assertIs(windows.inject_unicode, windows.commit_text)

    def test_input_structure_size(self):
        self.assertEqual(ctypes.sizeof(windows.INPUT), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)

    def test_scancode_down_up(self):
        events = []
        api = Mock()
        api.MapVirtualKeyW.return_value = 30
        def send(count, event, size):
            item = ctypes.cast(event, ctypes.POINTER(windows.INPUT)).contents
            events.append((count, item.type, item.ki.wVk, item.ki.wScan, item.ki.dwFlags, size))
            return 1
        api.SendInput.side_effect = send
        with patch.object(windows, "_api", return_value=api), patch.object(windows.time, "sleep") as sleep:
            windows.inject_keys("a", 8)
        api.MapVirtualKeyW.assert_called_once_with(ord("A"), 0)
        self.assertEqual([r[4] for r in events], [8, 10])
        self.assertEqual([r[3] for r in events], [30, 30])
        sleep.assert_called_once_with(.008)

    def test_unicode_surrogate_pairs(self):
        events = []
        api = Mock()
        def send(count, event, size):
            item = ctypes.cast(event, ctypes.POINTER(windows.INPUT)).contents
            events.append((item.ki.wScan, item.ki.dwFlags))
            return 1
        api.SendInput.side_effect = send
        with patch.object(windows, "_api", return_value=api), patch.object(windows.time, "sleep"):
            windows.inject_unicode("𠄘", 0)
        units = [int.from_bytes("𠄘".encode("utf-16-le")[i:i+2], "little") for i in (0, 2)]
        self.assertEqual(events, [(units[0], 4), (units[0], 6), (units[1], 4), (units[1], 6)])

    def test_failed_send(self):
        api = Mock()
        api.MapVirtualKeyW.return_value = 30
        api.SendInput.return_value = 0
        with patch.object(windows, "_api", return_value=api):
            with self.assertRaisesRegex(RuntimeError, "SendInput failed"):
                windows.inject_keys("a")


class MacInjectorTests(unittest.TestCase):
    def test_events_released_and_delay(self):
        api = Mock()
        api.AXIsProcessTrusted.return_value = True
        api.CGEventCreateKeyboardEvent.side_effect = [101, 102]
        with patch.object(macos, "_api", return_value=api), patch.object(macos.time, "sleep") as sleep:
            macos.inject_keys("y", 8)
        self.assertEqual(api.CGEventCreateKeyboardEvent.call_args_list, [unittest.mock.call(None, 16, True), unittest.mock.call(None, 16, False)])
        self.assertEqual(api.CGEventPost.call_args_list, [unittest.mock.call(0, 101), unittest.mock.call(0, 102)])
        self.assertEqual(api.CFRelease.call_count, 2)
        sleep.assert_called_once_with(.008)

    def test_permission_required(self):
        api = Mock()
        api.AXIsProcessTrusted.return_value = False
        with patch.object(macos, "_api", return_value=api), patch("sys.stderr"):
            self.assertFalse(macos.availability()[0])
            with self.assertRaisesRegex(RuntimeError, "Accessibility"):
                macos.inject_keys("a")
        api.CGEventPost.assert_not_called()

    def test_release_even_when_post_fails(self):
        api = Mock()
        api.AXIsProcessTrusted.return_value = True
        api.CGEventCreateKeyboardEvent.return_value = 101
        api.CGEventPost.side_effect = RuntimeError("posting failed")
        with patch.object(macos, "_api", return_value=api):
            with self.assertRaises(RuntimeError):
                macos.inject_keys("a")
        api.CFRelease.assert_called_once_with(101)


class MacCommitTests(unittest.TestCase):
    """Mocked only: real CGEvent Unicode posting is UNVERIFIED on a Mac."""
    def test_unicode_events_down_up_and_release(self):
        api = Mock()
        api.AXIsProcessTrusted.return_value = True
        api.CGEventCreateKeyboardEvent.side_effect = [201, 202]
        seen = []
        api.CGEventKeyboardSetUnicodeString.side_effect = lambda ev, n, buf: seen.append((ev, n, list(buf[:n])))
        with patch.object(macos, "_api", return_value=api), patch.object(macos.time, "sleep") as sleep:
            macos.commit_text("顏值", 8)
        self.assertEqual(api.CGEventCreateKeyboardEvent.call_args_list, [unittest.mock.call(None, 0, True), unittest.mock.call(None, 0, False)])
        self.assertEqual(seen, [(201, 2, [0x984F, 0x503C]), (202, 2, [0x984F, 0x503C])])
        self.assertEqual(api.CGEventPost.call_args_list, [unittest.mock.call(0, 201), unittest.mock.call(0, 202)])
        self.assertEqual(api.CFRelease.call_args_list, [unittest.mock.call(201), unittest.mock.call(202)])
        sleep.assert_called_once_with(.008)

    def test_chunks_never_split_surrogates(self):
        text = "顏" * 19 + "𠄘" + "值" * 25
        chunks = macos.unicode_chunks(text)
        self.assertTrue(all(len(c) <= 20 for c in chunks))
        self.assertEqual(len(chunks[0]), 19)  # the pair moved to the next chunk
        joined = b"".join(u.to_bytes(2, "little") for c in chunks for u in c).decode("utf-16-le")
        self.assertEqual(joined, text)
        api = Mock()
        api.AXIsProcessTrusted.return_value = True
        api.CGEventCreateKeyboardEvent.return_value = 7
        with patch.object(macos, "_api", return_value=api), patch.object(macos.time, "sleep"):
            macos.commit_text(text, 0)
        self.assertEqual(api.CGEventPost.call_count, 2 * len(chunks))

    def test_permission_message(self):
        api = Mock()
        api.AXIsProcessTrusted.return_value = False
        with patch.object(macos, "_api", return_value=api), patch("sys.stderr"):
            with self.assertRaisesRegex(RuntimeError, "Accessibility"):
                macos.commit_text("顏")
        api.CGEventPost.assert_not_called()

    def test_release_even_when_post_fails(self):
        api = Mock()
        api.AXIsProcessTrusted.return_value = True
        api.CGEventCreateKeyboardEvent.return_value = 9
        api.CGEventPost.side_effect = RuntimeError("posting failed")
        with patch.object(macos, "_api", return_value=api), self.assertRaises(RuntimeError):
            macos.commit_text("顏")
        api.CFRelease.assert_called_once_with(9)


class CommonInjectorTests(unittest.TestCase):
    def test_platform_selection(self):
        self.assertIs(get_injector("linux"), linux)
        self.assertIs(get_injector("darwin"), macos)
        self.assertIs(get_injector("win32"), windows)
        with self.assertRaisesRegex(RuntimeError, "Unsupported"):
            get_injector("other")

    def test_rejects_nonletters_and_bad_delay_before_injection(self):
        for text in ("A", "a;ls", "顏", "a\n", None):
            for module in (linux, windows, macos):
                with self.assertRaises(ValueError):
                    module.inject_keys(text)
        for delay in (-1, float("nan"), float("inf"), "8", True):
            with self.assertRaises(ValueError):
                validate("a", delay)

    def test_empty_input_never_injects(self):
        for module in (linux, windows, macos):
            module.inject_keys("")


if __name__ == "__main__":
    unittest.main()
