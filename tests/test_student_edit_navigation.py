from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.workspace import events as workspace_events
from xingyuan_sis.tui.workspace import forms as workspace_forms
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
            return workspace_events.detail_targets(self.state, self.catalog)

    def _actions(self):
        return [action for _, action in self._targets()]

    def _move(self, current: str, direction: str):
        actions = self._actions()
        self.state.details = True
        self.state.detail_selected = actions.index(current)
        with patch.object(keys, "_read_key", side_effect=[direction, "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            event = workspace_events.interact(self.state, self.catalog)
        self.assertEqual(event, ("refresh", 0))
        if not self.state.details:
            return None
        return self._actions()[self.state.detail_selected]

    def test_enter_from_roster_focuses_name_then_student_number(self):
        self.state.details = False
        with patch.object(keys, "_read_key", side_effect=["select", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            event = workspace_events.interact(self.state, self.catalog)

        self.assertEqual(event, ("refresh", 0))
        self.assertTrue(self.state.details)
        actions = self._actions()
        self.assertEqual(actions[self.state.detail_selected], "field-target:name")
        self.assertEqual(
            self._move("field-target:name", "down"),
            "field-target:student_no",
        )

    def test_species_composite_row_uses_real_event_geometry(self):
        self.assertEqual(
            self._move("field-target:student_no", "down"),
            "field-target:branch",
        )
        self.assertEqual(
            self._move("field-target:gender", "up"),
            "field-target:branch",
        )
        self.assertEqual(
            self._move("field-target:branch", "up"),
            "field-target:student_no",
        )
        self.assertEqual(
            self._move("field-target:branch", "left"),
            "field-target:family",
        )
        self.assertEqual(
            self._move("field-target:family", "right"),
            "field-target:branch",
        )
        self.assertIsNone(self._move("field-target:family", "left"))

    def test_element_composite_row_uses_the_same_real_event_geometry(self):
        self.assertEqual(
            self._move("field-target:status", "down"),
            "field-target:primary_affinity",
        )
        self.assertEqual(
            self._move("field-target:primary_affinity", "up"),
            "field-target:status",
        )
        self.assertEqual(
            self._move("field-target:primary_affinity", "left"),
            "field-target:primary_element",
        )
        self.assertEqual(
            self._move("field-target:primary_element", "right"),
            "field-target:primary_affinity",
        )
        self.assertIsNone(self._move("field-target:primary_element", "left"))

    def test_read_only_identity_fields_are_focusable_but_not_editable(self):
        actions = self._actions()
        for action in ("field-target:name", "field-target:student_no"):
            with self.subTest(action=action):
                self.state.details = True
                self.state.form = None
                self.state.detail_selected = actions.index(action)
                with patch.object(keys, "_read_key", side_effect=["select", "refresh"]), \
                     patch.object(screen, "_paint"), \
                     patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
                    event = workspace_events.interact(self.state, self.catalog)
                self.assertEqual(event, ("refresh", 0))
                self.assertIsNone(self.state.form)
                self.assertEqual(self._actions()[self.state.detail_selected], action)
                self.assertIn("只读", self.state.notice)

    def test_enter_opens_only_the_selected_editable_field(self):
        actions = self._actions()
        self.state.detail_selected = actions.index("field-target:primary_element")

        with patch.object(keys, "_read_key", side_effect=["select"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            event = workspace_events.interact(self.state, self.catalog)

        self.assertEqual(event, ("field", 0))
        self.assertEqual([field.key for field in self.state.form.fields], ["primary_element"])

    def test_complete_birth_date_keeps_derived_age_focusable_but_not_directly_editable(self):
        row = self.state.current(self.catalog)
        self.catalog.service.update_student_by_no(row["student_no"], birth_date="2000-01-01", age=99)
        self.catalog.refresh()
        actions = self._actions()
        self.assertIn("field-target:age", actions)
        with self.assertRaisesRegex(ValueError, "自动计算年龄"):
            workspace_forms.open_field(self.state, self.catalog, "age")


if __name__ == "__main__":
    unittest.main()
