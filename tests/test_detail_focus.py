from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.board import Board
from xingyuan_sis.tui.workspace import student_inspector, view as workspace_view
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.inspector import render_inspector

from xingyuan_sis.tui.workspace import events as workspace_events


class DetailFocusTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def render(self, state):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ) as environment:
            environment.pop("NO_COLOR", None)
            return workspace_view.render(state, self.catalog)

    def test_tab_focus_is_visible_on_both_panel_heading_and_detail_item(self):
        state = workspace.Workspace("students")
        roster = self.render(state)
        plain = screen._ANSI_RE.sub("", "\n".join(roster.lines))
        self.assertIn("▌ 名册", plain)
        self.assertIn("  档案", plain)
        self.assertNotIn("即时预览", plain)

        state.set_focus(workspace.FocusArea.INSPECTOR)
        detail = self.render(state)
        plain = screen._ANSI_RE.sub("", "\n".join(detail.lines))
        self.assertIn("  名册", plain)
        self.assertIn("▌ 档案", plain)
        self.assertNotIn("阅读中", plain)
        self.assertTrue(any(screen._SURFACE_SELECTED in line for line in detail.lines))

    def test_selected_marker_sits_beside_the_specific_inspector_field(self):
        state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        row = state.current(self.catalog)
        targets = workspace_view.detail_targets("students", row, self.catalog, 42)
        state.detail_selected = next(
            index for index, (_, action) in enumerate(targets)
            if action == "field:branch"
        )
        detail = self.render(state)
        line = next(
            screen._ANSI_RE.sub("", raw)
            for raw in detail.lines
            if "物种" in screen._ANSI_RE.sub("", raw)
        )
        self.assertIn("> ", line)
        self.assertLess(line.index("物种"), line.index("> "))

    def test_selected_inspector_item_keeps_its_original_color_and_emphasis(self):
        state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        board = Board(40, 16)
        original_style = screen._TEXT_ACCENT + "\x1b[4m"
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ) as environment:
            environment.pop("NO_COLOR", None)
            render_inspector(
                board,
                state,
                self.catalog,
                0,
                30,
                [[("关联项目", original_style, "field:name")]],
            )
            raw = "\n".join(board.frame().lines)
        self.assertIn(screen._SURFACE_SELECTED, raw)
        self.assertIn(screen._TEXT_ACCENT, raw)
        self.assertIn("\x1b[4m", raw)
        self.assertIn("> 关联项目", screen._ANSI_RE.sub("", raw))

    def test_student_inspector_uses_current_archive_hierarchy(self):
        state = workspace.Workspace("students")
        row = state.current(self.catalog)
        lines = student_inspector.lines(row, self.catalog)
        plain = "\n".join(
            screen._ANSI_RE.sub("", "".join(text for text, _, _ in line))
            for line in lines
        )

        self.assertIn(row["name"], plain)
        self.assertIn(row["student_no"], plain)
        self.assertIn("性别", plain)
        self.assertIn("年龄", plain)
        self.assertIn("选课与成绩", plain)
        self.assertIn("个人信息", plain)
        self.assertIn("出生日期", plain)
        self.assertNotIn("详细信息", plain)
        self.assertNotIn("档案字段", plain)

    def test_arrows_move_selection_inside_focused_detail_pane(self):
        state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        with patch.object(keys, "_read_key", side_effect=["down", "back", "back", "back"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            workspace_events.interact(state, self.catalog)
        self.assertEqual(state.detail_selected, 1)
        self.assertEqual(state.selected, 0)

    def test_horizontal_arrows_choose_pane_directionally(self):
        state = workspace.Workspace("students")
        with patch.object(
            keys,
            "_read_key",
            side_effect=["right", "right", "down", "left", "left", "back", "back"],
        ), patch.object(screen, "_paint"), patch.object(
            screen, "_terminal_size", return_value=os.terminal_size((120, 35))
        ):
            workspace_events.interact(state, self.catalog)

        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)
        self.assertEqual(state.detail_selected, 1)
        self.assertEqual(state.selected, 0)

    def test_generic_inspector_uses_the_same_directional_event_path(self):
        state = workspace.Workspace(
            "courses",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        with patch.object(
            keys,
            "_read_key",
            side_effect=["down", "left", "back", "back"],
        ), patch.object(screen, "_paint"), patch.object(
            screen, "_terminal_size", return_value=os.terminal_size((120, 35))
        ):
            workspace_events.interact(state, self.catalog)

        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)
        self.assertEqual(state.detail_selected, 1)
        self.assertEqual(state.selected, 0)


if __name__ == "__main__":
    unittest.main()
