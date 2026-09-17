from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.workspace import student_inspector, view as workspace_view
from xingyuan_sis.tui.workspace.data import Catalog


class StudentEditNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)
        self.state = workspace.Workspace("students", details=True)

    def _targets(self):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            return workspace._detail_targets(self.state, self.catalog)

    def _actions(self):
        return [action for _, action in self._targets()]

    @staticmethod
    def _moved_action(actions, current, direction):
        selected = actions.index(current)
        moved = workspace_view.directional_target("students", actions, selected, direction)
        return None if moved is None else actions[moved]

    def test_species_composite_row_uses_spatial_navigation(self):
        actions = self._actions()
        self.assertEqual(
            self._moved_action(actions, "edit-field:student_no", "down"),
            "edit-field:branch",
        )
        self.assertEqual(
            self._moved_action(actions, "edit-field:gender", "up"),
            "edit-field:branch",
        )
        self.assertEqual(
            self._moved_action(actions, "edit-field:branch", "left"),
            "edit-field:family",
        )
        self.assertEqual(
            self._moved_action(actions, "edit-field:family", "right"),
            "edit-field:branch",
        )
        self.assertIsNone(
            self._moved_action(actions, "edit-field:family", "left")
        )

    def test_element_composite_row_uses_the_same_spatial_navigation(self):
        actions = self._actions()
        self.assertEqual(
            self._moved_action(actions, "edit-field:status", "down"),
            "edit-field:primary_affinity",
        )
        self.assertEqual(
            self._moved_action(actions, "edit-field:primary_affinity", "left"),
            "edit-field:primary_element",
        )
        self.assertEqual(
            self._moved_action(actions, "edit-field:primary_element", "right"),
            "edit-field:primary_affinity",
        )
        self.assertIsNone(
            self._moved_action(actions, "edit-field:primary_element", "left")
        )
        affinity = actions.index("edit-field:primary_affinity")
        next_main = actions[affinity + 1]
        self.assertEqual(
            self._moved_action(actions, next_main, "up"),
            "edit-field:primary_affinity",
        )

    def test_left_from_species_primary_returns_to_student_roster(self):
        actions = self._actions()
        self.state.detail_selected = actions.index("edit-field:family")
        with patch.object(keys, "_read_key", side_effect=["left", "back", "back"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            workspace._interact(self.state, self.catalog)
        self.assertFalse(self.state.details)
        self.assertEqual(self.state.selected, 0)

    def test_arrows_move_the_same_detail_selection_before_editing(self):
        with patch.object(keys, "_read_key", side_effect=["down", "back", "back", "back"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            workspace._interact(self.state, self.catalog)
        self.assertEqual(self.state.detail_selected, 1)
        self.assertIsNone(self.state.form)

    def test_enter_opens_only_the_selected_field(self):
        actions = self._actions()
        self.state.detail_selected = actions.index("edit-field:primary_element")

        with patch.object(keys, "_read_key", side_effect=["select"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            event = workspace._interact(self.state, self.catalog)

        self.assertEqual(event, ("field", 0))
        self.assertEqual([field.key for field in self.state.form.fields], ["primary_element"])

    def test_render_groups_element_with_affinity_not_status(self):
        row = self.state.current(self.catalog)
        lines = student_inspector._lines(row, self.catalog)
        actions = [[action for _, _, action in line if action.startswith("edit-field:")] for line in lines]

        element_line = next(line for line in actions if "edit-field:primary_element" in line)
        self.assertIn("edit-field:primary_affinity", element_line)
        self.assertNotIn("edit-field:status", element_line)

    def test_only_active_field_changes_visual_state(self):
        row = self.state.current(self.catalog)
        workspace._open_field(self.state, self.catalog, "student_no")
        lines = student_inspector._lines(row, self.catalog, self.state)
        self.assertEqual(lines[0][0][1], screen._BOLD + screen._TEXT_PRIMARY)

        self.state.form = None
        workspace._open_field(self.state, self.catalog, "name")
        lines = student_inspector._lines(row, self.catalog, self.state)
        self.assertEqual(lines[0][0][1], screen._BOLD + screen._TEXT_ACCENT)


if __name__ == "__main__":
    unittest.main()
