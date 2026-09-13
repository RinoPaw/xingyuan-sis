from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis import terminal_input
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen, workspace, workspace_forms
from xingyuan_sis.tui.workspace_data import Catalog


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
        with patch("sys.stdout.write") as write, patch("sys.stdout.flush"):
            terminal_input._redraw_inline(7, 13, 8, list("林岚"), 2, colored=True)

        output = "".join(call.args[0] for call in write.call_args_list)
        self.assertIn("\x1b[7;13H", output)
        self.assertNotIn("\x1b[2K", output)


if __name__ == "__main__":
    unittest.main()
