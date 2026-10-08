from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen
from xingyuan_sis.tui.layout import WorkspaceLayout
from xingyuan_sis.tui.workspace import view
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.state import ContentPanel, FocusArea, Workspace


class WorkspaceFooterTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)


    def test_student_footer_contains_only_search_across_workspaces_and_sizes(self):
        from xingyuan_sis.auth import Identity
        from xingyuan_sis.tui.workspace.commands import SEARCH, available

        student_no = self.catalog.records["students"][0]["student_no"]
        student = Identity(student_no, "student", student_no)
        student_catalog = Catalog(self.db, student)
        self.assertTrue(student_catalog.read_only)
        for key in ("students", "grades", "announcements"):
            self.assertEqual(available(student_catalog, key), (SEARCH,))
            for size in ((120, 35), (64, 20), (30, 12)):
                with self.subTest(collection=key, size=size), patch.object(
                    screen, "_terminal_size", return_value=os.terminal_size(size)
                ):
                    frame = view.render(Workspace(key), student_catalog)
                footer = screen._ANSI_RE.sub("", frame.lines[-1])
                self.assertIn("/ 搜索", footer)
                for forbidden in ("新增", "增加", "删除", "重置密码", "导入", "导出", "保存", "演示"):
                    self.assertNotIn(forbidden, footer)
                prohibited = {"create", "delete", "reset-password", "import", "export", "seed", "save"}
                self.assertFalse(prohibited & {region.action for region in frame.regions})

    def test_students_cannot_activate_hidden_write_commands_by_shortcut(self):
        from xingyuan_sis.auth import Identity
        from xingyuan_sis.tui import keys
        from xingyuan_sis.tui.workspace import events

        row = self.catalog.records["students"][0]
        identity = Identity(row["student_no"], "student", row["student_no"])
        catalog = Catalog(self.db, identity)
        for key in ("students", "grades", "announcements"):
            for shortcut in ("a", "d", "r", "i", "o", "g", "create", "delete", "reset-password", "import", "export", "seed"):
                with self.subTest(collection=key, shortcut=shortcut):
                    state = Workspace(key)
                    with patch.object(keys, "_read_key", side_effect=(shortcut, "refresh")), \
                         patch.object(screen, "_paint"), \
                         patch.object(screen, "_terminal_size", return_value=os.terminal_size((64, 20))):
                        self.assertEqual(events.interact(state, catalog), ("refresh", 0))
                    self.assertIsNone(state.form)
                    self.assertIsNone(state.field_session)
        self.assertIsNotNone(catalog.service.student_by_no(row["student_no"]))

    def test_filtered_student_footer_never_reveals_admin_commands(self):
        from xingyuan_sis.auth import Identity
        from xingyuan_sis.tui.workspace.commands import available

        student_no = self.catalog.records["students"][0]["student_no"]
        catalog = Catalog(self.db, Identity(student_no, "student", student_no))
        state = Workspace("students")
        state.commit_search(f"--no {student_no}")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((64, 20))):
            footer = screen._ANSI_RE.sub("", view.render(state, catalog).lines[-1])
        self.assertIn("清除筛选", footer)
        for forbidden in ("新增", "增加", "删除", "重置密码", "导入", "演示"):
            self.assertNotIn(forbidden, footer)
        self.assertEqual({c.action for c in available(catalog, state.key)}, {"search"})

    def test_admin_footer_still_exposes_authorized_actions(self):
        from xingyuan_sis.auth import Identity

        catalog = Catalog(self.db, Identity("Administrator", "admin"))
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            footer = screen._ANSI_RE.sub("", view.render(Workspace("students"), catalog).lines[-1])
        for command in ("/ 搜索", "A 增加", "D 删除", "R 重置密码"):
            self.assertIn(command, footer)

    def test_layout_reserves_only_the_footer(self):
        for layout in (WorkspaceLayout(80, 18), WorkspaceLayout(120, 35)):
            self.assertEqual(
                layout.panel_capacity("students"),
                layout.height - layout.panel_content_row("students") - 1,
            )

    def test_notice_state_does_not_render_a_second_footer_row(self):
        state = Workspace("students")
        state.notice = "THIS NOTICE MUST NOT BE RENDERED"
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            frame = view.render(state, self.catalog)
        self.assertFalse(any("THIS NOTICE MUST NOT BE RENDERED" in line for line in frame.lines))
        self.assertTrue(frame.lines[-1].strip())

    def test_inspector_has_no_scroll_hint_row_above_footer(self):
        state = Workspace(
            "students",
            focus=FocusArea.INSPECTOR,
            content_panel=ContentPanel.INSPECTOR,
        )
        state.detail_selected = 10
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((30, 12))):
            frame = view.render(state, self.catalog)
        penultimate = screen._ANSI_RE.sub("", frame.lines[-2]).strip()
        self.assertNotRegex(penultimate, r"^\d+[–-]\d+\s*/\s*\d+$")
        self.assertTrue(frame.lines[-1].strip())


if __name__ == "__main__":
    unittest.main()
