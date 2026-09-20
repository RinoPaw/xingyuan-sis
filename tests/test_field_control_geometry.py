from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen, workspace
from xingyuan_sis.tui.workspace import field_session, forms, view
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.student_layout import STUDENT_FIELD_ORDER


class FieldControlGeometryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def test_student_create_form_derives_order_from_shared_layout(self):
        state = workspace.Workspace("students")
        forms.open_form(state, self.catalog, "create")

        available = {field.key for field in self.catalog.fields("students")}
        expected = [key for key in STUDENT_FIELD_ORDER if key in available]
        self.assertEqual([field.key for field in state.form.fields], expected)
        self.assertEqual(expected[:2], ["name", "student_no"])

    def test_form_selection_and_editing_use_the_same_bounded_box(self):
        state = workspace.Workspace("students")
        forms.open_form(state, self.catalog, "create")
        state.form.position = next(
            i for i, field in enumerate(state.form.fields) if field.key == "student_no"
        )

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            selected = view.render(state, self.catalog)
        selected_region = next(r for r in selected.regions if r.action == "field:student_no")

        field_session.start_form(state, self.catalog)
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            editing = view.render(state, self.catalog)
        editing_region = next(r for r in editing.regions if r.action == "field:student_no")

        self.assertEqual(editing_region.x, selected_region.x)
        self.assertEqual(editing_region.width, selected_region.width)
        self.assertLessEqual(editing_region.width, 28)

    def test_form_enter_keeps_typed_name_in_the_draft(self):
        state = workspace.Workspace("students")
        forms.open_form(state, self.catalog, "create")
        state.form.position = next(
            i for i, field in enumerate(state.form.fields) if field.key == "name"
        )
        field_session.start_form(state, self.catalog)

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch.object(screen, "_paint"), \
             patch.object(field_session, "read_inline_input", return_value="Rino") as inline:
            field_session.edit_current(state, self.catalog)

        self.assertIsNone(state.field_session)
        self.assertEqual(state.form.values["name"], "Rino")
        self.assertLessEqual(inline.call_args.kwargs["width"], 28)

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            frame = view.render(state, self.catalog)
        plain = "\n".join(screen._ANSI_RE.sub("", line) for line in frame.lines)
        self.assertIn("Rino", plain)


if __name__ == "__main__":
    unittest.main()
