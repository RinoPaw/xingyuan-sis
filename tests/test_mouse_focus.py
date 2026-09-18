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

from xingyuan_sis.tui.workspace import events as workspace_events

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
        size = os.terminal_size((120, 24))
        with patch.object(screen, "_terminal_size", return_value=size):
            frame = workspace_view.render(state, self.catalog)
        region = next(region for region in frame.regions if region.action == "focus-details")
        x, y = region.x, min(region.y, 12)

        with patch.object(
            keys,
            "_read_key",
            side_effect=[keys.MouseScroll(x, y, "down"), "back", "back"],
        ), patch.object(screen, "_paint"), patch.object(
            screen, "_terminal_size", return_value=size
        ):
            self.assertIsNone(workspace_events.interact(state, self.catalog))

        self.assertFalse(state.details)
        self.assertEqual(state.selected, 0)
        self.assertEqual(state.detail_selected, 0)
        self.assertGreater(state.detail_scroll, 0)

    def test_focused_inspector_wheel_uses_the_same_geometry_as_arrow_navigation(self):
        size = os.terminal_size((120, 24))
        for collection in ("students", "courses"):
            with self.subTest(collection=collection):
                state = workspace.Workspace(collection, details=True)
                with patch.object(screen, "_terminal_size", return_value=size):
                    frame = workspace_view.render(state, self.catalog)
                    targets = workspace_events.detail_targets(state, self.catalog)
                actions = [action for _, action in targets]
                expected = workspace_view.directional_target(
                    collection,
                    actions,
                    state.detail_selected,
                    "down",
                )
                region = next(region for region in frame.regions if region.action == "focus-details")

                with patch.object(
                    keys,
                    "_read_key",
                    side_effect=[keys.MouseScroll(region.x, region.y, "down")],
                ), patch.object(screen, "_paint"), patch.object(
                    screen, "_terminal_size", return_value=size
                ):
                    with self.assertRaises(StopIteration):
                        workspace_events.interact(state, self.catalog)

                self.assertEqual(state.detail_selected, expected)
                self.assertTrue(state.details)

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
                workspace_events.interact(state, self.catalog)

        self.assertTrue(state.details)
        self.assertEqual(state.selected, 1)


if __name__ == "__main__":
    unittest.main()
