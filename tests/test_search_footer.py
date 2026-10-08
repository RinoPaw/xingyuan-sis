"""Search footer and temporary roster-filter navigation in real workspace frames."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen
from xingyuan_sis.tui.workspace import events, forms, view
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.state import ContentPanel, FocusArea, Workspace


class SearchFooterFlowTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        db = Path(temporary.name) / "campus.db"
        initialize_database(db)
        seed_demo(db)
        self.catalog = Catalog(db)

    def interact(self, state, sequence, size=(64, 20)):
        with patch.object(keys, "_read_key", side_effect=sequence), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return events.interact(state, self.catalog)

    def render(self, state, size=(64, 20)):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return view.render(state, self.catalog)

    def test_search_shortcut_opens_footer_input_without_changing_roster(self):
        for size in ((120, 35), (64, 20), (30, 12)):
            with self.subTest(size=size):
                state = Workspace("students", selected=3, roster_scroll=2)
                initial = state.current(self.catalog)["id"]
                self.assertEqual(self.interact(state, ["/"], size), ("search", 0))
                self.assertTrue(state.searching)
                self.assertEqual(state.current(self.catalog)["id"], initial)
                frame = self.render(state, size)
                body = "\\n".join(screen._ANSI_RE.sub("", line) for line in frame.lines[:-1])
                footer = screen._ANSI_RE.sub("", frame.lines[-1])
                self.assertIn("搜索", footer)
                self.assertIn("名册", body)
                self.assertNotIn("搜索 >", body)
                self.assertNotIn("Esc 清除筛选", footer)

    def test_enter_filters_and_escape_restores_original_position(self):
        state = Workspace("students", selected=4, roster_scroll=3,
                          focus=FocusArea.INSPECTOR, content_panel=ContentPanel.INSPECTOR)
        original_id = state.current(self.catalog)["id"]
        keyword = self.catalog.records["students"][8]["student_no"]
        self.assertEqual(self.interact(state, ["search"]), ("search", 0))
        with patch("builtins.input", return_value=keyword), patch.object(screen, "_paint"):
            forms.read_search(state, self.catalog)
        self.assertEqual(state.query, keyword)
        self.assertEqual(len(state.rows(self.catalog)), 1)
        self.assertEqual(state.selected, 0)
        self.assertEqual(state.focus, FocusArea.ROSTER)
        self.assertEqual(state.content_panel, ContentPanel.ROSTER)
        self.assertIn("Esc 清除筛选", screen._ANSI_RE.sub("", self.render(state).lines[-1]))
        self.assertIsNotNone(state.search_context)
        self.assertEqual(self.interact(state, ["back", "refresh"]), ("refresh", 0))
        self.assertEqual(state.query, "")
        self.assertIsNone(state.search_context)
        self.assertEqual(state.selected, 4)
        self.assertEqual(state.roster_scroll, 3)
        self.assertEqual(state.current(self.catalog)["id"], original_id)
        self.assertEqual(state.focus, FocusArea.ROSTER)
        self.assertNotIn("Esc 清除筛选", screen._ANSI_RE.sub("", self.render(state).lines[-1]))

    def test_escape_during_entry_does_not_mutate_list_or_selection(self):
        state = Workspace("students", selected=2)
        original = (state.query, state.selected)
        state.searching = True
        with patch("xingyuan_sis.tui.workspace.forms.read_inline_input", side_effect=KeyboardInterrupt), \
             patch.object(screen, "_paint"):
            with self.assertRaises(KeyboardInterrupt):
                forms.read_search(state, self.catalog)
        self.assertEqual((state.query, state.selected), original)
        self.assertFalse(state.searching)
        self.assertIsNone(state.search_context)

    def test_invalid_search_does_not_override_existing_filter(self):
        state = Workspace("students", selected=2)
        state.commit_search("--year 2026")
        previous = (state.query, state.selected, state.search_context)
        with patch("builtins.input", return_value="--year not-a-number"), \
             patch.object(screen, "_paint"):
            forms.read_search(state, self.catalog)
        self.assertEqual((state.query, state.selected, state.search_context), previous)
        self.assertIn("未完成", state.notice)

    def test_research_updates_filter_without_losing_original_restore_point(self):
        state = Workspace("students", selected=9, roster_scroll=7)
        first, second = (row["student_no"] for row in self.catalog.records["students"][:2])
        with patch("builtins.input", return_value=first), patch.object(screen, "_paint"):
            forms.read_search(state, self.catalog)
        with patch("builtins.input", return_value=second), patch.object(screen, "_paint"):
            forms.read_search(state, self.catalog)
        self.assertEqual([r["student_no"] for r in state.rows(self.catalog)], [second])
        state.clear_search()
        self.assertEqual((state.query, state.selected, state.roster_scroll), ("", 9, 7))

    def test_empty_query_from_unfiltered_roster_does_not_jump_selection(self):
        state = Workspace("students", selected=12, roster_scroll=10,
                          focus=FocusArea.INSPECTOR, content_panel=ContentPanel.INSPECTOR)
        with patch("builtins.input", return_value=""), patch.object(screen, "_paint"):
            forms.read_search(state, self.catalog)
        self.assertEqual((state.query, state.selected, state.roster_scroll), ("", 12, 10))
        self.assertEqual(state.focus, FocusArea.ROSTER)
        self.assertIsNone(state.search_context)

    def test_empty_search_restores_list_and_footer(self):
        state = Workspace("students", selected=7)
        state.commit_search(self.catalog.records["students"][0]["student_no"])
        with patch("builtins.input", return_value=""), patch.object(screen, "_paint"):
            forms.read_search(state, self.catalog)
        self.assertFalse(state.query)
        self.assertIsNone(state.search_context)
        self.assertEqual(state.selected, 7)
        self.assertNotIn("Esc 清除筛选", screen._ANSI_RE.sub("", self.render(state).lines[-1]))

    def test_empty_result_can_escape_and_restore(self):
        state = Workspace("students", selected=5)
        state.commit_search("NO-MATCH-QUERY")
        self.assertFalse(state.rows(self.catalog))
        self.assertIn("没有匹配的记录", "\\n".join(
            screen._ANSI_RE.sub("", line) for line in self.render(state).lines
        ))
        self.assertEqual(self.interact(state, ["back", "refresh"]), ("refresh", 0))
        self.assertEqual(state.selected, 5)
        self.assertTrue(state.rows(self.catalog))

    def test_search_context_survives_related_navigation_and_is_cleared_on_switch(self):
        state = Workspace("students", selected=3)
        state.commit_search(self.catalog.records["students"][3]["student_no"])
        related_key, related = self.catalog.related("students", state.current(self.catalog))
        self.assertTrue(related)
        state.visit(related_key, str(related[0]["id"]), self.catalog)
        self.assertIsNone(state.search_context)
        state.restore(self.catalog)
        self.assertIsNotNone(state.search_context)
        self.assertEqual(len(state.rows(self.catalog)), 1)
        state.clear_search()
        self.assertEqual(state.selected, 3)
        state.switch("courses")
        self.assertIsNone(state.search_context)
        self.assertFalse(state.searching)

    def test_footer_input_uses_actual_last_terminal_row(self):
        state = Workspace("students")
        for size in ((120, 35), (64, 20), (30, 12)):
            with self.subTest(size=size), \
                 patch("xingyuan_sis.tui.workspace.forms.read_inline_input", return_value="") as reader, \
                 patch.object(screen, "_paint"), \
                 patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
                forms.read_search(state, self.catalog)
                _, kwargs = reader.call_args
                self.assertEqual(kwargs["row"], len(self.render(state, size).lines))
                self.assertGreaterEqual(kwargs["column"], 1)
                self.assertGreaterEqual(kwargs["width"], 3)


if __name__ == "__main__":
    unittest.main()
