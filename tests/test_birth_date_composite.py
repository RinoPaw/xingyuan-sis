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
from xingyuan_sis.tui.view_common import Board
from xingyuan_sis.tui.workspace import editor, field_session, forms, student_inspector
from xingyuan_sis.tui.workspace.birth_date_editor import display, options, parts
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.state import FieldSessionOwner, Workspace


class BirthDateCompositeTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def test_display_hides_storage_syntax(self):
        self.assertEqual(display("2006"), "2006")
        self.assertEqual(display("--09-07"), "9-7")
        self.assertEqual(display("2006-09-07"), "2006-9-7")
        self.assertEqual(display(None), "-")

    def test_parts_and_day_options_follow_year_and_month(self):
        self.assertEqual(
            parts("--09-07"),
            {"birth_year": None, "birth_month": 9, "birth_day": 7},
        )
        leap_days = options("birth_day", {"birth_year": 2004, "birth_month": 2})
        common_days = options("birth_day", {"birth_year": 2005, "birth_month": 2})
        unknown_year_days = options("birth_day", {"birth_year": None, "birth_month": 2})
        self.assertEqual(leap_days[-1][0], 29)
        self.assertEqual(common_days[-1][0], 28)
        self.assertEqual(unknown_year_days[-1][0], 29)

    def test_record_session_expands_and_persists_canonical_value(self):
        row = self.catalog.rows("students")[0]
        student_no = row["student_no"]
        self.catalog.service.update_student_by_no(student_no, birth_date="2006")
        self.catalog.refresh()

        state = Workspace("students")
        field_session.start(state, self.catalog, "birth_date")
        session = state.field_session
        self.assertEqual(
            [field.key for field in session.fields],
            ["birth_year", "birth_month", "birth_day"],
        )
        self.assertEqual(
            session.values,
            {"birth_year": 2006, "birth_month": None, "birth_day": None},
        )

        session.values.update(birth_year=None, birth_month=9, birth_day=7)
        session.active = 2
        field_session.commit(state, self.catalog)

        saved = self.catalog.service.student_by_no(student_no)
        self.assertEqual(saved["birth_date"], "--09-07")
        line = next(
            line for line in student_inspector.lines(self.catalog.rows("students")[0], self.catalog)
            if line and line[0][0].startswith("出生日期")
        )
        self.assertIn("9-7", "".join(text for text, _, _ in line))
        self.assertEqual([action for _, _, action in line if action], ["field:birth_date"])

    def test_editing_line_uses_three_independent_fixed_slots(self):
        state = Workspace("students")
        field_session.start(state, self.catalog, "birth_date")
        line = next(
            line for line in student_inspector.lines(state.current(self.catalog), self.catalog, state)
            if line and line[0][0].startswith("出生日期")
        )
        segments = {action: text for text, _, action in line if action}
        self.assertEqual(
            list(segments),
            ["field:birth_year", "field:birth_month", "field:birth_day"],
        )
        self.assertEqual(screen._display_width(segments["field:birth_year"]), 4)
        self.assertEqual(screen._display_width(segments["field:birth_month"]), 2)
        self.assertEqual(screen._display_width(segments["field:birth_day"]), 2)

    def test_arrow_keys_move_inside_slot_before_crossing_to_next_slot(self):
        state = Workspace("students")
        field_session.start(state, self.catalog, "birth_date")
        session = state.field_session
        session.values.update(birth_year=2005, birth_month=12, birth_day=22)
        session.active = 1
        buffers = field_session._birth_buffers(session)

        self.assertEqual(buffers["birth_month"].cursor, 0)
        field_session._move_birth_caret(session, buffers, "right")
        self.assertEqual(session.active_key, "birth_month")
        self.assertEqual(buffers["birth_month"].cursor, 1)

        field_session._move_birth_caret(session, buffers, "right")
        self.assertEqual(session.active_key, "birth_month")
        self.assertEqual(buffers["birth_month"].cursor, 2)

        field_session._move_birth_caret(session, buffers, "right")
        self.assertEqual(session.active_key, "birth_day")
        self.assertEqual(buffers["birth_day"].cursor, 0)

    def test_backspace_changes_only_the_active_date_slot(self):
        state = Workspace("students")
        field_session.start(state, self.catalog, "birth_date")
        session = state.field_session
        session.values.update(birth_year=2005, birth_month=12, birth_day=22)
        session.active = 1
        buffers = field_session._birth_buffers(session)
        buffers["birth_month"].cursor = 2

        changed = field_session._edit_birth_buffer(
            buffers["birth_month"],
            TextEvent("backspace"),
            2,
        )

        self.assertTrue(changed)
        self.assertEqual(buffers["birth_month"].value, "1")
        self.assertEqual(buffers["birth_day"].value, "22")

    def test_masked_editor_uses_tab_to_cross_slots_and_commits_once(self):
        row = self.catalog.rows("students")[0]
        student_no = row["student_no"]
        self.catalog.service.update_student_by_no(student_no, birth_date="2006-09-07")
        self.catalog.refresh()
        state = Workspace("students")
        field_session.start(state, self.catalog, "birth_date")

        events = [
            TextEvent("tab"),
            TextEvent("insert", "1"),
            TextEvent("insert", "2"),
            TextEvent("tab"),
            TextEvent("insert", "3"),
            TextEvent("insert", "1"),
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
        saved = self.catalog.service.student_by_no(student_no)
        self.assertEqual(saved["birth_date"], "2006-12-31")

    def test_create_form_keeps_one_business_field_and_three_edit_slots(self):
        state = Workspace("students")
        forms.open_form(state, self.catalog, "create")
        form = state.form
        form.position = next(i for i, field in enumerate(form.fields) if field.key == "birth_date")
        form.values["birth_date"] = "--09-07"

        field_session.start_form(state, self.catalog)
        self.assertIs(state.field_session.owner, FieldSessionOwner.FORM)
        self.assertEqual(
            state.field_session.values,
            {"birth_year": None, "birth_month": 9, "birth_day": 7},
        )

        board = Board(100, 35)
        editor.render_editor(board, state, self.catalog, 30, 68)
        actions = {region.action for region in board.regions}
        self.assertTrue({"field:birth_year", "field:birth_month", "field:birth_day"} <= actions)

        state.field_session.values.update(birth_year=2006, birth_month=None, birth_day=None)
        field_session.commit(state, self.catalog)
        self.assertEqual(form.values["birth_date"], "2006")
        self.assertNotIn("birth_year", form.values)
        self.assertNotIn("birth_month", form.values)
        self.assertNotIn("birth_day", form.values)


if __name__ == "__main__":
    unittest.main()
