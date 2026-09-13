from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.workspace_data import Catalog


class MouseFocusTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def test_right_wheel_scrolls_without_stealing_roster_focus(self):
        state = workspace.Workspace("students")
        with patch.object(
            keys,
            "_read_key",
            side_effect=[keys.MouseScroll(90, 12, "down"), "back"],
        ), patch.object(screen, "_paint"), patch.object(
            screen, "_terminal_size", return_value=os.terminal_size((120, 24))
        ):
            self.assertIsNone(workspace._interact(state, self.catalog))

        self.assertFalse(state.details)
        self.assertEqual(state.selected, 0)
        self.assertEqual(state.detail_selected, 0)
        self.assertGreater(state.detail_scroll, 0)

    def test_left_wheel_does_not_take_focus_from_the_inspector(self):
        state = workspace.Workspace("students", details=True)
        with patch.object(
            keys,
            "_read_key",
            side_effect=[keys.MouseScroll(2, 12, "down")],
        ), patch.object(screen, "_paint"), patch.object(
            screen, "_terminal_size", return_value=os.terminal_size((120, 24))
        ):
            with self.assertRaises(StopIteration):
                workspace._interact(state, self.catalog)

        self.assertTrue(state.details)
        self.assertEqual(state.selected, 1)


if __name__ == "__main__":
    unittest.main()
