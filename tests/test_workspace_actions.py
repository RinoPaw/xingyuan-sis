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

    def test_record_commands_are_the_toolbar_and_footer_source(self):
        state = workspace.Workspace("students")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            frame = workspace_view.render(state, self.catalog)

        actions = {region.action: region for region in frame.regions}
        for action in ("search", "create", "delete", "reset-password"):
            self.assertIn(action, actions)
            self.assertLess(actions[action].y, 35)
        self.assertNotIn("edit", actions)

        footer = screen._ANSI_RE.sub("", frame.lines[-1])
        self.assertIn("Enter 打开", footer)
        self.assertIn("Esc 返回", footer)
        self.assertIn("/ 搜索", footer)
        self.assertIn("A 增加", footer)
        self.assertIn("D 删除", footer)
        self.assertNotIn("E 编辑", footer)
        self.assertFalse(any(region.y == 35 for region in frame.regions))

    def test_toolbar_enter_invokes_the_same_delete_command(self):
        state = workspace.Workspace("students", selected=15)
        selected_at_delete: list[int] = []

        def capture(_state, _catalog, action):
            if action == "delete":
                selected_at_delete.append(_state.selected)

        with patch.object(
            keys, "_read_key",
            side_effect=["focus_prev", "right", "right", "select", "back"],
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

    def test_literal_command_shortcuts_open_the_same_transaction_forms(self):
        for key, action in (("a", "create"), ("d", "delete")):
            state = workspace.Workspace("students")
            with self.subTest(key=key), \
                 patch.object(keys, "_read_key", side_effect=[key, "back"]), \
                 patch.object(screen, "_paint"), \
                 patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
                 patch.object(workspace_events, "open_form") as open_form:
                workspace_events.interact(state, self.catalog)
            open_form.assert_called_once_with(state, self.catalog, action)

    def test_removed_edit_shortcut_has_no_hidden_edit_mode(self):
        state = workspace.Workspace("students")
        with patch.object(keys, "_read_key", side_effect=["e", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch.object(workspace_events, "open_form") as open_form:
            event = workspace_events.interact(state, self.catalog)

        self.assertEqual(event, ("refresh", 0))
        open_form.assert_not_called()
        self.assertFalse(state.details)
        self.assertIsNone(state.form)
        self.assertIsNone(state.field_session)

    def test_only_escape_is_global_back(self):
        state = workspace.Workspace("students")
        with patch.object(keys, "_read_key", side_effect=["q", "0", " ", "backspace", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            event = workspace_events.interact(state, self.catalog)
        self.assertEqual(event, ("refresh", 0))
        self.assertFalse(state.details)


if __name__ == "__main__":
    unittest.main()
