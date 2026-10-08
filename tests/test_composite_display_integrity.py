"""Integration guards for stable unset-field rendering and confirmed choices."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen
from xingyuan_sis.tui.workspace import field_session, forms, view
from xingyuan_sis.tui.workspace.composite_constraints import reconcile
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.state import FocusArea, Workspace
from xingyuan_sis.tui.workspace.student_layout import STUDENT_FIELD_ROWS


class UnsetCompositeRenderTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = Path(temp.name) / "test.db"
        initialize_database(db)
        seed_demo(db)
        self.catalog = Catalog(db)

    def render(self, state, size):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return view.render(state, self.catalog)

    @staticmethod
    def text(frame):
        return "\n".join(screen._ANSI_RE.sub("", line) for line in frame.lines)

    def test_unset_components_keep_real_archive_targets(self):
        for anchor, children in (
            ("family", ("branch",)),
            ("major_code", ("class_number",)),
            ("primary_element", ("primary_affinity",)),
            ("dorm_area", ("dorm_building", "dorm_room")),
        ):
            for size in ((120, 35), (64, 20)):
                with self.subTest(anchor=anchor, size=size):
                    state = Workspace("students")
                    state.set_focus(FocusArea.INSPECTOR)
                    field_session.start(state, self.catalog, anchor)
                    for key in (anchor, *children):
                        state.field_session.values[key] = None
                    frame = self.render(state, size)
                    shown = self.text(frame)
                    self.assertIn("未指定", shown)
                    actions = {region.action for region in frame.regions}
                    self.assertIn("field:" + anchor, actions)
                    for key in children:
                        self.assertIn("field:" + key, actions)
                    self.assertIsNotNone(state.field_session)

    def test_unset_components_keep_form_controls_in_both_layouts(self):
        state = Workspace("students")
        forms.open_form(state, self.catalog, "create")
        keys = tuple(
            dict.fromkeys(key for row in STUDENT_FIELD_ROWS
                          if len(row.keys) > 1 for key in row.keys)
        )
        for key in keys:
            state.form.values[key] = None
        for size in ((120, 35), (64, 20)):
            for key in keys:
                with self.subTest(key=key, size=size):
                    state.form.position = next(
                        i for i, field in enumerate(state.form.fields) if field.key == key
                    )
                    frame = self.render(state, size)
                    self.assertIn("未指定", self.text(frame))
                    self.assertIn(
                        "field:" + key,
                        {region.action for region in frame.regions},
                    )

    def test_opening_picker_never_normalizes_unconfirmed_values(self):
        state = Workspace("students")
        field_session.start(state, self.catalog, "branch")
        state.field_session.values["branch"] = "暂不属于当前选择范围"
        before = dict(state.field_session.values)
        self.assertTrue(field_session._open_options(state, self.catalog))
        self.assertEqual(state.field_session.values, before)
        field_session.cancel(state)
        self.assertIsNone(state.field_session)

        field_session.start(state, self.catalog, "birth_date")
        state.field_session.values.update(birth_year=2005, birth_month=2, birth_day=31)
        state.field_session.active = 2
        before = dict(state.field_session.values)
        self.assertTrue(field_session._open_options(state, self.catalog))
        self.assertEqual(state.field_session.values, before)

    def test_choice_domain_is_independent_of_labels_and_order(self):
        before = {"family": "甲", "branch": "子"}
        after = {"family": "乙", "branch": "子"}

        def domain(key, values):
            if values["family"] == "甲":
                return [("子", "旧标签"), ("另", "其他")]
            return [("另", "改名"), ("子", "新标签")]

        self.assertEqual(reconcile("students", before, after, domain), set())
        self.assertEqual(after["branch"], "子")


if __name__ == "__main__":
    unittest.main()
