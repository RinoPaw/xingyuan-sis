"""Dependent composite-field choices and birth-date limits."""
from contextlib import nullcontext
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen
from xingyuan_sis.tui.text_edit import TextEvent
from xingyuan_sis.tui.workspace import field_session, forms
from xingyuan_sis.tui.workspace.birth_date_editor import options
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.state import Workspace


class CompositeConstraintTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = Path(temp.name) / "test.db"
        initialize_database(db)
        seed_demo(db)
        self.catalog = Catalog(db)

    def test_parent_changes_clear_declared_dependents_only(self) -> None:
        changes = (
            ("family", {"family": "犬科", "branch": "拉布拉多犬"}, {"branch": None}),
            ("major_code", {"major_code": "OLD", "class_number": "01"}, {"class_number": None}),
            ("dorm_area", {"dorm_area": "A区", "dorm_building": "2", "dorm_room": "201"},
             {"dorm_building": None, "dorm_room": None}),
            ("dorm_building", {"dorm_area": "A区", "dorm_building": "2", "dorm_room": "201"},
             {"dorm_area": "A区", "dorm_room": None}),
            ("primary_element", {"primary_element": "风", "primary_affinity": "A"},
             {"primary_affinity": "A"}),
        )
        for parent, initial, expected in changes:
            with self.subTest(parent=parent):
                state = Workspace("students")
                field_session.start(state, self.catalog, parent)
                session = state.field_session
                session.values.update(initial)
                field_session._set_value(state, self.catalog, parent, "NEW")
                for name, value in expected.items():
                    self.assertEqual(session.values[name], value)
                self.assertEqual(session.active_key, parent)

    def test_unchanged_parent_does_not_erase_child(self) -> None:
        state = Workspace("students")
        field_session.start(state, self.catalog, "dorm_area")
        state.field_session.values.update(
            dorm_area="A区", dorm_building="2", dorm_room="201"
        )
        field_session._set_value(state, self.catalog, "dorm_area", "A区")
        self.assertEqual(state.field_session.values["dorm_building"], "2")
        self.assertEqual(state.field_session.values["dorm_room"], "201")

    def test_form_uses_same_dependency_rules_as_existing_record(self) -> None:
        state = Workspace("students")
        forms.open_form(state, self.catalog, "create")
        state.form.values.update(
            dorm_area="A区", dorm_building="2", dorm_room="201"
        )
        first = next(i for i, field in enumerate(state.form.fields) if field.key == "dorm_area")
        field_session.start_form(state, self.catalog, first)
        field_session._set_value(state, self.catalog, "dorm_building", "3")
        self.assertEqual(state.field_session.values["dorm_area"], "A区")
        self.assertIsNone(state.field_session.values["dorm_room"])
        field_session._set_value(state, self.catalog, "dorm_area", "B区")
        self.assertIsNone(state.field_session.values["dorm_building"])
        self.assertIsNone(state.field_session.values["dorm_room"])

    def test_year_and_month_determine_day_domain(self) -> None:
        scenarios = (
            (None, None, 31),
            (2005, None, 31),
            (None, 2, 29),
            (2004, 2, 29),
            (2005, 2, 28),
            (None, 4, 30),
            (None, 9, 30),
            (None, 8, 31),
        )
        for year, month, maximum in scenarios:
            with self.subTest(year=year, month=month):
                domain = options("birth_day", {"birth_year": year, "birth_month": month})
                self.assertEqual(domain[-1][0], maximum)
                self.assertEqual(domain[0], (None, "未指定"))
                self.assertEqual(
                    [value for value, _ in domain[1:]], list(range(1, maximum + 1))
                )

    def test_day_is_clamped_immediately_after_month_or_year_change(self) -> None:
        scenarios = (
            ({"birth_year": None, "birth_month": None, "birth_day": 31},
             "birth_month", 9, 30),
            ({"birth_year": 2005, "birth_month": 8, "birth_day": 31},
             "birth_month", 9, 30),
            ({"birth_year": None, "birth_month": 2, "birth_day": 29},
             "birth_year", 2005, 28),
            ({"birth_year": None, "birth_month": 2, "birth_day": 29},
             "birth_year", 2004, 29),
            ({"birth_year": 2005, "birth_month": 2, "birth_day": 28},
             "birth_month", None, 28),
            ({"birth_year": 2005, "birth_month": 2, "birth_day": 29},
             "birth_day", 31, 28),
        )
        for original, edited, new_value, expected in scenarios:
            with self.subTest(original=original, edited=edited, new_value=new_value):
                state = Workspace("students")
                field_session.start(state, self.catalog, "birth_date")
                state.field_session.values.update(original)
                field_session._set_value(state, self.catalog, edited, new_value)
                self.assertEqual(state.field_session.values["birth_day"], expected)

    def test_masked_editor_clamps_day_during_month_typing(self) -> None:
        student_no = self.catalog.rows("students")[0]["student_no"]
        self.catalog.service.update_student_by_no(student_no, birth_date="2005-08-31")
        self.catalog.refresh()
        state = Workspace("students")
        field_session.start(state, self.catalog, "birth_date")
        events = [
            TextEvent("tab"), TextEvent("clear"),
            TextEvent("insert", "0"), TextEvent("insert", "9"),
            TextEvent("submit"),
        ]
        with patch.object(field_session, "input_mode", return_value=nullcontext()), \
             patch.object(field_session, "editing_cursor", return_value=nullcontext()), \
             patch.object(field_session, "read_event", side_effect=events), \
             patch.object(field_session, "_position_birth_cursor"), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            field_session.edit_current(state, self.catalog)
        self.assertIsNone(state.field_session)
        self.assertEqual(
            self.catalog.service.student_by_no(student_no)["birth_date"], "2005-09-30"
        )


if __name__ == "__main__":
    unittest.main()
