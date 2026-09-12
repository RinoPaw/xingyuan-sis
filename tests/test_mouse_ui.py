from contextlib import redirect_stdout
from io import StringIO
import os
import unittest
from unittest.mock import patch

from xingyuan_sis import terminal_input
from xingyuan_sis.tui import app as menu, screen, keys, animation, theme, viewer as terminal_viewer

LABELS = ("学生", "教务", "课程", "成绩", "数据", "退出")


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

    def test_home_click_regions_follow_reflow(self):
        for size in ((80, 24), (40, 16), (30, 12), (120, 36)):
            with self.subTest(size=size), patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
                frame = menu._home_frame(LABELS, 0, {}, 0)
            items = [r for r in frame.regions if r.action.startswith("item:")]
            self.assertEqual(len(items), len(LABELS))
            for region in items:
                number = int(region.action.split(":")[1])
                self.assertIn(LABELS[number], screen._ANSI_RE.sub("", frame.lines[region.y - 1]))
                self.assertEqual(screen._hit_action(keys.MouseClick(region.x, region.y), frame.regions), region.action)
                self.assertLess(region.y, size[1])
                self.assertLessEqual(region.x + region.width, size[0])
            if size[0] < 39:
                self.assertEqual(items[0].y, items[1].y)
            else:
                self.assertNotEqual(items[0].y, items[1].y)


    def test_starlight_preserves_text_and_clickable_regions(self):
        base = [" " * 79 for _ in range(20)]
        base[5] = "学生姓名 林岚" + " " * 60
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
            bar = theme.home_footer(79, 1, True)[0]
        self.assertNotIn("44m", bar)
        self.assertTrue(all(232 <= int(color) <= 238 for color in screen.re.findall(r"48;5;(\d+)m", bar)))

    def test_gray_surface_is_reapplied_after_inline_style_reset(self):
        with redirect_stdout(StringIO()) as output, patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            screen._paint([screen._ansi("学生", screen._SELECTED) + " rest"])
        self.assertIn(screen._RESET + screen._SURFACE + " rest", output.getvalue())
        self.assertIn(screen._SURFACE + "\x1b[2K", output.getvalue())


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

    def test_viewer_footer_can_be_clicked(self):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 10))), \
             patch.object(keys, "_read_key", side_effect=[keys.MouseClick(40, 10), "back"]), \
             patch.object(screen, "_paint") as paint:
            terminal_viewer.show("\n".join(f"row-{i:02d}" for i in range(20)), "学生")
        self.assertIn("row-06", "".join(paint.call_args_list[1].args[0]))

    def test_native_input_keeps_chinese_and_resets_color_on_cancel(self):
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), \
             patch("builtins.input", return_value="林岚") as read, redirect_stdout(StringIO()) as output, \
             patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            with patch("sys.stdout.isatty", return_value=True):
                with terminal_input.input_style(True):
                    self.assertEqual(terminal_input.read_input("姓名: "), "林岚")
            self.assertIn("48;5;235m", read.call_args.args[0])
            self.assertTrue(output.getvalue().endswith("\x1b[0m"))
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt), terminal_input.input_style(True):
                terminal_input.read_input("姓名: ")
        self.assertFalse(terminal_input._ACTIVE.get())

    def test_cli_prompts_remain_plain(self):
        with patch("builtins.input", return_value="林岚") as read:
            self.assertEqual(terminal_input.read_input("姓名: "), "林岚")
        read.assert_called_once_with("姓名: ")
