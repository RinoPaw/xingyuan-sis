from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.schema import Field
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen, workspace
from xingyuan_sis.tui.workspace import field_session as workspace_field
from xingyuan_sis.tui.workspace import inspector, view as workspace_view
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.picker import prepare_candidates
from xingyuan_sis.tui.workspace.state import FieldSession, FocusArea, ContentPanel


class PickerSemanticsTests(unittest.TestCase):
    def test_current_value_is_not_a_candidate(self):
        session = FieldSession(
            fields=(Field("choice", "选项"),),
            values={"choice": "B"},
            original={"choice": "B"},
            anchor_key="choice",
            options=[("A", "A"), ("B", "B"), ("C", "C")],
            option_index=1,
        )

        prepare_candidates(session)

        self.assertEqual(session.options, [("A", "A"), ("C", "C")])
        self.assertEqual(session.option_index, 0)

    def test_candidate_text_keeps_field_column_and_secondary_style(self):
        target = "field:choice"
        lines = [[
            ("字段  ", screen._TEXT_SECONDARY, ""),
            ("B", screen._TEXT_PRIMARY, target),
        ]]
        session = FieldSession(
            fields=(Field("choice", "选项"),),
            values={"choice": "B"},
            original={"choice": "B"},
            anchor_key="choice",
            options=[("A", "A"), ("B", "B"), ("C", "C")],
            option_index=1,
        )

        expanded = inspector.expand_options(lines, session)
        field_indent = inspector._target_indent(expanded, target)
        candidate = expanded[1]
        candidate_indent = 0
        candidate_segment = None
        for segment in candidate:
            if segment[2].startswith("option:"):
                candidate_segment = segment
                break
            candidate_indent += screen._display_width(segment[0])

        self.assertEqual(candidate_indent, field_indent)
        self.assertIsNotNone(candidate_segment)
        self.assertEqual(candidate_segment[1], screen._TEXT_SECONDARY)
        self.assertNotIn("B", [label for _, label in session.options])

    def test_selected_marker_uses_left_gutter_without_shifting_candidate(self):
        with TemporaryDirectory() as temp:
            db = Path(temp) / "test.db"
            initialize_database(db)
            seed_demo(db)
            catalog = Catalog(db)
            state = workspace.Workspace(
                "students",
                focus=FocusArea.INSPECTOR,
                content_panel=ContentPanel.INSPECTOR,
            )
            workspace_field.start(state, catalog, "status")
            workspace_field.edit_current(state, catalog)

            with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
                frame = workspace_view.render(state, catalog)

        field_region = max(
            (region for region in frame.regions if region.action == "field:status"),
            key=lambda region: region.x,
        )
        option_region = max(
            (region for region in frame.regions if region.action == "option:0"),
            key=lambda region: region.x,
        )
        self.assertEqual(option_region.x, field_region.x)

        plain = screen._ANSI_RE.sub("", frame.lines[option_region.y - 1])
        marker_column = option_region.x - 3
        self.assertGreaterEqual(marker_column, 0)
        self.assertEqual(plain[marker_column], ">")


if __name__ == "__main__":
    unittest.main()
