from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace, workspace_events, workspace_view
from xingyuan_sis.tui.workspace_data import Catalog


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

    def test_arrow_focus_can_choose_edit_and_enter_opens_it(self):
        state = workspace.Workspace("students")
        with patch.object(keys, "_read_key", side_effect=["up", "right", "right", "select", "back"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch.object(workspace_events, "open_form") as open_form:
            workspace._interact(state, self.catalog)

        open_form.assert_called_once_with(state, self.catalog, "edit")

    def test_action_shortcuts_remain_direct(self):
        for key, action in (("create", "create"), ("edit", "edit"), ("delete", "delete")):
            state = workspace.Workspace("students")
            with self.subTest(key=key), \
                 patch.object(keys, "_read_key", side_effect=[key, "back"]), \
                 patch.object(screen, "_paint"), \
                 patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
                 patch.object(workspace_events, "open_form") as open_form:
                workspace._interact(state, self.catalog)
            open_form.assert_called_once_with(state, self.catalog, action)


if __name__ == "__main__":
    unittest.main()
