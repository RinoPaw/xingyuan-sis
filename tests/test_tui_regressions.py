from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.workspace import events as workspace_events
from xingyuan_sis.tui.workspace import field_session, forms as workspace_forms
from xingyuan_sis.tui.workspace import student_inspector, view as workspace_view
from xingyuan_sis.tui.workspace.data import ACADEMICS, Catalog


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

    def assert_escape_footer(self, state: workspace.Workspace) -> None:
        frame = self.render(state)
        footer = screen._ANSI_RE.sub("", frame.lines[-1])
        self.assertIn("Esc", footer)
        self.assertNotIn("Ctrl+C", footer)
        self.assertNotIn("q/", footer)
        self.assertNotIn("/q", footer)

    def test_every_workspace_footer_uses_the_same_visible_escape_contract(self):
        for key in WORKSPACES:
            with self.subTest(key=key):
                self.assert_escape_footer(workspace.Workspace(key))

    def test_every_transaction_and_field_session_keeps_escape_contract(self):
        for key in RECORD_WORKSPACES:
            with self.subTest(key=key, mode="field-session"):
                state = workspace.Workspace(key)
                field_key = self.catalog.fields(key, True)[0].key
                field_session.start(state, self.catalog, field_key)
                self.assertIsNone(state.form)
                self.assertIsNotNone(state.field_session)
                self.assert_escape_footer(state)

            with self.subTest(key=key, mode="delete"):
                state = workspace.Workspace(key)
                workspace_forms.open_form(state, self.catalog, "delete")
                self.assert_escape_footer(state)

        for mode in ("import", "export", "seed"):
            with self.subTest(key="data", mode=mode):
                state = workspace.Workspace("data")
                workspace_forms.open_form(state, self.catalog, mode)
                self.assert_escape_footer(state)

    def test_every_record_workspace_distinguishes_focused_and_context_selection(self):
        for key in RECORD_WORKSPACES:
            with self.subTest(key=key), patch("sys.stdout.isatty", return_value=True), \
                 patch.dict(os.environ) as environment:
                environment.pop("NO_COLOR", None)
                state = workspace.Workspace(key)
                focused = workspace_view.Board(60, 35)
                workspace_view._roster(focused, state, self.catalog, 59)
                focused_frame = focused.frame()
                focused_region = next(r for r in focused_frame.regions if r.action == "row:0")
                focused_line = focused_frame.lines[focused_region.y - 1]
                self.assertIn(screen._SURFACE_SELECTED, focused_line)
                self.assertIn(screen._TEXT_ACCENT, focused_line)

                state.set_focus(workspace.FocusArea.INSPECTOR)
                context = workspace_view.Board(60, 35)
                workspace_view._roster(context, state, self.catalog, 59)
                context_frame = context.frame()
                context_region = next(r for r in context_frame.regions if r.action == "row:0")
                context_line = context_frame.lines[context_region.y - 1]
                context_plain = screen._ANSI_RE.sub("", context_line)
                self.assertIn("· ", context_plain)
                self.assertIn(screen._TEXT_SECONDARY, context_line)
                self.assertIn(screen._TEXT_PRIMARY, context_line)
                self.assertNotIn(screen._SURFACE_INTERACTIVE, context_line)
                self.assertNotIn(screen._SURFACE_SELECTED, context_line)
                self.assertNotIn(screen._TEXT_ACCENT, context_line)

                inspector = workspace_view.Board(60, 35)
                workspace_view._inspector(inspector, state, self.catalog, 1, 55)
                inspector_frame = inspector.frame()
                targets = workspace_view.detail_targets(key, state.current(self.catalog), self.catalog, 55)
                selected_action = targets[state.detail_selected][1]
                selected_region = next(r for r in inspector_frame.regions if r.action == selected_action)
                self.assertIn(screen._SURFACE_SELECTED, inspector_frame.lines[selected_region.y - 1])

    def test_counts_stay_attached_to_their_matching_views(self):
        students = self.render(workspace.Workspace("students"))
        self.assertFalse(any(region.action.startswith("view:") for region in students.regions))
        for key in ("courses", "grades"):
            with self.subTest(key=key):
                state = workspace.Workspace(key)
                choice_row = screen._ANSI_RE.sub("", self.render(state).lines[4])
                for index in range(3):
                    self.assertIn(f"· {len(self.catalog.rows(key, index, state.query))}", choice_row)
        for key in ACADEMICS:
            with self.subTest(key=key):
                choice_row = screen._ANSI_RE.sub("", self.render(workspace.Workspace(key)).lines[4])
                for collection in ACADEMICS:
                    self.assertIn(f"· {len(self.catalog.records[collection])}", choice_row)

    def test_escape_cancels_field_sessions_without_writing_on_every_record_page(self):
        for key in RECORD_WORKSPACES:
            with self.subTest(key=key):
                state = workspace.Workspace(key)
                before = deepcopy(state.current(self.catalog))
                field_key = self.catalog.fields(key, True)[0].key
                field_session.start(state, self.catalog, field_key)
                self.assertIsNotNone(state.field_session)
                self.assertIsNone(state.form)

                with patch.object(keys, "_read_key", side_effect=["back", "back", "back"]), \
                     patch.object(screen, "_paint"), \
                     patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
                    self.assertIsNone(workspace_events.interact(state, self.catalog))

                self.assertIsNone(state.field_session)
                self.assertEqual(state.current(self.catalog), before)

    def test_escape_cancels_delete_confirmation_without_writing(self):
        state = workspace.Workspace("students")
        before = deepcopy(state.current(self.catalog))
        count = len(self.catalog.records["students"])
        workspace_forms.open_form(state, self.catalog, "delete")
        with patch.object(keys, "_read_key", side_effect=["back", "back"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            self.assertIsNone(workspace_events.interact(state, self.catalog))
        self.assertEqual(len(self.catalog.records["students"]), count)
        self.assertEqual(state.current(self.catalog), before)

    def test_escape_unwinds_inspector_focus_before_leaving_workspace(self):
        state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        with patch.object(keys, "_read_key", side_effect=["back", "back"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            self.assertIsNone(workspace_events.interact(state, self.catalog))
        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)
        self.assertEqual(state.content_panel, workspace.ContentPanel.ROSTER)

    def test_student_inspector_keeps_one_current_information_hierarchy(self):
        state = workspace.Workspace("students")
        row = state.current(self.catalog)
        rendered = student_inspector.lines(row, self.catalog)
        plain = "\n".join(screen._ANSI_RE.sub("", "".join(text for text, _, _ in line)) for line in rendered)
        summary = plain.split("选课与成绩", 1)[0]
        for text in (row["name"], str(row["student_no"]), "物种", "性别", "年龄", "入学", "学院", "班级", "学籍", "元素"):
            self.assertIn(text, summary)
        self.assertIn("选课与成绩", plain)
        self.assertIn("个人信息", plain)
        self.assertNotIn("详细信息", plain)
        self.assertEqual(plain.count(row["name"]), 1)


if __name__ == "__main__":
    unittest.main()
