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

    def test_footer_is_one_stable_navigation_contract(self):
        expected = ("方向键 移动", "Enter 打开", "Esc 返回")
        for animate in (True, False):
            frame = self.render((120, 36), animate=animate)
            footer = self.plain(frame.lines[-1])
            for hint in expected:
                self.assertIn(hint, footer)
            self.assertFalse(any(region.y == 36 for region in frame.regions))

    def test_narrow_footer_is_clipped_without_changing_wording(self):
        footer = self.plain(self.render((30, 12)).lines[-1])
        self.assertTrue(footer.startswith("[ 方向键 移动 ]"))
        self.assertNotIn("确认", footer)


if __name__ == "__main__":
    unittest.main()
