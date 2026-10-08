"""Optional student branch and inline, keyboard-reachable form saving."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.database import connect, initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.student_filters import query_students
from xingyuan_sis.tui import keys, screen
from xingyuan_sis.tui.workspace import events, forms, view
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.state import Workspace


class OptionalBranchAndSaveTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def interact(self, state, sequence, size=(64, 23)):
        with patch.object(keys, "_read_key", side_effect=sequence), \
             patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return events.interact(state, self.catalog)

    def render(self, state, size):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return view.render(state, self.catalog)

    def test_create_and_edit_optional_branch_persist_real_null(self):
        sample = self.catalog.service.list_students()[0]
        state = Workspace("students")
        forms.open_form(state, self.catalog, "create")
        fields = {field.key: field for field in state.form.fields}
        self.assertTrue(fields["family"].required)
        self.assertFalse(fields["branch"].required)
        self.assertEqual(self.catalog.options("students", "branch", {"family": sample["family"]})[0], (None, "未指定"))
        state.form.values.update(
            student_no="29990101", name="未指定支系", family=sample["family"],
            branch=None, enrollment_year=2026,
        )
        record_id = forms.apply_form(state, self.catalog)
        student = self.catalog.service.student_by_no("29990101")
        self.assertEqual(record_id, student["id"])
        self.assertIsNone(student["branch"])
        self.assertIsNone(student["species_branch_id"])
        self.assertEqual(student["family"], sample["family"])
        self.assertTrue(any(row.student_no == "29990101" and row.branch is None
                            for row in query_students(self.catalog.service)))
        self.catalog.service.update_student_by_no("29990101", branch=sample["branch"])
        self.assertEqual(self.catalog.service.student_by_no("29990101")["branch"], sample["branch"])
        self.catalog.service.update_student_by_no("29990101", branch=None)
        self.assertIsNone(self.catalog.service.student_by_no("29990101")["branch"])
        with connect(self.db) as connection:
            self.assertFalse(connection.execute("PRAGMA foreign_key_check").fetchall())
            self.assertFalse(connection.execute(
                "SELECT 1 FROM species_branches WHERE name = '未指定'"
            ).fetchall())

    def test_family_change_can_leave_branch_unassigned(self):
        row = self.catalog.service.list_students()[0]
        other = next(f["name"] for f in self.catalog.service.list_species_families() if f["name"] != row["family"])
        self.catalog.service.update_student_by_no(row["student_no"], family=other, branch=None)
        changed = self.catalog.service.student_by_no(row["student_no"])
        self.assertEqual(changed["family"], other)
        self.assertIsNone(changed["branch"])

    def test_schema_has_independent_family_and_nullable_branch(self):
        with connect(self.db) as connection:
            columns = {r["name"]: r for r in connection.execute("PRAGMA table_info(students)")}
        self.assertEqual(columns["species_family_id"]["notnull"], 1)
        self.assertEqual(columns["species_branch_id"]["notnull"], 0)

    def test_inline_save_is_keyboard_reachable_with_down_tab_and_enter(self):
        for size in ((120, 35), (64, 23), (30, 12)):
            with self.subTest(size=size):
                state = Workspace("students")
                forms.open_form(state, self.catalog, "create")
                count = len(state.form.fields)
                state.form.position = count - 1
                self.assertEqual(self.interact(state, ["down", "save"], size), ("save", 0))
                self.assertEqual(state.form.position, count)
                frame = self.render(state, size)
                save = next(r for r in frame.regions if r.action == "save")
                # Hit regions are 1-based: the footer is row size[1].
                self.assertLess(save.y, size[1])
                if size == (120, 35):
                    self.assertLess(save.y, size[1] - 1)
                self.assertIn("Enter 保存", screen._ANSI_RE.sub("", frame.lines[-1]))
                self.assertEqual(self.interact(state, ["up", "save"], size), ("save", 0))
                self.assertEqual(state.form.position, count - 1)
                self.assertEqual(self.interact(state, ["focus", "save"], size), ("save", 0))
                self.assertEqual(state.form.position, count)
                self.assertEqual(self.interact(state, ["select"], size), ("save", 0))

    def test_save_mouse_hit_matches_keyboard_action(self):
        state = Workspace("students")
        forms.open_form(state, self.catalog, "create")
        state.form.position = len(state.form.fields)
        frame = self.render(state, (64, 23))
        button = next(r for r in frame.regions if r.action == "save")
        self.assertEqual(self.interact(state, [keys.MouseClick(button.x, button.y)], (64, 23)), ("save", 0))

    def test_form_remains_editable_after_failed_save(self):
        state = Workspace("students")
        forms.open_form(state, self.catalog, "create")
        state.form.position = len(state.form.fields)
        with self.assertRaisesRegex(ValueError, "请填写"):
            forms.apply_form(state, self.catalog)
        self.assertIsNotNone(state.form)
        self.assertEqual(state.form.position, len(state.form.fields))


if __name__ == "__main__":
    unittest.main()
