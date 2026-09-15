from contextlib import redirect_stdout
from io import StringIO
import os
import unittest
from unittest.mock import patch

from xingyuan_sis import terminal_input
from xingyuan_sis.tui import screen, keys, animation, theme, text_edit, viewer as terminal_viewer


class MouseAndLayoutTests(unittest.TestCase):
    def test_sgr_click_activates_on_release_only(self):
        self.assertEqual(keys._mouse_event(b"[<0;20;8M"), "other")
        self.assertEqual(keys._mouse_event(b"[<0;20;8m"), keys.MouseClick(20, 8))
        self.assertEqual(keys._mouse_event(b"[<64;20;8M"), keys.MouseScroll(20, 8, "up"))
        self.assertEqual(keys._mouse_event(b"[<65;20;8M"), keys.MouseScroll(20, 8, "down"))
        for invalid in (b"[<0;0;8m", b"[<2;20;8m", b"[<32;20;8M", b"[<oopsM"):
            self.assertEqual(keys._mouse_event(invalid), "other")

    @unittest.skipIf(os.name == "nt", "POSIX terminal modes")
    def test_mouse_reports_do_not_echo_between_reads_and_cancel_restores_input(self):
        import pty
        import termios

        master, slave = pty.openpty()
        try:
            previous = termios.tcgetattr(slave)
            with redirect_stdout(StringIO()) as output, patch("sys.stdout.isatty", return_value=True), \
                 patch("sys.stdin.isatty", return_value=True), patch("sys.stdin.fileno", return_value=slave):
                with self.assertRaises(KeyboardInterrupt):
                    with keys._mouse_tracking():
                        self.assertFalse(termios.tcgetattr(slave)[3] & (termios.ECHO | termios.ICANON))
                        os.write(master, b"\x1b[<0;2;2m")
                        self.assertEqual(keys._read_key_posix(0.5), keys.MouseClick(2, 2))
                        self.assertFalse(termios.tcgetattr(slave)[3] & (termios.ECHO | termios.ICANON))
                        raise KeyboardInterrupt
            self.assertEqual(termios.tcgetattr(slave), previous)
            self.assertIn("\x1b[?1006h", output.getvalue())
            self.assertTrue(output.getvalue().endswith("\x1b[?1000l\x1b[?1006l\x1b[?25h"))
        finally:
            os.close(master)
            os.close(slave)

    def test_starlight_preserves_text_and_clickable_regions(self):
        base = [" " * 79 for _ in range(20)]
        base[5] = "学生姓名 测试" + " " * 60
        protected = screen.HitRegion(1, 6, 79, "item:0")
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            first = animation._starlight(screen.ScreenFrame(base.copy(), [protected]), 79, 0)
            second = animation._starlight(screen.ScreenFrame(base.copy(), [protected]), 79, 1.7)
        self.assertNotEqual(first.lines, second.lines)
        self.assertEqual(first.lines[5], base[5])
        self.assertEqual(first.lines[-1], base[-1])
        self.assertEqual(first.regions, second.regions)
        self.assertTrue(all(screen._display_width(a) == screen._display_width(b) for a, b in zip(base, first.lines)))

    def test_footer_uses_dark_gray_backgrounds(self):
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            bar = theme.footer(79)
        self.assertNotIn("44m", bar)
        self.assertTrue(all(232 <= int(color) <= 238 for color in screen.re.findall(r"48;5;(\d+)m", bar)))

    def test_page_surface_is_reapplied_after_inline_style_reset(self):
        page_style = screen._SURFACE_DEFAULT + screen._TEXT_PRIMARY
        selected_style = screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
        with redirect_stdout(StringIO()) as output, patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            screen._paint([screen._ansi("学生", selected_style) + " rest"])
        self.assertIn(screen._RESET + page_style + " rest", output.getvalue())
        self.assertIn(page_style + "\x1b[2K", output.getvalue())


