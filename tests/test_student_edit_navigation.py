from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.workspace import student_inspector
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

    def test_browse_navigation_uses_one_target_sequence(self):
        targets = self._targets()
        actions = [action for _, action in targets]
        self.assertIn("edit-field:family", actions)
        self.assertIn("edit-field:branch", actions)
        self.assertIn("edit-field:primary_element", actions)
        self.assertIn("edit-field:primary_affinity", actions)

        family = actions.index("edit-field:family")
        branch = actions.index("edit-field:branch")
        element = actions.index("edit-field:primary_element")
        affinity = actions.index("edit-field:primary_affinity")
        self.assertEqual(branch, family + 1)
        self.assertEqual(affinity, element + 1)

    def test_arrows_move_the_same_detail_selection_before_editing(self):
        with patch.object(keys, "_read_key", side_effect=["down", "back", "back", "back"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            workspace._interact(self.state, self.catalog)
        self.assertEqual(self.state.detail_selected, 1)
        self.assertIsNone(self.state.form)

    def test_enter_opens_only_the_selected_field(self):
        targets = self._targets()
        actions = [action for _, action in targets]
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
