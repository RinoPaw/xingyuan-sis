import os
import unittest
from unittest.mock import patch

from xingyuan_sis.tui import animation, screen, theme


LABELS = ("学生", "教务", "课程", "成绩", "数据", "退出")
STATS = {"students": 100, "classes": 26, "courses": 20, "enrollments": 400}


class HomeLayoutTests(unittest.TestCase):
    def render(self, size=(80, 36), *, animate=True):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return theme.home_frame(LABELS, 0, STATS, 0, animate=animate)

    def plain(self, text: str) -> str:
        return screen._ANSI_RE.sub("", text)

    def test_sidebar_overview_uses_one_metric_per_line(self):
        frame = self.render((65, 36))
        lines = [self.plain(line) for line in frame.lines]
        positions = []
        for label, value in (("学生", 100), ("班级", 26), ("课程", 20), ("选课", 400)):
            matches = [i for i, line in enumerate(lines) if f"{label}  {value}" in line]
            self.assertEqual(len(matches), 1)
            positions.append(matches[0])
        self.assertEqual(positions, list(range(positions[0], positions[0] + 4)))

    def test_coordinate_layout_leaves_visual_gaps_available_to_starlight(self):
        frame = self.render((120, 36))
        lines = [self.plain(line) for line in frame.lines]
        dots = set(animation._SPARKLE_DOTS)

        sidebar_rows = [line.split("│", 1)[0] for line in lines[2:8]]
        self.assertTrue(any(char in dots for line in sidebar_rows for char in line))

        right_title = lines[1].split("│", 1)[1]
        self.assertTrue(any(char in dots for char in right_title))

    def test_home_footer_only_describes_keyboard_actions(self):
        footer = self.plain(self.render((120, 36)).lines[-1])
        self.assertIn("↑↓ 移动", footer)
        self.assertIn("Enter 打开", footer)
        self.assertIn("p 暂停动画", footer)
        self.assertIn("Esc 退出", footer)
        self.assertNotIn("滚轮", footer)
        self.assertNotIn("点击", footer)

        paused = self.plain(self.render((120, 36), animate=False).lines[-1])
        self.assertIn("p 播放动画", paused)

    def test_minimum_footer_keeps_all_essential_keys(self):
        footer = self.plain(self.render((30, 12)).lines[-1])
        for hint in ("↑↓", "↵", "p", "Esc退"):
            self.assertIn(hint, footer)


if __name__ == "__main__":
    unittest.main()
