from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen
from xingyuan_sis.tui.layout import WorkspaceLayout
from xingyuan_sis.tui.workspace import student_inspector
from xingyuan_sis.tui.workspace.data import Catalog


class WorkspaceLayoutDensityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / "test.db"
        initialize_database(db)
        seed_demo(db)
        self.catalog = Catalog(db)

    def test_wide_split_uses_current_inspector_width(self):
        layout = WorkspaceLayout(160, 35, 28)
        self.assertEqual(layout.split_x, 128)
        self.assertEqual(layout.panel_width, 28)
        self.assertGreater(layout.split_x, layout.width * 3 // 4)

    def test_wide_split_keeps_fallback_cap_without_hint(self):
        layout = WorkspaceLayout(160, 35)
        self.assertEqual(layout.split_x, 114)
        self.assertEqual(layout.panel_width, 42)

    def test_medium_split_stays_balanced_when_content_is_wide(self):
        layout = WorkspaceLayout(80, 30, 42)
        self.assertEqual(layout.split_x, 40)
        self.assertEqual(layout.panel_width, 36)

    def test_student_inspector_width_tracks_actual_content(self):
        row = self.catalog.records["students"][0]
        width = student_inspector.preferred_width(row, self.catalog)
        self.assertGreaterEqual(width, 28)
        self.assertLessEqual(width, 42)

    def test_student_inspector_summary_matches_archive_identity(self):
        row = self.catalog.records["students"][0]
        rendered = student_inspector._lines(row, self.catalog)
        plain = "\n".join(
            screen._ANSI_RE.sub("", "".join(text for text, _, _ in line))
            for line in rendered
        )
        summary = plain.split("选课与成绩", 1)[0]

        self.assertIn(row["name"], summary)
        self.assertIn(str(row["student_no"]), summary)
        self.assertIn("物种", summary)
        self.assertIn("性别", summary)
        self.assertIn("年龄", summary)
        self.assertIn("入学", summary)
        self.assertIn("学院", summary)
        self.assertIn("班级", summary)
        self.assertIn("学籍", summary)
        self.assertIn("元素", summary)


if __name__ == "__main__":
    unittest.main()
