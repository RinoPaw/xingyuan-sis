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

    def test_browse_actions_live_only_in_the_command_footer(self):
        state = workspace.Workspace("students")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            frame = workspace_view.render(state, self.catalog)
        actions = {region.action for region in frame.regions}
        for command in ("search", "create", "delete", "reset-password"):
            self.assertNotIn(command, actions)
        footer = screen._ANSI_RE.sub("", frame.lines[-1])
        for label in ("/ 搜索", "A 增加", "D 删除", "R 重置密码"):
            self.assertIn(label, footer)
        for label in ("Tab", "方向键", "Enter", "Esc", "I 导入", "G 演示"):
            self.assertNotIn(label, footer)

    def test_create_save_remains_local_to_transaction(self):
        state = workspace.Workspace("students")
        workspace_forms.open_form(state, self.catalog, "create")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            creating = workspace_view.render(state, self.catalog)
        save = next(region for region in creating.regions if region.action == "save")
        self.assertLess(save.y, 34)

    def test_create_student_commits_and_focuses_saved_record_without_animation(self):
        state = workspace.Workspace("students")
        sample = state.current(self.catalog)
        workspace_forms.open_form(state, self.catalog, "create")
        state.form.values.update(
            student_no="29999998",
            name="无动画新增测试",
            family=sample["family"],
            branch=sample["branch"],
            enrollment_year=sample["enrollment_year"],
        )

        record_id = workspace_forms.apply_form(state, self.catalog)

        created = self.catalog.service.student_by_no("29999998")
        self.assertIsNotNone(created)
        self.assertEqual(created["id"], record_id)
        self.assertIsNone(state.form)
        self.assertEqual(state.focus, workspace.FocusArea.INSPECTOR)
        self.assertEqual(state.current(self.catalog)["id"], record_id)

    def test_delete_shortcut_preserves_selected_record(self):
        state = workspace.Workspace("students", selected=15)
        captured = []

        def capture(_state, _catalog, action):
            if action == "delete":
                captured.append(_state.selected)

        with patch.object(keys, "_read_key", side_effect=["d", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch.object(workspace_events, "open_form", side_effect=capture):
            event = workspace_events.interact(state, self.catalog)

        self.assertEqual(event, ("refresh", 0))
        self.assertEqual(captured, [15])
        self.assertEqual(state.selected, 15)

    def test_search_shortcut_returns_to_roster_from_inspector(self):
        state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            frame = workspace_view.render(state, self.catalog)
        self.assertFalse(any(region.action == "search" for region in frame.regions))

        with patch.object(keys, "_read_key", side_effect=["/"]), \
             patch.object(screen, "_paint"), patch.object(
                 screen, "_terminal_size", return_value=os.terminal_size((120, 35))
             ):
            event = workspace_events.interact(state, self.catalog)
        self.assertEqual(event, ("search", 0))

        with redirect_stdout(StringIO()), patch.object(workspace_forms, "read_inline_input", return_value=""), \
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
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
            detail_scroll=3,
            detail_selected=6,
        )
        workspace_forms.open_form(state, self.catalog, "delete")

        self.assertEqual(state.focus, workspace.FocusArea.INSPECTOR)
        self.assertEqual(state.content_panel, workspace.ContentPanel.INSPECTOR)
        self.assertIsNotNone(state.form.return_to)
        self.assertEqual(state.form.return_to.focus, workspace.FocusArea.INSPECTOR)
        self.assertEqual(state.form.return_to.detail_scroll, 3)
        self.assertEqual(state.form.return_to.detail_selected, 6)

        workspace_forms.cancel_form(state)
        self.assertEqual(state.focus, workspace.FocusArea.INSPECTOR)
        self.assertEqual(state.content_panel, workspace.ContentPanel.INSPECTOR)
        self.assertEqual(state.detail_scroll, 3)
        self.assertEqual(state.detail_selected, 6)

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
        successor = state.rows(self.catalog)[5]
        workspace_forms.open_form(state, self.catalog, "delete")
        workspace_forms.apply_form(state, self.catalog)

        self.assertIsNone(self.catalog.service.student_by_no(original["student_no"]))
        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)
        self.assertEqual(state.content_panel, workspace.ContentPanel.ROSTER)
        self.assertEqual(state.selected, 4)
        self.assertEqual(state.current(self.catalog)["id"], successor["id"])
        self.assertEqual(state.detail_scroll, 0)
        self.assertEqual(state.detail_selected, 0)

    def test_deleting_middle_student_selects_next_and_keeps_arrow_navigation(self):
        state = workspace.Workspace("students", selected=4)
        before = state.rows(self.catalog)
        deleted, successor, predecessor = before[4], before[5], before[3]
        workspace_forms.open_form(state, self.catalog, "delete")
        workspace_forms.apply_form(state, self.catalog)

        self.assertIsNone(self.catalog.service.student_by_no(deleted["student_no"]))
        self.assertEqual(state.selected, 4)
        self.assertEqual(state.current(self.catalog)["id"], successor["id"])
        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)

        with patch.object(keys, "_read_key", side_effect=["up", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            workspace_events.interact(state, self.catalog)
        self.assertEqual(state.current(self.catalog)["id"], predecessor["id"])

        with patch.object(keys, "_read_key", side_effect=["down", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            workspace_events.interact(state, self.catalog)
        self.assertEqual(state.current(self.catalog)["id"], successor["id"])

    def test_deleting_final_student_selects_previous(self):
        rows = self.catalog.rows("students")
        state = workspace.Workspace("students", selected=len(rows) - 1)
        workspace_forms.open_form(state, self.catalog, "delete")
        workspace_forms.apply_form(state, self.catalog)

        self.assertEqual(state.selected, len(rows) - 2)
        self.assertEqual(state.current(self.catalog)["id"], rows[-2]["id"])
        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)

    def test_deleting_only_visible_student_leaves_no_selection(self):
        student = self.catalog.rows("students")[0]
        state = workspace.Workspace("students", query=f"--no {student['student_no']}")
        self.assertEqual(len(state.rows(self.catalog)), 1)
        workspace_forms.open_form(state, self.catalog, "delete")
        workspace_forms.apply_form(state, self.catalog)

        self.assertFalse(state.rows(self.catalog))
        self.assertIsNone(state.current(self.catalog))
        self.assertEqual(state.selected, 0)
        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)

    def test_deleting_other_collection_also_selects_next(self):
        rows = self.catalog.rows("grades")
        self.assertGreater(len(rows), 1)
        state = workspace.Workspace("grades")
        workspace_forms.open_form(state, self.catalog, "delete")
        workspace_forms.apply_form(state, self.catalog)

        self.assertEqual(state.selected, 0)
        self.assertEqual(state.current(self.catalog)["id"], rows[1]["id"])
        self.assertEqual(state.focus, workspace.FocusArea.ROSTER)

    def test_failed_delete_keeps_form_and_selection(self):
        state = workspace.Workspace("students", selected=4)
        original = state.current(self.catalog)
        workspace_forms.open_form(state, self.catalog, "delete")
        with patch.object(self.catalog, "delete", side_effect=ValueError("删除失败")):
            with self.assertRaisesRegex(ValueError, "删除失败"):
                workspace_forms.apply_form(state, self.catalog)
        self.assertIsNotNone(state.form)
        self.assertEqual(state.selected, 4)
        self.assertEqual(state.current(self.catalog)["id"], original["id"])

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
        self.assertIn("删除学生", text)
        self.assertNotIn("确认删除以下记录？", text)
        self.assertIn(selected["name"], text)
        self.assertIn(neighbor["name"], text)
        self.assertIn("姓名", text)
        self.assertIn("学号", text)
        self.assertIn("同时删除", text)
        self.assertIn("删除后无法撤销", text)
        self.assertIn("确认删除", text)
        self.assertNotIn("\n档案", text)

        record_line = next(line for line in plain_lines if "姓名" in line and selected["name"] in line)
        id_line = next(line for line in plain_lines if "学号" in line and selected["student_no"] in line)
        record_value = record_line.rfind(selected["name"])
        id_value = id_line.rfind(selected["student_no"])
        self.assertEqual(
            screen._display_width(record_line[:record_value]),
            screen._display_width(id_line[:id_value]),
        )

    def test_delete_defaults_to_cancel_and_repeated_enter_cannot_delete(self):
        state = workspace.Workspace("students", selected=2)
        original = state.current(self.catalog)
        with patch.object(keys, "_read_key", side_effect=["delete", "select", "refresh"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 26))):
            event = workspace_events.interact(state, self.catalog)
        self.assertEqual(event, ("refresh", 0))
        self.assertIsNone(state.form)
        self.assertIsNotNone(self.catalog.service.student_by_no(original["student_no"]))

    def test_delete_confirmation_requires_explicit_keyboard_selection(self):
        state = workspace.Workspace("students", selected=2)
        original = state.current(self.catalog)
        with patch.object(keys, "_read_key", side_effect=["delete", "left", "select"]), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 26))):
            self.assertEqual(workspace_events.interact(state, self.catalog), ("save", 0))
        self.assertEqual(state.form.position, 0)
        workspace_forms.apply_form(state, self.catalog)
        self.assertIsNone(self.catalog.service.student_by_no(original["student_no"]))

    def test_delete_buttons_are_near_warning_and_clickable_in_wide_and_compact_modes(self):
        for width, height in ((120, 35), (64, 20), (30, 12)):
            with self.subTest(size=(width, height)):
                state = workspace.Workspace("students", selected=1)
                workspace_forms.open_form(state, self.catalog, "delete")
                with patch.object(screen, "_terminal_size", return_value=os.terminal_size((width, height))):
                    frame = workspace_view.render(state, self.catalog)
                plain = [screen._ANSI_RE.sub("", line) for line in frame.lines]
                confirm = next(region for region in frame.regions if region.action == "confirm-action")
                cancel = next(region for region in frame.regions if region.action == "cancel-action")
                risk_y = next(i + 1 for i, line in enumerate(plain) if "删除后无法撤销" in line)
                self.assertGreater(confirm.y, risk_y)
                self.assertLessEqual(confirm.y - risk_y, 3)
                self.assertLess(confirm.y, height)
                self.assertLess(cancel.y, height)
                self.assertIn("Enter 选择", plain[-1])

    def test_delete_mouse_actions_have_distinct_meanings(self):
        for action, event_sequence, expect_save in (
            ("confirm-action", None, True),
            ("cancel-action", "refresh", False),
        ):
            with self.subTest(action=action):
                state = workspace.Workspace("students", selected=2)
                original = state.current(self.catalog)
                workspace_forms.open_form(state, self.catalog, "delete")
                with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 26))):
                    frame = workspace_view.render(state, self.catalog)
                region = next(region for region in frame.regions if region.action == action)
                sequence = [keys.MouseClick(region.x, region.y)]
                if event_sequence:
                    sequence.append(event_sequence)
                with patch.object(keys, "_read_key", side_effect=sequence), \
                     patch.object(screen, "_paint"), \
                     patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 26))):
                    result = workspace_events.interact(state, self.catalog)
                self.assertEqual(result, ("save", 0) if expect_save else ("refresh", 0))
                if expect_save:
                    workspace_forms.apply_form(state, self.catalog)
                    self.assertIsNone(self.catalog.service.student_by_no(original["student_no"]))
                else:
                    self.assertIsNone(state.form)
                    self.assertIsNotNone(self.catalog.service.student_by_no(original["student_no"]))

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
