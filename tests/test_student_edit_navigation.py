from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen
from xingyuan_sis.tui.workspace import forms as workspace_forms, student_inspector
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.state import Workspace


class StudentEditNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)
        self.state = Workspace("students")
        workspace_forms.open_form(self.state, self.catalog, "edit")

    def _focus(self, key: str) -> None:
        self.state.form.position = next(
            index for index, field in enumerate(self.state.form.fields) if field.key == key
        )

    def _focused_key(self) -> str:
        return self.state.form.fields[self.state.form.position].key

    def test_species_navigation_follows_visual_geometry(self):
        self._focus("family")
        workspace_forms.move_form_position(self.state, "up", self.catalog)
        self.assertEqual(self._focused_key(), "family")

        self._focus("family")
        workspace_forms.move_form_position(self.state, "right", self.catalog)
        self.assertEqual(self._focused_key(), "branch")

        workspace_forms.move_form_position(self.state, "left", self.catalog)
        self.assertEqual(self._focused_key(), "family")

    def test_element_and_affinity_share_one_navigation_row(self):
        self._focus("primary_element")
        workspace_forms.move_form_position(self.state, "right", self.catalog)
        self.assertEqual(self._focused_key(), "primary_affinity")

        workspace_forms.move_form_position(self.state, "left", self.catalog)
        self.assertEqual(self._focused_key(), "primary_element")

        self._focus("status")
        workspace_forms.move_form_position(self.state, "down", self.catalog)
        self.assertEqual(self._focused_key(), "primary_element")

    def test_render_groups_element_with_affinity_not_status(self):
        row = self.state.current(self.catalog)
        lines = student_inspector.lines(row, self.catalog, self.state)
        actions = [[action for _, _, action in line if action.startswith("field:")] for line in lines]
        index_by_key = {
            field.key: index for index, field in enumerate(self.state.form.fields)
        }
        element_action = f"field:{index_by_key['primary_element']}"
        affinity_action = f"field:{index_by_key['primary_affinity']}"
        status_action = f"field:{index_by_key['status']}"

        element_line = next(line for line in actions if element_action in line)
        self.assertIn(affinity_action, element_line)
        self.assertNotIn(status_action, element_line)

    def test_identity_is_read_only_while_editing(self):
        row = self.state.current(self.catalog)
        self._focus("family")
        lines = student_inspector.lines(row, self.catalog, self.state)
        self.assertEqual(lines[0][0][1], screen._BOLD + screen._TEXT_PRIMARY)
        self.assertFalse(lines[0][0][2])
        self.assertFalse(lines[1][1][2])
        self.assertNotIn("name", [field.key for field in self.state.form.fields])
        self.assertNotIn("student_no", [field.key for field in self.state.form.fields])

    def test_down_from_species_reaches_gender_before_enrollment(self):
        self._focus("family")
        workspace_forms.move_form_position(self.state, "down", self.catalog)
        self.assertEqual(self._focused_key(), "gender")
        workspace_forms.move_form_position(self.state, "down", self.catalog)
        self.assertEqual(self._focused_key(), "enrollment_year")


if __name__ == "__main__":
    unittest.main()
