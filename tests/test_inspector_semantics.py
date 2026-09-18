from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.auth import Identity
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.workspace import events as workspace_events
from xingyuan_sis.tui.workspace.data import Catalog


class InspectorSemanticTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def _state(self, key: str = "students") -> workspace.Workspace:
        return workspace.Workspace(
            key,
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )

    def _targets(self, state: workspace.Workspace, catalog: Catalog | None = None):
        catalog = catalog or self.catalog
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            return workspace_events.detail_targets(state, catalog)

    def _interact(self, state: workspace.Workspace, catalog: Catalog, *inputs: str):
        with patch.object(keys, "_read_key", side_effect=[*inputs, "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            return workspace_events.interact(state, catalog)

    def test_display_only_department_is_a_normal_read_only_target(self):
        state = self._state()
        actions = [action for _, action in self._targets(state)]
        self.assertIn("field:department_name", actions)

        state.detail_selected = actions.index("field:department_name")
        event = self._interact(state, self.catalog, "select")

        self.assertEqual(event, ("refresh", 0))
        self.assertIsNone(state.field_session)
        self.assertEqual([action for _, action in self._targets(state)][state.detail_selected],
                         "field:department_name")
        self.assertIn("只读", state.notice)

    def test_dynamic_age_editability_is_resolved_by_field_session(self):
        state = self._state()
        row = state.current(self.catalog)
        self.catalog.service.update_student_by_no(
            row["student_no"],
            birth_date="2000-01-01",
            age=99,
        )
        self.catalog.refresh()
        actions = [action for _, action in self._targets(state)]
        state.detail_selected = actions.index("field:age")

        event = self._interact(state, self.catalog, "select")

        self.assertEqual(event, ("refresh", 0))
        self.assertIsNone(state.field_session)
        self.assertIn("自动计算年龄", state.notice)
        self.assertEqual([action for _, action in self._targets(state)][state.detail_selected],
                         "field:age")

    def test_read_only_permissions_do_not_change_home_end_navigation(self):
        student_no = str(self.catalog.records["students"][0]["student_no"])
        catalog = Catalog(self.db, Identity(student_no, "student", student_no))
        state = self._state()
        actions = [action for _, action in self._targets(state, catalog)]

        self.assertEqual(self._interact(state, catalog, "end"), ("refresh", 0))
        self.assertEqual([action for _, action in self._targets(state, catalog)][state.detail_selected],
                         actions[-1])

        self.assertEqual(self._interact(state, catalog, "home"), ("refresh", 0))
        self.assertEqual([action for _, action in self._targets(state, catalog)][state.detail_selected],
                         actions[0])

    def test_multiline_announcement_keeps_body_and_timestamp_in_focus_graph(self):
        class_code = str(self.catalog.records["classes"][0]["code"])
        self.catalog.service.create_announcement(
            title="语义焦点测试",
            body="第一行\n第二行",
            class_code=class_code,
        )
        self.catalog.refresh()
        state = self._state("announcements")
        actions = [action for _, action in self._targets(state)]

        self.assertEqual(
            actions,
            ["field:title", "field:class_code", "field:created_at", "field:body"],
        )

        state.detail_selected = actions.index("field:created_at")
        self.assertEqual(self._interact(state, self.catalog, "down"), ("refresh", 0))
        actions = [action for _, action in self._targets(state)]
        self.assertEqual(actions[state.detail_selected], "field:body")

        self.assertEqual(self._interact(state, self.catalog, "select"), ("refresh", 0))
        self.assertIsNone(state.field_session)
        self.assertEqual([action for _, action in self._targets(state)][state.detail_selected],
                         "field:body")
        self.assertIn("只读", state.notice)


if __name__ == "__main__":
    unittest.main()
