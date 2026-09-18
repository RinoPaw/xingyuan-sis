from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.workspace import events as workspace_events, view as workspace_view
from xingyuan_sis.tui.workspace.data import Catalog


class WorkspaceActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def test_record_actions_are_body_buttons_and_footer_is_not_clickable(self):
        state = workspace.Workspace("students")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            frame = workspace_view.render(state, self.catalog)

        actions = {region.action: region for region in frame.regions}
        for action in ("create", "edit", "delete"):
            self.assertIn(action, actions)
            self.assertLess(actions[action].y, 35)

        footer = screen._ANSI_RE.sub("", frame.lines[-1])
        self.assertIn("方向键 移动", footer)
        self.assertIn("Enter 打开", footer)
        self.assertIn("Esc 返回", footer)
        self.assertFalse(any(region.y == 35 for region in frame.regions))

    def test_shift_tab_can_choose_edit_and_enter_focuses_first_editable_field(self):
        state = workspace.Workspace("students")
        with patch.object(
            keys,
            "_read_key",
            side_effect=["focus_prev", "right", "right", "select", "refresh"],
        ), patch.object(screen, "_paint"), patch.object(
            screen, "_terminal_size", return_value=os.terminal_size((120, 35))
        ):
            event = workspace_events.interact(state, self.catalog)

        self.assertEqual(event, ("refresh", 0))
        self.assertTrue(state.details)
        self.assertFalse(state.action_focus)
        self.assertIsNone(state.form)
        targets = workspace_events.detail_targets(state, self.catalog)
        current = targets[state.detail_selected][1]
        editable = {field.key for field in self.catalog.fields("students", True)}
        self.assertTrue(current.startswith("field-target:"))
        self.assertIn(current.removeprefix("field-target:"), editable)

    def test_shift_tab_to_actions_preserves_selected_record_for_delete(self):
        state = workspace.Workspace("students", selected=15)
        selected_at_delete: list[int] = []

        def capture(_state, _catalog, action):
            if action == "delete":
                selected_at_delete.append(_state.selected)

        with patch.object(
            keys, "_read_key",
            side_effect=["focus_prev", "right", "right", "right", "select", "back", "back"],
        ), patch.object(screen, "_paint"), patch.object(
            screen, "_terminal_size", return_value=os.terminal_size((120, 35))
        ), patch.object(workspace_events, "open_form", side_effect=capture):
            workspace_events.interact(state, self.catalog)

        self.assertEqual(selected_at_delete, [15])
        self.assertEqual(state.selected, 15)

    def test_action_focus_keeps_current_record_weakly_selected(self):
        state = workspace.Workspace("students", selected=15, action_focus=True)
        selected = state.current(self.catalog)

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ) as environment:
            environment.pop("NO_COLOR", None)
            frame = workspace_view.render(state, self.catalog)

        selected_line = next(
            line for line in frame.lines
            if selected["name"] in screen._ANSI_RE.sub("", line)
            and selected["student_no"] in screen._ANSI_RE.sub("", line)
        )
        self.assertIn(screen._SURFACE_INTERACTIVE, selected_line)
        self.assertIn(screen._TEXT_PRIMARY, selected_line)
        self.assertNotIn(screen._SURFACE_SELECTED, selected_line)

    def test_create_and_delete_shortcuts_open_their_transaction_forms(self):
        for key, action in (("create", "create"), ("delete", "delete")):
            state = workspace.Workspace("students")
            with self.subTest(key=key), \
                 patch.object(keys, "_read_key", side_effect=[key, "back", "back"]), \
                 patch.object(screen, "_paint"), \
                 patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
                 patch.object(workspace_events, "open_form") as open_form:
                workspace_events.interact(state, self.catalog)
            open_form.assert_called_once_with(state, self.catalog, action)

    def test_edit_shortcut_never_opens_a_record_edit_form(self):
        state = workspace.Workspace("students")
        with patch.object(keys, "_read_key", side_effect=["edit", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch.object(workspace_events, "open_form") as open_form:
            event = workspace_events.interact(state, self.catalog)

        self.assertEqual(event, ("refresh", 0))
        open_form.assert_not_called()
        self.assertTrue(state.details)
        self.assertIsNone(state.form)


if __name__ == "__main__":
    unittest.main()