class ViewerAndInputTests(unittest.TestCase):
    def test_viewer_pages_and_reflows_while_waiting(self):
        sizes = [os.terminal_size((80, 10)), os.terminal_size((30, 12)), os.terminal_size((30, 12))]
        with patch.object(screen, "_terminal_size", side_effect=sizes), \
             patch.object(keys, "_read_key", side_effect=["select", None, "back"]), \
             patch.object(screen, "_paint") as paint:
            terminal_viewer.show("\n".join(f"row-{i:02d} 学生信息" for i in range(20)), "学生 / 列表")
        first, second = (call.args[0] for call in paint.call_args_list)
        self.assertEqual(len(first), 10)
        self.assertEqual(len(second), 12)
        self.assertIn("row-06", "".join(second))
        self.assertTrue(all(screen._display_width(line) < 30 for line in second))

    def test_scroll_down_on_last_partial_page_never_moves_backwards(self):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 10))), \
             patch.object(keys, "_read_key", side_effect=["select", "down", "back"]), \
             patch.object(screen, "_paint") as paint:
            terminal_viewer.show("\n".join(f"row-{i:02d}" for i in range(10)), "学生")
        self.assertIn("row-07", "".join(paint.call_args_list[-1].args[0]))
        self.assertNotIn("row-06", "".join(paint.call_args_list[-1].args[0]))

    def test_viewer_footer_is_not_clickable(self):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 10))), \
             patch.object(keys, "_read_key", side_effect=[keys.MouseClick(40, 10), "back"]), \
             patch.object(screen, "_paint") as paint:
            terminal_viewer.show("\n".join(f"row-{i:02d}" for i in range(20)), "学生")
        self.assertEqual(len(paint.call_args_list), 1)
        self.assertIn("row-00", "".join(paint.call_args_list[0].args[0]))

    def test_native_input_keeps_chinese_and_resets_color_on_cancel(self):
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), \
             patch.object(terminal_input, "_read_interactive_line", return_value="测试") as read, \
             patch("sys.stdout.write") as write, patch("sys.stdout.flush"), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            with terminal_input.input_style(True):
                self.assertEqual(terminal_input.read_input("姓名: "), "测试")
            read.assert_called_once_with("姓名: ", colored=True)
            self.assertEqual(write.call_args_list[-1].args[0], "\x1b[0m")

        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), \
             patch.object(terminal_input, "_read_interactive_line", side_effect=KeyboardInterrupt), \
             patch.dict(os.environ, {"NO_COLOR": "1"}):
            with self.assertRaises(KeyboardInterrupt), terminal_input.input_style(True):
                terminal_input.read_input("姓名: ")
        self.assertFalse(terminal_input._ACTIVE.get())

    @unittest.skipIf(os.name == "nt", "POSIX line editor")
    def test_tui_line_editor_bare_escape_cancels_and_tab_never_completes(self):
        import termios
        import tty

        with patch("sys.stdin.isatty", return_value=True), \
             patch("sys.stdin.fileno", return_value=10), \
             patch("termios.tcgetattr", return_value=[1, 2, 3]), \
             patch("tty.setcbreak") as cbreak, patch("termios.tcsetattr") as restore, \
             patch("os.read", side_effect=[b"\t", b"\x1b"]), \
             patch.object(text_edit, "_read_escape_sequence", return_value=b""):
            with text_edit.input_mode():
                self.assertEqual(text_edit.read_event().kind, "tab")
                self.assertEqual(text_edit.read_event().kind, "cancel")
        cbreak.assert_called_once_with(10, termios.TCSANOW)
        restore.assert_called_once()

    @unittest.skipIf(os.name == "nt", "POSIX line editor")
    def test_tui_line_editor_accepts_utf8_and_cursor_navigation(self):
        import termios
        import tty

        chinese = list("林岚".encode("utf-8"))
        reads = [bytes([byte]) for byte in chinese] + [b"\x1b", b"X", b"\r"]
        buffer = text_edit.TextBuffer.from_value()
        with patch("sys.stdin.isatty", return_value=True), \
             patch("sys.stdin.fileno", return_value=10), \
             patch("termios.tcgetattr", return_value=[1, 2, 3]), \
             patch("tty.setcbreak"), patch("termios.tcsetattr"), \
             patch("os.read", side_effect=reads), \
             patch.object(text_edit, "_read_escape_sequence", return_value=b"[D"):
            with text_edit.input_mode():
                while True:
                    event = text_edit.read_event()
                    action = buffer.apply(event)
                    if action == "submit":
                        break
        self.assertEqual(buffer.value, "林X岚")

    def test_cli_prompts_remain_plain(self):
        with patch("builtins.input", return_value="测试") as read:
            self.assertEqual(terminal_input.read_input("姓名: "), "测试")
        read.assert_called_once_with("姓名: ")


if __name__ == "__main__":
    unittest.main()
