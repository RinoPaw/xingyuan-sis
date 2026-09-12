from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace, workspace_view
from xingyuan_sis.tui.workspace_data import ACADEMICS, Catalog


WORKSPACES = ("students", "departments", "majors", "classes", "courses", "grades", "data")
RECORD_WORKSPACES = tuple(key for key in WORKSPACES if key != "data")


class TuiRegressionAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def render(self, state: workspace.Workspace):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ) as environment:
            environment.pop("NO_COLOR", None)
            return workspace_view.render(state, self.catalog)

    def test_every_workspace_footer_uses_the_same_visible_escape_contract(self):
        for key in WORKSPACES:
            with self.subTest(key=key):
                frame = self.render(workspace.Workspace(key))
                footer = screen._ANSI_RE.sub("", frame.lines[-1])
                self.assertIn("Esc", footer)
                self.assertNotIn("Ctrl+C", footer)
                self.assertNotIn("q/", footer)
                self.assertNotIn("/q", footer)

    def test_every_record_workspace_distinguishes_focused_and_context_selection(self):
        for key in RECORD_WORKSPACES:
            with self.subTest(key=key), patch("sys.stdout.isatty", return_value=True), \
                 patch.dict(os.environ) as environment:
                environment.pop("NO_COLOR", None)

                state = workspace.Workspace(key)
                focused = workspace_view.Board(60, 35)
                workspace_view._roster(focused, state, self.catalog, 59)
                focused_line = focused.frame().lines[10]
                self.assertIn(screen._SURFACE_SELECTED, focused_line)

                state.details = True
                context = workspace_view.Board(60, 35)
                workspace_view._roster(context, state, self.catalog, 59)
                context_line = context.frame().lines[10]
                self.assertIn(screen._SURFACE_INTERACTIVE, context_line)
                self.assertNotIn(screen._SURFACE_SELECTED, context_line)

                inspector = workspace_view.Board(60, 35)
                workspace_view._inspector(inspector, state, self.catalog, 1, 55)
                detail_lines = inspector.frame().lines
                targets = workspace_view.detail_targets(key, state.current(self.catalog), self.catalog, 55)
                self.assertTrue(targets)
                selected_line = 9 + targets[state.detail_selected][0] - state.detail_scroll
                self.assertIn(screen._SURFACE_SELECTED, detail_lines[selected_line])

    def test_counts_stay_attached_to_their_matching_views(self):
        for key in ("students", "courses", "grades"):
            with self.subTest(key=key):
                state = workspace.Workspace(key)
                frame = self.render(state)
                choice_row = screen._ANSI_RE.sub("", frame.lines[4])
                for index in range(3):
                    expected = len(self.catalog.rows(key, index, state.query))
                    self.assertIn(f"· {expected}", choice_row)

        for key in ACADEMICS:
            with self.subTest(key=key):
                frame = self.render(workspace.Workspace(key))
                choice_row = screen._ANSI_RE.sub("", frame.lines[4])
                for collection in ACADEMICS:
                    self.assertIn(f"· {len(self.catalog.records[collection])}", choice_row)

        data = screen._ANSI_RE.sub("", self.render(workspace.Workspace("data")).lines[4])
        self.assertIn("学生", data)
        self.assertIn(str(len(self.catalog.records["students"])), data)

    def test_escape_cancels_edit_forms_without_writing_on_every_record_page(self):
        for key in RECORD_WORKSPACES:
            with self.subTest(key=key):
                state = workspace.Workspace(key)
                before = deepcopy(state.current(self.catalog))
                workspace._open_form(state, self.catalog, "edit")
                self.assertIsNotNone(state.form)

                with patch.object(keys, "_read_key", side_effect=["back", "back"]), \
                     patch.object(screen, "_paint"), \
                     patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
                    self.assertIsNone(workspace._interact(state, self.catalog))

                self.assertIsNone(state.form)
                self.assertEqual(state.current(self.catalog), before)

    def test_escape_unwinds_detail_focus_before_leaving_workspace(self):
        state = workspace.Workspace("students", details=True)
        with patch.object(keys, "_read_key", side_effect=["back", "back"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            self.assertIsNone(workspace._interact(state, self.catalog))
        self.assertFalse(state.details)

    def test_student_inspector_keeps_compact_information_hierarchy(self):
        state = workspace.Workspace("students")
        row = state.current(self.catalog)
        details = workspace_view._details("students", row, self.catalog, 55)
        plain = "\n".join(screen._ANSI_RE.sub("", text) for text, _, _ in details)

        self.assertIn(row["name"], plain)
        self.assertIn(row["student_no"], plain)
        self.assertIn("选课与成绩", plain)
        self.assertIn("详细信息", plain)
        self.assertNotIn("即时预览", plain)
        self.assertNotIn("阅读中", plain)
        self.assertNotIn("档案字段", plain)
        self.assertEqual(plain.count(row["student_no"]), 1)
        self.assertEqual(plain.count(row["name"]), 1)


if __name__ == "__main__":
    unittest.main()
