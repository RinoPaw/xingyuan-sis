import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import keys, screen
from xingyuan_sis.tui.workspace import events, forms, view
from xingyuan_sis.tui.workspace.data import COLLECTIONS, Catalog
from xingyuan_sis.tui.workspace.state import FieldSessionOwner, Workspace


class CreateFormConsistencyTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def render(self, state, size=(120, 35)):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return view.render(state, self.catalog)

    def interact(self, state, sequence, size=(120, 35)):
        with patch.object(keys, "_read_key", side_effect=sequence), patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return events.interact(state, self.catalog)

    def test_every_record_create_keeps_the_workspace_and_one_footer_contract(self):
        for key in COLLECTIONS:
            with self.subTest(key=key):
                state = Workspace(key)
                forms.open_form(state, self.catalog, "create")
                frame = self.render(state)
                plain = [screen._ANSI_RE.sub("", line) for line in frame.lines]
                body = "\n".join(plain[:-1])
                footer = plain[-1]

                self.assertIn("名册", body)
                self.assertIn("档案", body)
                self.assertNotIn("新建 ·", body)
                self.assertNotIn("* 必填", body)
                self.assertNotIn("更改暂存", body)
                self.assertTrue(any(region.action.startswith("field:") for region in frame.regions))
                self.assertFalse(any(region.action == "save" for region in frame.regions))
                self.assertEqual(footer.count("Enter 编辑"), 1)
                self.assertEqual(footer.count("S 保存"), 1)
                self.assertEqual(footer.count("Esc 取消"), 1)

                if self.catalog.rows(key):
                    self.assertTrue(any(region.action.startswith("row:") for region in frame.regions))
                else:
                    self.assertIn("名册还是空白的", body)

    def test_every_record_create_waits_for_enter_before_field_session(self):
        for key in COLLECTIONS:
            with self.subTest(key=key):
                state = Workspace(key)
                self.assertEqual(self.interact(state, ["create", "save"]), ("save", 0))
                self.assertIsNotNone(state.form)
                self.assertEqual(state.form.position, 0)
                self.assertIsNone(state.field_session)

                event = self.interact(state, ["select"])
                self.assertEqual(event, ("field-edit", 0))
                self.assertIsNotNone(state.field_session)
                self.assertIs(state.field_session.owner, FieldSessionOwner.FORM)
                self.assertEqual(state.field_session.anchor_key, state.form.fields[0].key)

    def test_moving_between_create_fields_does_not_enter_edit_state(self):
        for key in COLLECTIONS:
            state = Workspace(key)
            forms.open_form(state, self.catalog, "create")
            if len(state.form.fields) < 2:
                continue
            with self.subTest(key=key):
                self.assertEqual(self.interact(state, ["down", "save"]), ("save", 0))
                self.assertEqual(state.form.position, 1)
                self.assertIsNone(state.field_session)

                self.assertEqual(self.interact(state, ["select"]), ("field-edit", 0))
                self.assertEqual(state.field_session.anchor_key, state.form.fields[1].key)


if __name__ == "__main__":
    unittest.main()
