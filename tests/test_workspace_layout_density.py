from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import os

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen
from xingyuan_sis.tui.layout import WorkspaceLayout
from xingyuan_sis.tui.workspace import student_inspector
from xingyuan_sis.tui.workspace.state import Workspace
from xingyuan_sis.tui.workspace.view import workspace_layout
from xingyuan_sis.tui.workspace.data import Catalog


class WorkspaceLayoutDensityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / "test.db"
        initialize_database(db)
        seed_demo(db)
        self.catalog = Catalog(db)

    def test_wide_split_keeps_roster_dense_and_inspector_content_sized(self):
        layout = WorkspaceLayout(160, 35, 28)
        self.assertEqual(layout.split_x, 72)
        self.assertEqual(layout.panel_width, 28)
        self.assertLess(layout.split_x, layout.width // 2)

    def test_wide_split_caps_both_panels_instead_of_stretching_across_terminal(self):
        layout = WorkspaceLayout(160, 35)
        self.assertEqual(layout.split_x, 72)
        self.assertEqual(layout.panel_width, 42)
        self.assertLess(layout.panel_x + layout.panel_width, layout.width)

    def test_medium_split_stays_balanced_when_content_is_wide(self):
        layout = WorkspaceLayout(80, 30, 42)
        self.assertEqual(layout.split_x, 40)
        self.assertEqual(layout.panel_width, 36)

    def test_student_inspector_width_tracks_actual_content(self):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((160, 35))):
            width = workspace_layout(Workspace("students"), self.catalog).inspector_width
        self.assertGreaterEqual(width, 28)
        self.assertLessEqual(width, 42)

    def test_class_relationship_uses_major_and_local_number_once(self):
        row = next(row for row in self.catalog.rows("students") if row.get("class_code"))
        self.assertEqual(row["class_label"], f"{row['major_name']} · {row['class_number']}")
        self.assertNotIn(str(row["class_code"]), str(row["class_label"]))
        self.assertNotIn("班", str(row["class_label"]))

        labels = dict(self.catalog.options("students", "class_code", row) or [])
        self.assertEqual(labels[row["class_code"]], row["class_label"])

    def test_student_inspector_summary_matches_archive_identity(self):
        row = self.catalog.rows("students")[0]
        rendered = student_inspector.lines(row, self.catalog)
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
        self.assertIn(str(row["class_label"]), summary)
        self.assertIn("学籍", summary)
        self.assertIn("元素", summary)


if __name__ == "__main__":
    unittest.main()
