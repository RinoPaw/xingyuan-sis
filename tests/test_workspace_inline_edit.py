from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis import terminal_input
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen, workspace
from xingyuan_sis.tui.text_edit import TextBuffer
from xingyuan_sis.tui.workspace import forms as workspace_forms, view as workspace_view
from xingyuan_sis.tui.workspace.data import Catalog


class WorkspaceInlineEditTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def test_student_fields_with_finite_values_are_options(self):
        state = workspace.Workspace("students")
        workspace._open_form(state, self.catalog, "edit")
        values = state.form.values

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

        for field in ("student_no", "name", "enrollment_year", "birth_date", "contact", "dormitory", "notes"):
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

    def test_edit_form_stays_inside_the_same_record_inspector(self):
        state = workspace.Workspace("students")
        workspace._open_form(state, self.catalog, "edit")
        row = state.current(self.catalog)

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((140, 35))), \
             patch.object(workspace_view, "render_editor") as detached_editor:
            frame = workspace_view.render(state, self.catalog)

        detached_editor.assert_not_called()
        plain = "\n".join(screen._ANSI_RE.sub("", line) for line in frame.lines)
        self.assertIn("档案", plain)
        self.assertNotIn("编辑中", plain)
        self.assertIn("物种", plain)
        self.assertIn("性别", plain)
        self.assertRegex(plain, r"\d+岁")
        self.assertIn("入学", plain)
        self.assertIn("学院", plain)
        self.assertIn("班级", plain)
        self.assertIn("学籍", plain)
        self.assertIn("元素", plain)
        self.assertIn(f"{row['primary_element']} · {row['primary_affinity']}", plain)
        self.assertNotIn("亲和  ", plain)
        self.assertIn("选课与成绩", plain)
        self.assertIn("个人信息", plain)
        personal = plain.split("个人信息", 1)[1]
        self.assertNotIn("性别", personal)
        self.assertIn("出生日期", personal)
        self.assertNotIn("编辑 · 学生档案", plain)
        self.assertNotIn("族系*", plain)
        self.assertNotIn("支系*", plain)
        self.assertTrue(any(region.action == "field:1" for region in frame.regions))
        self.assertTrue(any(region.action == "save" for region in frame.regions))

    def test_student_edit_starts_on_name_without_reordering_schema_fields(self):
        state = workspace.Workspace("students")
        workspace._open_form(state, self.catalog, "edit")
        self.assertEqual(state.form.fields[0].key, "student_no")
        self.assertEqual(state.form.fields[1].key, "name")
        self.assertEqual(state.form.position, 1)

    def test_enum_picker_expands_inside_the_inspector(self):
        state = workspace.Workspace("students")
        workspace._open_form(state, self.catalog, "edit")
        index = next(i for i, field in enumerate(state.form.fields) if field.key == "status")
        workspace._read_value(state, self.catalog, ("field", index))

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((140, 35))), \
             patch.object(workspace_view, "render_editor") as detached_editor:
            frame = workspace_view.render(state, self.catalog)

        detached_editor.assert_not_called()
        self.assertTrue(any(region.action.startswith("option:") for region in frame.regions))
        self.assertTrue(any(region.action == f"field:{index}" for region in frame.regions))

    def test_freeform_edit_uses_the_field_row_instead_of_bottom_prompt(self):
        state = workspace.Workspace("students")
        workspace._open_form(state, self.catalog, "edit")
        index = next(i for i, field in enumerate(state.form.fields) if field.key == "name")
        original = state.form.values["name"]

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch.object(screen, "_paint"), \
             patch.object(workspace_forms, "read_inline_input", return_value="原地新名字") as inline, \
             patch.object(workspace_forms, "read_input") as bottom:
            workspace._read_value(state, self.catalog, ("field", index))

        bottom.assert_not_called()
        self.assertEqual(state.form.values["name"], "原地新名字")
        self.assertEqual(inline.call_args.kwargs["initial_value"], original)
        self.assertGreater(inline.call_args.kwargs["row"], 0)
        self.assertGreater(inline.call_args.kwargs["column"], 0)
        self.assertGreater(inline.call_args.kwargs["width"], 0)

    def test_enum_edit_opens_picker_without_text_input(self):
        state = workspace.Workspace("students")
        workspace._open_form(state, self.catalog, "edit")
        index = next(i for i, field in enumerate(state.form.fields) if field.key == "status")

        with patch.object(workspace_forms, "read_inline_input") as inline, \
             patch.object(workspace_forms, "read_input") as bottom:
            workspace._read_value(state, self.catalog, ("field", index))

        inline.assert_not_called()
        bottom.assert_not_called()
        self.assertEqual([value for value, _ in state.form.options], ["在读", "休学", "保留学籍"])

    def test_inline_redraw_never_clears_the_whole_terminal_row(self):
        buffer = TextBuffer.from_value("林岚")
        with patch("sys.stdout.write") as write, patch("sys.stdout.flush"):
            terminal_input._redraw_inline(7, 13, 8, buffer, colored=True)

        output = "".join(call.args[0] for call in write.call_args_list)
        self.assertIn("\x1b[7;13H", output)
        self.assertNotIn("\x1b[2K", output)


if __name__ == "__main__":
    unittest.main()
