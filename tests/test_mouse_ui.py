from contextlib import redirect_stdout
from io import StringIO
import os
import unittest
from unittest.mock import patch

from xingyuan_sis import menu, terminal_input, terminal_viewer

LABELS = ("学生", "教务", "课程", "成绩", "数据", "退出")


class MouseAndLayoutTests(unittest.TestCase):
    def test_sgr_click_activates_on_release_only(self):
        self.assertEqual(menu._mouse_event(b"[<0;20;8M"), "other")
        self.assertEqual(menu._mouse_event(b"[<0;20;8m"), menu.MouseClick(20, 8))
        self.assertEqual(menu._mouse_event(b"[<64;20;8M"), "up")
        self.assertEqual(menu._mouse_event(b"[<65;20;8M"), "down")
        for invalid in (b"[<0;0;8m", b"[<2;20;8m", b"[<32;20;8M", b"[<oopsM"):
            self.assertEqual(menu._mouse_event(invalid), "other")

    def test_mouse_mode_is_restored_when_action_is_cancelled(self):
        with redirect_stdout(StringIO()) as output, patch("sys.stdout.isatty", return_value=True), \
             patch("sys.stdin.isatty", return_value=True), patch.object(menu.os, "name", "posix"):
            with self.assertRaises(KeyboardInterrupt):
                with menu._mouse_tracking():
                    raise KeyboardInterrupt
        self.assertIn("\x1b[?1006h", output.getvalue())
        self.assertTrue(output.getvalue().endswith("\x1b[?1000l\x1b[?1006l\x1b[?25h"))

    def test_home_click_regions_follow_reflow(self):
        for size in ((80, 24), (40, 16), (30, 12), (120, 36)):
            with self.subTest(size=size), patch.object(menu, "_terminal_size", return_value=os.terminal_size(size)):
                frame = menu._home_frame(LABELS, 0, {}, 0)
            items = [r for r in frame.regions if r.action.startswith("item:")]
            self.assertEqual(len(items), len(LABELS))
            for region in items:
                number = int(region.action.split(":")[1])
                self.assertIn(LABELS[number], menu._ANSI_RE.sub("", frame.lines[region.y - 1]))
                self.assertEqual(menu._hit_action(menu.MouseClick(region.x, region.y), frame.regions), region.action)
                self.assertLess(region.y, size[1])
                self.assertLessEqual(region.x + region.width, size[0])
            if size[0] < 50:
                self.assertEqual(items[0].y, items[1].y)
            else:
                self.assertNotEqual(items[0].y, items[1].y)

    def test_click_opens_submenu_item_after_resize(self):
        sizes = [os.terminal_size((100, 30)), os.terminal_size((32, 12))]
        with patch.object(menu, "_terminal_size", side_effect=sizes), \
             patch.object(menu, "_read_key", side_effect=[None, menu.MouseClick(4, 5)]), \
             patch.object(menu, "_paint") as paint:
            selected = menu._select("学生", ["学生列表", "查看学生", "编辑学生"])
        self.assertEqual(selected, 1)
        self.assertEqual(len(paint.call_args_list[0].args[0]), 30)
        self.assertEqual(len(paint.call_args_list[1].args[0]), 12)

    def test_short_submenu_scrolls_selected_item_into_view(self):
        with patch.object(menu, "_terminal_size", return_value=os.terminal_size((32, 8))):
            frame = menu._selection_frame("学生", [f"项目{i}" for i in range(9)], 8, "返回")
        self.assertEqual(len(frame.lines), 8)
        self.assertIn("项目8", "".join(frame.lines))
        self.assertTrue(any(r.action == "item:8" and r.y < 8 for r in frame.regions))

    def test_starlight_preserves_text_and_clickable_regions(self):
        base = [" " * 79 for _ in range(20)]
        base[5] = "学生姓名 林岚" + " " * 60
        protected = menu.HitRegion(1, 6, 79, "item:0")
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            first = menu._starlight(menu.ScreenFrame(base.copy(), [protected]), 79, 0)
            second = menu._starlight(menu.ScreenFrame(base.copy(), [protected]), 79, 1.7)
        self.assertNotEqual(first.lines, second.lines)
        self.assertEqual(first.lines[5], base[5])
        self.assertEqual(first.lines[-1], base[-1])
        self.assertEqual(first.regions, second.regions)
        self.assertTrue(all(menu._display_width(a) == menu._display_width(b) for a, b in zip(base, first.lines)))

    def test_footer_has_no_bright_background(self):
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            bar = menu._bottom_bar(79, True)
        self.assertNotIn("44m", bar)
        self.assertNotIn("48;", bar)
        self.assertIn("38;5;245m", bar)

    def test_gray_surface_is_reapplied_after_inline_style_reset(self):
        with redirect_stdout(StringIO()) as output, patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            menu._paint([menu._ansi("学生", menu._SELECTED) + " rest"])
        self.assertIn(menu._RESET + menu._SURFACE + " rest", output.getvalue())
        self.assertIn(menu._SURFACE + "\x1b[2K", output.getvalue())


class ViewerAndInputTests(unittest.TestCase):
    def test_viewer_pages_and_reflows_while_waiting(self):
        sizes = [os.terminal_size((80, 10)), os.terminal_size((30, 12)), os.terminal_size((30, 12))]
        with patch.object(menu, "_terminal_size", side_effect=sizes), \
             patch.object(menu, "_read_key", side_effect=["select", None, "back"]), \
             patch.object(menu, "_paint") as paint:
            terminal_viewer.show("\n".join(f"row-{i:02d} 学生信息" for i in range(20)), "学生 / 列表")
        first, second = (call.args[0] for call in paint.call_args_list)
        self.assertEqual(len(first), 10)
        self.assertEqual(len(second), 12)
        self.assertIn("row-06", "".join(second))
        self.assertTrue(all(menu._display_width(line) < 30 for line in second))

    def test_scroll_down_on_last_partial_page_never_moves_backwards(self):
        with patch.object(menu, "_terminal_size", return_value=os.terminal_size((80, 10))), \
             patch.object(menu, "_read_key", side_effect=["select", "down", "back"]), \
             patch.object(menu, "_paint") as paint:
            terminal_viewer.show("\n".join(f"row-{i:02d}" for i in range(10)), "学生")
        self.assertIn("row-07", "".join(paint.call_args_list[-1].args[0]))
        self.assertNotIn("row-06", "".join(paint.call_args_list[-1].args[0]))

    def test_viewer_footer_can_be_clicked(self):
        with patch.object(menu, "_terminal_size", return_value=os.terminal_size((80, 10))), \
             patch.object(menu, "_read_key", side_effect=[menu.MouseClick(13, 10), "back"]), \
             patch.object(menu, "_paint") as paint:
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
