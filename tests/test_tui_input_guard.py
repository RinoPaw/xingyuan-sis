import ast
from contextlib import nullcontext
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from xingyuan_sis import terminal_input
from xingyuan_sis.auth import ADMIN_USERNAME
from xingyuan_sis import tui
from xingyuan_sis.tui import auth_view, screen
from xingyuan_sis.tui.text_edit import TextBuffer, TextEvent


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
        self.assertEqual(
            offenders,
            [],
            "TUI text fields must use the shared text editor: " + ", ".join(offenders),
        )

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

    def test_tui_editor_forwards_nonempty_initial_value(self):
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), \
             patch.object(terminal_input, "_read_interactive_line", return_value=ADMIN_USERNAME) as read, \
             patch("sys.stdout.write"), patch("sys.stdout.flush"), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            with terminal_input.input_style(True):
                value = terminal_input.read_input("账号: ", initial_value=ADMIN_USERNAME)
        self.assertEqual(value, ADMIN_USERNAME)
        read.assert_called_once_with("账号: ", colored=True, initial_value=ADMIN_USERNAME)

    def test_shared_text_buffer_owns_value_cursor_and_editing(self):
        buffer = TextBuffer.from_value("Admin")
        buffer.apply(TextEvent("left"))
        buffer.apply(TextEvent("left"))
        buffer.apply(TextEvent("insert", "X"))
        self.assertEqual(buffer.value, "AdmXin")
        self.assertEqual(buffer.cursor, 4)
        buffer.apply(TextEvent("backspace"))
        self.assertEqual(buffer.value, "Admin")
        self.assertEqual(buffer.cursor, 3)

    def test_auth_form_uses_one_state_loop_for_prefill_and_submission(self):
        events = [
            TextEvent("submit"),
            TextEvent("insert", "s"),
            TextEvent("insert", "e"),
            TextEvent("insert", "c"),
            TextEvent("submit"),
        ]
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 24))), \
             patch.object(screen, "_paint") as paint, patch("sys.stdout.isatty", return_value=False), \
             patch.object(auth_view, "input_mode", return_value=nullcontext()), \
             patch.object(auth_view, "read_event", side_effect=events):
            result = auth_view._run_form(
                "login",
                {"username": ADMIN_USERNAME, "password": ""},
                database="test.db",
            )

        self.assertEqual(result, {"username": ADMIN_USERNAME, "password": "sec"})
        self.assertGreaterEqual(paint.call_count, len(events))

    def test_auth_form_repaints_animation_on_idle_without_a_second_renderer(self):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 24))), \
             patch.object(screen, "_paint") as paint, patch("sys.stdout.isatty", return_value=False), \
             patch.object(auth_view, "input_mode", return_value=nullcontext()), \
             patch.object(auth_view, "read_event", side_effect=[None, TextEvent("cancel")]):
            result = auth_view._run_form(
                "login",
                {"username": ADMIN_USERNAME, "password": ""},
                database="test.db",
            )

        self.assertIsNone(result)
        self.assertGreaterEqual(paint.call_count, 2)

    def test_form_paint_hides_cursor_during_frame_then_restores_it_at_field(self):
        events: list[str] = []

        def fake_paint(_lines, _previous):
            events.append("paint")

        with patch("sys.stdout.isatty", return_value=True), \
             patch.object(screen, "_paint", side_effect=fake_paint), \
             patch("sys.stdout.write") as write, patch("sys.stdout.flush"):
            auth_view._paint_form(["row"], [], (12, 7))

        self.assertEqual(events, ["paint"])
        self.assertEqual(write.call_args_list[0].args[0], "\x1b[?25l")
        self.assertEqual(write.call_args_list[-1].args[0], "\x1b[8;13H\x1b[?25h")

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
