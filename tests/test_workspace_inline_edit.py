from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis import terminal_input
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.text_edit import TextBuffer
from xingyuan_sis.tui.workspace import events as workspace_events
from xingyuan_sis.tui.workspace import field_session as workspace_field
from xingyuan_sis.tui.workspace import student_inspector, view as workspace_view
from xingyuan_sis.tui.workspace.data import Catalog


class WorkspaceInlineEditTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    @staticmethod
    def inspector_state(collection: str = "students"):
        return workspace.Workspace(
            collection,
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )

    def test_student_fields_with_finite_values_are_options(self):
        values = self.catalog.defaults("students", self.catalog.records["students"][0])

        expected = {
            "status": ["在读", "休学", "保留学籍"],
            "gender": [None, "男", "女"],
            "primary_element": [None, "风", "水", "火", "雷", "岩", "光"],
            "primary_affinity": [None, "A", "B", "C"],
        }
        for field, choices in expected.items():
            with self.subTest(field=field):
                options = self.catalog.options("students", field, values)
                self.assertEqual([value for value, _ in options], choices)

        families = self.catalog.options("students", "family", values)
        self.assertIn(values["family"], [value for value, _ in families])

        branches = self.catalog.options("students", "branch", values)
        expected_branches = [
            row["name"]
            for row in self.catalog.service.list_species_branches()
            if row["family_name"] == values["family"]
        ]
        self.assertEqual([value for value, _ in branches], expected_branches)

        for field in (
            "student_no", "name", "enrollment_year", "age",
            "birth_date", "contact", "dormitory", "notes",
        ):
            with self.subTest(freeform=field):
                self.assertIsNone(self.catalog.options("students", field, values))

    def test_foreign_keys_are_enumerated_across_forms(self):
        cases = (
            ("students", "class_code"),
            ("courses", "department_code"),
            ("majors", "department_code"),
            ("classes", "major_code"),
            ("grades", "student_no"),
            ("grades", "course_code"),
        )
        for collection, field in cases:
            with self.subTest(collection=collection, field=field):
                values = self.catalog.defaults(collection, self.catalog.records[collection][0])
                self.assertIsNotNone(self.catalog.options(collection, field, values))

    def test_field_edit_stays_inside_same_record_inspector_with_stable_target(self):
        state = self.inspector_state()
        workspace_field.start(state, self.catalog, "contact")
        row = state.current(self.catalog)

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((140, 35))), \
             patch.object(workspace_view, "render_editor") as detached_editor:
            frame = workspace_view.render(state, self.catalog)

        detached_editor.assert_not_called()
        plain = "\n".join(screen._ANSI_RE.sub("", line) for line in frame.lines)
        self.assertIn("档案", plain)
        self.assertIn(row["name"], plain)
        self.assertIn("物种", plain)
        self.assertIn("选课与成绩", plain)
        self.assertIn("个人信息", plain)
        self.assertTrue(any(region.action == "field:contact" for region in frame.regions))
        self.assertFalse(any(region.action == "save" for region in frame.regions))
        self.assertIsNone(state.form)

    def test_field_session_contains_only_selected_field_group(self):
        state = workspace.Workspace("students")
        workspace_field.start(state, self.catalog, "contact")
        self.assertEqual([field.key for field in state.field_session.fields], ["contact"])
        self.assertEqual(state.field_session.active_key, "contact")
        self.assertIsNone(state.form)

    def test_enum_picker_expands_inside_inspector_without_replacing_field_target(self):
        state = self.inspector_state()
        workspace_field.start(state, self.catalog, "status")
        workspace_field.edit_current(state, self.catalog)

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((140, 35))), \
             patch.object(workspace_view, "render_editor") as detached_editor:
            frame = workspace_view.render(state, self.catalog)

        detached_editor.assert_not_called()
        self.assertTrue(any(region.action.startswith("option:") for region in frame.regions))
        self.assertTrue(any(region.action == "field:status" for region in frame.regions))
        self.assertFalse(any(region.action == "save" for region in frame.regions))

    def test_freeform_enter_saves_immediately(self):
        state = self.inspector_state()
        workspace_field.start(state, self.catalog, "contact")
        original_no = state.current(self.catalog)["student_no"]

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch.object(screen, "_paint"), \
             patch.object(workspace_field, "read_inline_input", return_value="原地新联系方式") as inline:
            workspace_field.edit_current(state, self.catalog)

        self.assertIsNone(state.field_session)
        self.assertEqual(self.catalog.service.student_by_no(original_no)["contact"], "原地新联系方式")
        self.assertGreater(inline.call_args.kwargs["row"], 0)
        self.assertGreater(inline.call_args.kwargs["column"], 0)
        self.assertGreater(inline.call_args.kwargs["width"], 0)

    def test_enum_enter_saves_inside_same_event_path(self):
        state = self.inspector_state()
        original = state.current(self.catalog).copy()
        workspace_field.start(state, self.catalog, "status")
        workspace_field.edit_current(state, self.catalog)
        target_index = next(
            i for i, (value, _) in enumerate(state.field_session.options)
            if value != original["status"]
        )

        with patch.object(keys, "_read_key", side_effect=[f"option:{target_index}", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            event = workspace_events.interact(state, self.catalog)

        self.assertEqual(event, ("refresh", 0))
        self.assertIsNone(state.field_session)
        self.assertNotEqual(
            self.catalog.service.student_by_no(original["student_no"])["status"],
            original["status"],
        )

    def test_family_edit_completes_branch_before_one_atomic_save(self):
        state = self.inspector_state()
        original = state.current(self.catalog).copy()
        workspace_field.start(state, self.catalog, "family")
        workspace_field.edit_current(state, self.catalog)
        family_index = next(
            i for i, (value, _) in enumerate(state.field_session.options)
            if value != original["family"] and any(
                row["family_name"] == value for row in self.catalog.species_branches
            )
        )
        chosen_family = state.field_session.options[family_index][0]
        workspace_field.accept_option(state, self.catalog, family_index)
        self.assertEqual(state.field_session.active_key, "branch")
        chosen_branch = state.field_session.options[0][0]
        workspace_field.accept_option(state, self.catalog, 0)

        self.assertIsNone(state.field_session)
        changed = self.catalog.service.student_by_no(original["student_no"])
        self.assertEqual((changed["family"], changed["branch"]), (chosen_family, chosen_branch))

    def test_complete_birth_date_derives_age_but_keeps_age_in_focus_graph(self):
        row = self.catalog.records["students"][0]
        self.catalog.service.update_student_by_no(row["student_no"], birth_date="2000-01-01", age=99)
        self.catalog.refresh()
        row = self.catalog.records["students"][0]
        lines = student_inspector.lines(row, self.catalog)
        age_line = next(line for line in lines if line and line[0][0].startswith("年龄"))

        self.assertIsNone(row["age"])
        self.assertTrue(any(action == "field:age" for _, _, action in age_line))
        self.assertTrue(any(text.endswith("岁") for text, _, _ in age_line))
        with self.assertRaisesRegex(ValueError, "自动计算年龄"):
            workspace_field.start(workspace.Workspace("students"), self.catalog, "age")

    def test_inline_redraw_never_clears_the_whole_terminal_row(self):
        buffer = TextBuffer.from_value("林岚")
        with patch("sys.stdout.write") as write, patch("sys.stdout.flush"):
            terminal_input._redraw_inline(7, 13, 8, buffer, colored=True)

        output = "".join(call.args[0] for call in write.call_args_list)
        self.assertIn("\x1b[7;13H", output)
        self.assertNotIn("\x1b[2K", output)


if __name__ == "__main__":
    unittest.main()
