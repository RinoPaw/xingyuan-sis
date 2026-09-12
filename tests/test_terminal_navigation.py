from contextlib import nullcontext, redirect_stdout
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis import basic_ui, terminal_ui
from xingyuan_sis.tui import app as menu, screen, keys, animation, theme
from xingyuan_sis.database import initialize_database


class BreadcrumbTests(unittest.TestCase):
    def test_home_name_matches_breadcrumb_in_both_menus(self):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 24))):
            home = menu._home_frame(("学生", "教务", "课程", "成绩", "数据", "退出"), 0, {}, 0)
            child, _ = screen._breadcrumb("学生", 79)
        self.assertIn("首页", home.lines[1])
        self.assertIn("首页 / 学生", child)
        with patch.object(basic_ui, "_clear"), patch("builtins.input", return_value="q"), \
             redirect_stdout(StringIO()) as output:
            basic_ui.run()
        self.assertIn("教务台\n首页\n", output.getvalue())
        self.assertNotIn("工作区", output.getvalue())

    def test_only_visible_ancestor_labels_are_clickable(self):
        for width in (3, 4, 8, 10, 18, 30, 80):
            with self.subTest(width=width):
                line, regions = screen._breadcrumb("教务 / 班级", width)
                self.assertLessEqual(screen._display_width(line), width)
                for region in regions:
                    self.assertLessEqual(region.x + region.width - 1, width)
                    for cell in range(region.x, region.x + region.width):
                        self.assertEqual(screen._hit_action(keys.MouseClick(cell, 2), regions), region.action)
                self.assertIsNone(screen._hit_action(keys.MouseClick(6, 2), regions))  # separator
                self.assertIsNone(screen._hit_action(keys.MouseClick(15, 2), regions))  # current page
                self.assertEqual([region.action for region in regions],
                                 ([] if width < 4 else ["navigate:"] if width < 11
                                  else ["navigate:", "navigate:教务"]))

    def test_query_titles_include_academic_entity(self):
        for entity, label in (("college", "学院"), ("major", "专业"), ("class", "班级")):
            self.assertEqual(terminal_ui._command_title(["acad", entity, "ls"]), f"教务 / {label} / 列表")


class TerminalSurfaceTests(unittest.TestCase):
    def test_screen_is_restored_on_exit_or_failure_without_mutating_terminal_palette(self):
        for failure in (None, KeyboardInterrupt, EOFError, RuntimeError):
            with self.subTest(failure=failure), redirect_stdout(StringIO()) as output, \
                 patch("sys.stdout.isatty", return_value=True), patch("sys.stdin.isatty", return_value=True), \
                 patch.dict(os.environ), patch.object(menu, "_home", side_effect=failure, return_value=None):
                os.environ.pop("NO_COLOR", None)
                if failure is RuntimeError:
                    with self.assertRaises(RuntimeError):
                        menu.run()
                else:
                    menu.run()
            rendered = output.getvalue()
            self.assertIn("\x1b[?1049h", rendered)
            self.assertTrue(rendered.endswith("\x1b[0m\x1b[?1049l\x1b[?25h"))
            self.assertNotIn("\x1b]11;", rendered)
            self.assertNotIn("\x1b]111", rendered)

    def test_no_color_does_not_change_terminal_palette(self):
        with redirect_stdout(StringIO()) as output, patch("sys.stdout.isatty", return_value=True), \
             patch("sys.stdin.isatty", return_value=True), patch.dict(os.environ, {"NO_COLOR": "1"}), \
             patch.object(menu, "_home", return_value=None):
            menu.run()
        self.assertNotIn("\x1b]", output.getvalue())
        self.assertNotIn("48;", output.getvalue())
        self.assertIn("\x1b[?1049l", output.getvalue())

    def test_clear_and_resize_erase_with_surface_color(self):
        with redirect_stdout(StringIO()) as output, patch("sys.stdout.isatty", return_value=True), \
             patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            screen._clear()
            screen._paint(["wide first row", "", "footer"])
            screen._paint(["short", ""], ["wide first row", "", "footer"])
        self.assertEqual(output.getvalue().count(screen._RESET + screen._SURFACE + "\x1b[2J"), 3)
        self.assertNotIn(screen._RESET + "\x1b[2J", output.getvalue())


if __name__ == "__main__":
    unittest.main()
