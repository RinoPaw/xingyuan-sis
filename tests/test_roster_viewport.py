import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.workspace import view as workspace_view
from xingyuan_sis.tui.workspace.data import Catalog

from xingyuan_sis.tui.workspace import events as workspace_events


class RosterViewportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def test_moving_up_inside_visible_window_does_not_scroll_page(self):
        size = (120, 42)  # The reclaimed notice row lets records 0–33 fit without scrolling.
        state = workspace.Workspace("students", selected=33)

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            workspace_view.render(state, self.catalog)
        self.assertEqual(state.roster_scroll, 0)

        with patch.object(keys, "_read_key", side_effect=["up", "back", "back"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            workspace_events.interact(state, self.catalog)

        self.assertEqual(state.selected, 32)
        self.assertEqual(state.roster_scroll, 0)

    def test_viewport_moves_only_after_selection_crosses_an_edge(self):
        size = (120, 42)
        state = workspace.Workspace("students", selected=30, roster_scroll=1)

        state.selected = 29
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            workspace_view.render(state, self.catalog)
        self.assertEqual(state.roster_scroll, 1)

        state.selected = 0
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            workspace_view.render(state, self.catalog)
        self.assertEqual(state.roster_scroll, 0)


if __name__ == "__main__":
    unittest.main()
