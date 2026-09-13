from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen, workspace_view
from xingyuan_sis.tui.layout import WorkspaceLayout
from xingyuan_sis.tui.workspace_data import Catalog


class WorkspaceLayoutDensityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / "test.db"
        initialize_database(db)
        seed_demo(db)
        self.catalog = Catalog(db)

    def test_wide_split_caps_inspector_and_gives_surplus_to_roster(self):
        layout = WorkspaceLayout(160, 35)
        self.assertEqual(layout.split_x, 114)
        self.assertEqual(layout.panel_width, 42)
        self.assertGreater(layout.split_x, layout.width * 2 // 3)

    def test_medium_split_stays_balanced_before_inspector_cap(self):
        layout = WorkspaceLayout(80, 30)
        self.assertEqual(layout.split_x, 40)
        self.assertEqual(layout.panel_width, 36)

    def test_student_inspector_does_not_repeat_roster_fields(self):
        row = self.catalog.records["students"][0]
        rendered = workspace_view._details("students", row, self.catalog, 60)
        plain = "\n".join(screen._ANSI_RE.sub("", text) for text, _, _ in rendered)
        summary = plain.split("选课与成绩", 1)[0]

        self.assertIn(row["name"], summary)
        self.assertIn("物种", summary)
        self.assertIn("入学", summary)
        self.assertIn("亲和", summary)
        self.assertIn("学院", summary)
        self.assertNotIn(str(row["student_no"]), summary)
        self.assertNotIn(str(row["class_name"]), summary)
        self.assertNotIn(str(row["status"]), summary)
        self.assertNotIn(str(row["primary_element"]), summary)


if __name__ == "__main__":
    unittest.main()
