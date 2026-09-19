from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.workspace import events as workspace_events
from xingyuan_sis.tui.workspace import field_session as workspace_field
from xingyuan_sis.tui.workspace.data import Catalog


class StudentEditNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)
        self.state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )

    def _targets(self):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            return workspace_events.detail_targets(self.state, self.catalog)

    def _actions(self):
        return [action for _, action in self._targets()]

    def _move(self, current: str, direction: str):
        actions = self._actions()
        self.state.set_focus(workspace.FocusArea.INSPECTOR)
        self.state.detail_selected = actions.index(current)
        with patch.object(keys, "_read_key", side_effect=[direction, "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            event = workspace_events.interact(self.state, self.catalog)
        self.assertEqual(event, ("refresh", 0))
        if self.state.focus is not workspace.FocusArea.INSPECTOR:
            return None
        return self._actions()[self.state.detail_selected]

    def test_enter_from_roster_focuses_name_then_student_number(self):
        self.state.set_focus(workspace.FocusArea.ROSTER)
        with patch.object(keys, "_read_key", side_effect=["select", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            event = workspace_events.interact(self.state, self.catalog)

        self.assertEqual(event, ("refresh", 0))
        self.assertEqual(self.state.focus, workspace.FocusArea.INSPECTOR)
        actions = self._actions()
        self.assertEqual(actions[self.state.detail_selected], "field:name")
        self.assertEqual(self._move("field:name", "down"), "field:student_no")

    def test_species_composite_row_uses_real_event_geometry(self):
        self.assertEqual(self._move("field:student_no", "down"), "field:branch")
        self.assertEqual(self._move("field:gender", "up"), "field:branch")
        self.assertEqual(self._move("field:branch", "up"), "field:student_no")
        self.assertEqual(self._move("field:branch", "left"), "field:family")
        self.assertEqual(self._move("field:family", "right"), "field:branch")
        self.assertIsNone(self._move("field:family", "left"))

    def test_class_composite_row_uses_same_real_event_geometry(self):
        self.assertEqual(self._move("field:department_name", "down"), "field:class_number")
        self.assertEqual(self._move("field:status", "up"), "field:class_number")
        self.assertEqual(self._move("field:class_number", "up"), "field:department_name")
        self.assertEqual(self._move("field:class_number", "left"), "field:major_code")
        self.assertEqual(self._move("field:major_code", "right"), "field:class_number")
        self.assertIsNone(self._move("field:major_code", "left"))

    def test_element_composite_row_uses_same_real_event_geometry(self):
        self.assertEqual(self._move("field:status", "down"), "field:primary_affinity")
        self.assertEqual(self._move("field:primary_affinity", "up"), "field:status")
        self.assertEqual(self._move("field:primary_affinity", "left"), "field:primary_element")
        self.assertEqual(self._move("field:primary_element", "right"), "field:primary_affinity")
        self.assertIsNone(self._move("field:primary_element", "left"))

    def test_read_only_fields_are_focusable_but_not_editable(self):
        actions = self._actions()
        for action in ("field:name", "field:student_no", "field:department_name"):
            with self.subTest(action=action):
                self.state.set_focus(workspace.FocusArea.INSPECTOR)
                self.state.field_session = None
                self.state.detail_selected = actions.index(action)
                with patch.object(keys, "_read_key", side_effect=["select", "refresh"]), \
                     patch.object(screen, "_paint"), \
                     patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
                    event = workspace_events.interact(self.state, self.catalog)
                self.assertEqual(event, ("refresh", 0))
                self.assertIsNone(self.state.field_session)
                self.assertEqual(self._actions()[self.state.detail_selected], action)
                self.assertIn("只读", self.state.notice)

    def test_department_stays_in_the_vertical_focus_chain(self):
        self.assertEqual(self._move("field:enrollment_year", "down"), "field:department_name")
        self.assertEqual(self._move("field:department_name", "down"), "field:class_number")
        self.assertEqual(self._move("field:class_number", "up"), "field:department_name")

    def test_enter_opens_selected_semantic_field_group(self):
        actions = self._actions()
        self.state.detail_selected = actions.index("field:primary_element")

        with patch.object(keys, "_read_key", side_effect=["select"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            event = workspace_events.interact(self.state, self.catalog)

        self.assertEqual(event, ("field-edit", 0))
        self.assertEqual(
            [field.key for field in self.state.field_session.fields],
            ["primary_element", "primary_affinity"],
        )
        self.assertIsNone(self.state.form)

    def test_species_class_and_element_share_parent_child_session_semantics(self):
        pairs = (
            ("family", "branch"),
            ("major_code", "class_number"),
            ("primary_element", "primary_affinity"),
        )
        for parent, child in pairs:
            with self.subTest(parent=parent, child=child):
                workspace_field.start(self.state, self.catalog, parent)
                self.assertEqual(
                    [field.key for field in self.state.field_session.fields],
                    [parent, child],
                )
                workspace_field.cancel(self.state)
                workspace_field.start(self.state, self.catalog, child)
                self.assertEqual(
                    [field.key for field in self.state.field_session.fields],
                    [child],
                )
                workspace_field.cancel(self.state)

    def test_complete_birth_date_keeps_derived_age_focusable_but_not_directly_editable(self):
        row = self.state.current(self.catalog)
        self.catalog.service.update_student_by_no(row["student_no"], birth_date="2000-01-01", age=99)
        self.catalog.refresh()
        actions = self._actions()
        self.assertIn("field:age", actions)
        with self.assertRaisesRegex(ValueError, "自动计算年龄"):
            workspace_field.start(self.state, self.catalog, "age")


if __name__ == "__main__":
    unittest.main()
