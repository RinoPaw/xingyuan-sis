from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen, workspace
from xingyuan_sis.tui.workspace import events as workspace_events, forms as workspace_forms, view as workspace_view
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

    def test_create_save_is_archive_local_but_browse_delete_stays_in_toolbar(self):
        state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            browsing = workspace_view.render(state, self.catalog)
        delete = next(region for region in browsing.regions if region.action == "delete")

        workspace_forms.open_form(state, self.catalog, "create")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            creating = workspace_view.render(state, self.catalog)
        save = next(region for region in creating.regions if region.action == "save")

        self.assertLess(delete.y, save.y)
        self.assertEqual(save.y, 34)
        self.assertFalse(any(
            region.action == "delete" and region.y == save.y
            for region in browsing.regions
        ))

    def test_toolbar_enter_invokes_the_same_delete_command(self):
        state = workspace.Workspace("students", selected=15)
        selected_at_delete: list[int] = []

        def capture(_state, _catalog, action):
            if action == "delete":
                selected_at_delete.append(_state.selected)

        with patch.object(
            keys, "_read_key",
            side_effect=["focus", "focus", "right", "right", "select", "refresh"],
        ), patch.object(screen, "_paint"), patch.object(
            screen, "_terminal_size", return_value=os.terminal_size((120, 35))
        ), patch.object(workspace_events, "open_form", side_effect=capture):
            event = workspace_events.interact(state, self.catalog)

        self.assertEqual(event, ("refresh", 0))
        self.assertEqual(selected_at_delete, [15])
        self.assertEqual(state.selected, 15)

    def test_toolbar_focus_keeps_current_record_as_weak_context_only(self):
        state = workspace.Workspace("students", selected=15, focus=workspace.FocusArea.TOOLBAR)
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
        plain = screen._ANSI_RE.sub("", selected_line)
        self.assertIn("· ", plain)
        self.assertIn(screen._TEXT_SECONDARY, selected_line)
        self.assertIn(screen._TEXT_PRIMARY, selected_line)
        self.assertNotIn(screen._SURFACE_INTERACTIVE, selected_line)
        self.assertNotIn(screen._SURFACE_SELECTED, selected_line)
        self.assertNotIn(screen._TEXT_ACCENT, selected_line)

    def test_search_click_does_not_promote_inspector_to_selected_state(self):
        state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            frame = workspace_view.render(state, self.catalog)
        search = next(region for region in frame.regions if region.action == "search")

        with patch.object(keys, "_read_key", side_effect=[keys.MouseClick(search.x, search.y)]), \
             patch.object(screen, "_paint"), patch.object(
                 screen, "_terminal_size", return_value=os.terminal_size((120, 35))
             ):
            event = workspace_events.interact(state, self.catalog)
        self.assertEqual(event, ("search", 0))

        with redirect_stdout(StringIO()), patch.object(workspace_forms, "read_input", return_value=""), \
             patch.object(screen, "_paint"), patch.object(
                 screen, "_terminal_size", return_value=os.terminal_size((120, 35))
             ):
            workspace_forms.read_search(state, self.catalog)

        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)
        self.assertEqual(state.content_panel, workspace.ContentPanel.ROSTER)

    def test_delete_panel_temporarily_owns_focus_then_escape_restores_exact_context(self):
        state = workspace.Workspace(
            "students",
            selected=4,
            focus=workspace.FocusArea.TOOLBAR,
            content_panel=workspace.ContentPanel.INSPECTOR,
            detail_scroll=3,
            detail_selected=6,
            action_selected=2,
        )
        workspace_forms.open_form(state, self.catalog, "delete")

        self.assertEqual(state.focus, workspace.FocusArea.INSPECTOR)
        self.assertEqual(state.content_panel, workspace.ContentPanel.INSPECTOR)
        self.assertIsNotNone(state.form.return_to)
        self.assertEqual(state.form.return_to.focus, workspace.FocusArea.TOOLBAR)
        self.assertEqual(state.form.return_to.detail_scroll, 3)
        self.assertEqual(state.form.return_to.detail_selected, 6)
        self.assertEqual(state.form.return_to.action_selected, 2)

        workspace_forms.cancel_form(state)
        self.assertEqual(state.focus, workspace.FocusArea.TOOLBAR)
        self.assertEqual(state.content_panel, workspace.ContentPanel.INSPECTOR)
        self.assertEqual(state.detail_scroll, 3)
        self.assertEqual(state.detail_selected, 6)
        self.assertEqual(state.action_selected, 2)

    def test_delete_confirmation_restores_the_same_context_after_commit(self):
        state = workspace.Workspace(
            "students",
            selected=4,
            focus=workspace.FocusArea.ROSTER,
            content_panel=workspace.ContentPanel.ROSTER,
            detail_scroll=2,
            detail_selected=5,
        )
        original = state.current(self.catalog)
        workspace_forms.open_form(state, self.catalog, "delete")
        workspace_forms.apply_form(state, self.catalog)

        self.assertIsNone(self.catalog.service.student_by_no(original["student_no"]))
        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)
        self.assertEqual(state.content_panel, workspace.ContentPanel.ROSTER)
        self.assertEqual(state.detail_scroll, 2)
        self.assertEqual(state.detail_selected, 5)

    def test_deleted_student_can_leave_an_empty_slot_until_up_or_down_selects_a_neighbor(self):
        state = workspace.Workspace("students", selected=4)
        original = state.current(self.catalog)
        workspace_forms.open_form(state, self.catalog, "delete")
        workspace_forms.apply_form(state, self.catalog)
        rows = state.rows(self.catalog)
        state.leave_roster_gap(4)

        self.assertIsNone(self.catalog.service.student_by_no(original["student_no"]))
        self.assertIsNone(state.current(self.catalog))
        self.assertEqual(state.roster_gap, 4)
        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)

        with patch.object(keys, "_read_key", side_effect=["up", "refresh"]), \
             patch.object(screen, "_paint"), patch.object(
                 screen, "_terminal_size", return_value=os.terminal_size((120, 35))
             ):
            workspace_events.interact(state, self.catalog)
        self.assertIsNone(state.roster_gap)
        self.assertEqual(state.current(self.catalog)["id"], rows[3]["id"])

        state.leave_roster_gap(4)
        with patch.object(keys, "_read_key", side_effect=["down", "refresh"]), \
             patch.object(screen, "_paint"), patch.object(
                 screen, "_terminal_size", return_value=os.terminal_size((120, 35))
             ):
            workspace_events.interact(state, self.catalog)
        self.assertIsNone(state.roster_gap)
        self.assertEqual(state.current(self.catalog)["id"], rows[4]["id"])

    def test_toolbar_return_to_roster_resolves_gap_to_the_next_student(self):
        state = workspace.Workspace("students", selected=4)
        rows = state.rows(self.catalog)
        state.leave_roster_gap(4)
        self.assertIsNone(state.current(self.catalog))

        state.set_focus(workspace.FocusArea.TOOLBAR)
        state.focus_content()

        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)
        self.assertIsNone(state.roster_gap)
        self.assertEqual(state.current(self.catalog)["id"], rows[4]["id"])

    def test_wide_delete_keeps_roster_and_replaces_inspector_with_aligned_panel(self):
        state = workspace.Workspace("students", selected=1)
        rows = state.rows(self.catalog)
        selected = rows[1]
        neighbor = rows[0]
        workspace_forms.open_form(state, self.catalog, "delete")

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            frame = workspace_view.render(state, self.catalog)

        plain_lines = [screen._ANSI_RE.sub("", line) for line in frame.lines]
        text = "\n".join(plain_lines)
        self.assertIn("删除记录", text)
        self.assertIn("确认删除以下记录？", text)
        self.assertIn(selected["name"], text)
        self.assertIn(neighbor["name"], text)
        self.assertIn("记录", text)
        self.assertIn("标识", text)
        self.assertIn("影响", text)
        self.assertIn("风险", text)
        self.assertIn("确认删除", text)
        self.assertNotIn("\n档案", text)

        record_line = next(line for line in plain_lines if "记录" in line and selected["name"] in line)
        id_line = next(line for line in plain_lines if "标识" in line and selected["student_no"] in line)
        record_value = record_line.rfind(selected["name"])
        id_value = id_line.rfind(selected["student_no"])
        self.assertEqual(
            screen._display_width(record_line[:record_value]),
            screen._display_width(id_line[:id_value]),
        )

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
        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)
        self.assertIsNone(state.form)
        self.assertIsNone(state.field_session)

    def test_only_escape_is_global_back(self):
        state = workspace.Workspace("students")
        with patch.object(keys, "_read_key", side_effect=["q", "0", " ", "backspace", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            event = workspace_events.interact(state, self.catalog)
        self.assertEqual(event, ("refresh", 0))
        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)


if __name__ == "__main__":
    unittest.main()
