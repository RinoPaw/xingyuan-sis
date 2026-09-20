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
