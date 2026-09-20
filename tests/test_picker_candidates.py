from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.schema import Field
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen, workspace
from xingyuan_sis.tui.workspace import field_session, student_inspector, view
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.picker import prepare_candidates
from xingyuan_sis.tui.workspace.state import FieldSession


class PickerCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def test_direct_picker_excludes_current_value_and_uses_secondary_candidates(self):
        state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        current = state.current(self.catalog)["primary_affinity"]
        field_session.start(state, self.catalog, "primary_affinity")
        field_session.edit_current(state, self.catalog)

        lines = student_inspector.lines(state.current(self.catalog), self.catalog, state)
        self.assertNotIn(current, [value for value, _ in state.field_session.options])
        self.assertEqual(state.field_session.option_index, 0)

        candidates = [
            (text, style, action)
            for line in lines
            for text, style, action in line
            if action.startswith("option:")
        ]
        self.assertTrue(candidates)
        self.assertTrue(all(style == screen._TEXT_SECONDARY for _, style, _ in candidates))

    def test_dependent_picker_also_excludes_the_value_already_shown_in_field(self):
        session = FieldSession(
            fields=(Field("parent", "父项"), Field("child", "子项")),
            values={"parent": "P2", "child": "B"},
            original={"parent": "P1", "child": "B"},
            anchor_key="parent",
            active=1,
            options=[("A", "A"), ("B", "B"), ("C", "C")],
            option_index=1,
        )

        prepare_candidates(session)

        self.assertEqual(session.options, [("A", "A"), ("C", "C")])
        self.assertEqual(session.option_index, 0)

    def test_picker_marker_uses_left_gutter_without_moving_candidate_text(self):
        state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        field_session.start(state, self.catalog, "primary_affinity")
        field_session.edit_current(state, self.catalog)

        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((100, 35))):
            frame = view.render(state, self.catalog)

        option_actions = [
            f"option:{index}" for index in range(len(state.field_session.options))
        ]
        text_xs = []
        for action in option_actions:
            regions = [region for region in frame.regions if region.action == action]
            self.assertTrue(regions)
            text_xs.append(max(region.x for region in regions))

        self.assertEqual(len(set(text_xs)), 1)
        selected_regions = [
            region for region in frame.regions
            if region.action == f"option:{state.field_session.option_index}"
        ]
        self.assertEqual(max(region.x for region in selected_regions) - min(region.x for region in selected_regions), 2)


if __name__ == "__main__":
    unittest.main()
