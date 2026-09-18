"""Keyboard-only journeys across the shared record workspace."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.auth import Identity
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen
from xingyuan_sis.tui.workspace import events, field_session, forms, view
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.state import Workspace


class WorkspaceFlowTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def interact(self, state, sequence, size=(100, 28), catalog=None):
        with patch.object(keys, "_read_key", side_effect=sequence), patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return events.interact(state, catalog or self.catalog)

    def render(self, state, size=(100, 28), catalog=None):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return view.render(state, catalog or self.catalog)

    def test_delete_selected_student_through_toolbar_without_mouse(self):
        state = Workspace("students", selected=17)
        original = state.current(self.catalog).copy()
        self.assertEqual(
            self.interact(state, ["focus_prev", "right", "right", "select", "select"], (120, 35)),
            ("save", 0),
        )
        self.assertEqual(state.form.mode, "delete")
        self.assertEqual(state.form.original["id"], original["id"])
        forms.apply_form(state, self.catalog)
        self.assertIsNone(self.catalog.service.student_by_no(original["student_no"]))

    def test_focus_cycle_preserves_record_and_roster_scroll(self):
        state = Workspace("students", selected=40, roster_scroll=30)
        self.render(state)
        original = (state.selected, state.roster_scroll)
        for sequence, expected in (
            (["focus", "refresh"], (True, False)),
            (["focus", "refresh"], (False, True)),
            (["focus", "refresh"], (False, False)),
            (["focus_prev", "refresh"], (False, True)),
        ):
            self.interact(state, sequence)
            self.assertEqual((state.details, state.action_focus), expected)
            self.assertEqual((state.selected, state.roster_scroll), original)

    def test_cancel_delete_preserves_student_and_returns_to_current_record(self):
        state = Workspace("students", selected=21)
        original = state.current(self.catalog).copy()
        self.interact(state, ["delete", "back", "refresh"])
        self.assertIsNone(state.form)
        self.assertEqual(state.current(self.catalog), original)

    def test_other_entities_keep_identical_field_target_during_session(self):
        for key in ("departments", "majors", "classes", "courses", "grades"):
            editable_key = self.catalog.fields(key, True)[0].key
            for size in ((140, 45), (80, 24), (30, 12)):
                with self.subTest(key=key, size=size):
                    state = Workspace(key, details=True)
                    before = self.render(state, size)
                    old = next(r for r in before.regions if r.action == f"field:{editable_key}")
                    field_session.start(state, self.catalog, editable_key)
                    after = self.render(state, size)
                    active = next(r for r in after.regions if r.action == f"field:{editable_key}")
                    self.assertEqual((active.x, active.y), (old.x, old.y))
                    self.assertIsNone(state.form)
                    self.assertFalse(any(r.action == "save" for r in after.regions))

    def test_every_editable_field_is_reachable_after_resize_without_record_save_button(self):
        for key in ("students", "departments", "majors", "classes", "courses", "grades"):
            for field in self.catalog.fields(key, True):
                for size in ((120, 35), (40, 20), (24, 10)):
                    with self.subTest(key=key, field=field.key, size=size):
                        state = Workspace(key, details=True)
                        try:
                            field_session.start(state, self.catalog, field.key)
                        except ValueError as exc:
                            if key == "students" and field.key == "age" and "自动计算年龄" in str(exc):
                                continue
                            raise
                        frame = self.render(state, size)
                        self.assertTrue(any(r.action == f"field:{state.field_session.active_key}" for r in frame.regions))
                        self.assertFalse(any(r.action == "save" for r in frame.regions))

    def test_create_form_keeps_explicit_save_target(self):
        state = Workspace("courses")
        forms.open_form(state, self.catalog, "create")
        event = self.interact(state, ["focus"] * len(state.form.fields) + ["select"])
        self.assertEqual(event, ("save", 0))
        self.assertTrue(state.form.focus_save)

    def test_short_create_and_confirmation_keep_controls_above_status(self):
        for size in ((24, 8), (30, 10), (40, 20)):
            state = Workspace("students", selected=17)
            forms.open_form(state, self.catalog, "create")
            for index in (0, len(state.form.fields) - 1):
                state.form.position = index
                frame = self.render(state, size)
                field = next(r for r in frame.regions if r.action == f"field:{index}")
                save = next(r for r in frame.regions if r.action == "save")
                self.assertLess(field.y, save.y)
                self.assertLess(save.y, size[1] - 1)
            forms.open_form(state, self.catalog, "delete")
            save = next(r for r in self.render(state, size).regions if r.action == "save")
            self.assertLess(save.y, size[1] - 1)

    def test_read_only_queries_and_related_pages_never_expose_write_actions(self):
        row = self.catalog.records["students"][0]
        student = Identity(row["student_no"], "student", row["student_no"])
        catalog = Catalog(self.db, student)
        state = Workspace("students", query=f"--no {row['student_no']}")
        frame = self.render(state, catalog=catalog)
        forbidden = {"create", "edit", "delete", "import", "export", "seed", "reset-password"}
        self.assertFalse(forbidden & {r.action for r in frame.regions})
        self.assertTrue(any(r.action == "field:name" for r in frame.regions))
        related = catalog.related("students", row)[1][0]
        self.interact(state, [f"related:grades:{related['id']}", "e", "refresh"], catalog=catalog)
        self.assertEqual(state.key, "grades")
        self.assertIsNone(state.form)
        self.assertIsNone(state.field_session)
        self.assertFalse(forbidden & {r.action for r in self.render(state, catalog=catalog).regions})

    def test_read_only_student_can_scroll_past_links_to_personal_information(self):
        row = self.catalog.records["students"][0]
        catalog = Catalog(self.db, Identity(row["student_no"], "student", row["student_no"]))
        state = Workspace("students", details=True)
        self.interact(state, ["end", "refresh"], size=(30, 12), catalog=catalog)
        text = "".join(self.render(state, (30, 12), catalog).lines)
        self.assertIn("备注", text)
        self.assertIn("出生日期", text)

    def test_family_change_waits_for_branch_then_commits_atomically(self):
        state = Workspace("students", details=True)
        original = state.current(self.catalog).copy()
        field_session.start(state, self.catalog, "family")
        field_session.edit_current(state, self.catalog)
        family_index = next(
            i for i, (value, _) in enumerate(state.field_session.options)
            if value != original["family"]
            and any(row["family_name"] == value for row in self.catalog.species_branches)
        )
        chosen_family = state.field_session.options[family_index][0]
        field_session.accept_option(state, self.catalog, family_index)
        self.assertEqual(state.field_session.active_key, "branch")
        self.assertIsNotNone(state.field_session.options)
        self.assertEqual(
            self.catalog.service.student_by_no(original["student_no"])["family"],
            original["family"],
        )
        chosen_branch = state.field_session.options[0][0]
        field_session.accept_option(state, self.catalog, 0)
        changed = self.catalog.service.student_by_no(original["student_no"])
        self.assertEqual((changed["family"], changed["branch"]), (chosen_family, chosen_branch))

    def test_empty_transaction_picker_can_be_cancelled_without_losing_form(self):
        state = Workspace("grades")
        forms.open_form(state, self.catalog, "create")
        state.form.options = []
        with self.assertRaises(StopIteration):
            self.interact(state, ["select", "back"])
        self.assertIsNotNone(state.form)
        self.assertIsNone(state.form.options)

    def test_related_return_restores_focus_from_any_source(self):
        for key in ("students", "departments", "majors", "classes", "courses", "grades"):
            with self.subTest(key=key):
                state = Workspace(key, details=True)
                original = state.current(self.catalog)
                target, rows = self.catalog.related(key, original)
                self.interact(state, [f"related:{target}:{rows[0]['id']}", "back", "refresh"])
                self.assertEqual(state.key, key)
                self.assertEqual(state.current(self.catalog)["id"], original["id"])
                self.assertTrue(state.details)


if __name__ == "__main__":
    unittest.main()
