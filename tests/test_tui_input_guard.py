import ast
from contextlib import nullcontext
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from xingyuan_sis import terminal_input
from xingyuan_sis import tui
from xingyuan_sis.tui import animation, auth_view, screen


class TuiInputGuardTests(unittest.TestCase):
    def test_tui_modules_do_not_call_raw_input_or_getpass(self):
        tui_dir = Path(tui.__file__).parent
        offenders: list[str] = []
        for path in sorted(tui_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name) and node.func.id == "input":
                    offenders.append(f"{path.name}:{node.lineno}: input()")
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "getpass"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "getpass"
                ):
                    offenders.append(f"{path.name}:{node.lineno}: getpass.getpass()")
        self.assertEqual(offenders, [], "TUI text fields must use terminal_input.read_input: " + ", ".join(offenders))

    def test_secret_input_uses_the_same_tui_editor_and_masks_text(self):
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), \
             patch.object(terminal_input, "_read_interactive_line", return_value="s3cret") as read, \
             patch("sys.stdout.write"), patch("sys.stdout.flush"), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            with terminal_input.input_style(True):
                self.assertEqual(terminal_input.read_input("密码: ", secret=True), "s3cret")
        read.assert_called_once_with("密码: ", colored=True, secret=True)
        shown, cursor = terminal_input._visible_input(list("s3cret"), 6, 20, secret=True)
        self.assertEqual(shown, "••••••")
        self.assertEqual(cursor, 6)
        self.assertNotIn("s3cret", shown)

    def test_auth_field_escape_cancels_instead_of_becoming_text(self):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 24))), \
             patch.object(screen, "_paint"), patch("sys.stdout.isatty", return_value=False), \
             patch.object(auth_view, "read_input", side_effect=KeyboardInterrupt) as read:
            value = auth_view._read_field(
                "login",
                {"username": "", "password": ""},
                "password",
                "密码",
                secret=True,
                database="test.db",
                message="",
            )
        self.assertIsNone(value)
        self.assertTrue(read.call_args.kwargs["secret"])

    def test_auth_field_repaints_animation_while_input_is_idle(self):
        def fake_read(_prompt, **kwargs):
            kwargs["on_idle"]("abc")
            return "abc"

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 24))), \
             patch.object(screen, "_paint") as paint, patch("sys.stdout.isatty", return_value=False), \
             patch.object(auth_view, "_phase", side_effect=[0.0, 2.0]), \
             patch.object(auth_view, "read_input", side_effect=fake_read) as read:
            value = auth_view._read_field(
                "login",
                {"username": "", "password": ""},
                "password",
                "密码",
                secret=True,
                database="test.db",
                message="",
            )

        self.assertEqual(value, "abc")
        self.assertGreaterEqual(paint.call_count, 2)
        self.assertIsNotNone(read.call_args.kwargs["on_idle"])
        self.assertEqual(read.call_args.kwargs["idle_interval"], animation._SPARKLE_FRAME)

    def test_idle_refresh_hides_terminal_cursor_until_input_is_redrawn(self):
        events: list[str] = []
        with patch("sys.stdout.isatty", return_value=True), \
             patch("sys.stdout.write") as write, patch("sys.stdout.flush"):
            terminal_input._refresh_idle(
                lambda value: events.append(f"paint:{value}"),
                "abc",
                lambda: events.append("redraw"),
            )

        self.assertEqual(events, ["paint:abc", "redraw"])
        self.assertEqual(write.call_args_list[0].args[0], "\x1b[?25l")
        self.assertEqual(write.call_args_list[-1].args[0], "\x1b[?25h")


if __name__ == "__main__":
    unittest.main()
