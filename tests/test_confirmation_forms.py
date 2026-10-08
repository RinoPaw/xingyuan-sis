"""Shared confirmation contracts for delete, password reset and demo creation."""
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
from xingyuan_sis.tui.workspace.state import FocusArea, Workspace


class ConfirmationFormTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "demo.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def interact(self, state, *sequence, size=(80, 24)):
        with (
            patch.object(keys, "_read_key", side_effect=sequence),
            patch.object(screen, "_paint"),
            patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)),
        ):
            return events.interact(state, self.catalog)

    def test_repeated_enter_does_not_confirm_any_action(self):
        for mode in ("delete", "reset-password", "seed"):
            with self.subTest(mode=mode):
                state = Workspace("students", selected=2)
                original = state.current(self.catalog).copy()
                self.assertEqual(self.interact(state, mode, "select", "refresh"), ("refresh", 0))
                self.assertIsNone(state.form)
                self.assertEqual(state.current(self.catalog)["id"], original["id"])
                self.assertIsNotNone(self.catalog.service.student_by_no(original["student_no"]))

    def test_action_layout_and_click_regions_across_terminal_widths(self):
        for mode in ("delete", "reset-password", "seed"):
            for size in ((120, 35), (64, 20), (30, 12)):
                with self.subTest(mode=mode, size=size):
                    state = Workspace("students", selected=1)
                    forms.open_form(state, self.catalog, mode)
                    with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
                        frame = view.render(state, self.catalog)
                    plain = [screen._ANSI_RE.sub("", line) for line in frame.lines]
                    confirm = next(r for r in frame.regions if r.action == "confirm-action")
                    cancel = next(r for r in frame.regions if r.action == "cancel-action")
                    self.assertEqual(state.form.position, 1)
                    self.assertLess(max(confirm.y, cancel.y), size[1] - 1)
                    self.assertGreater(confirm.width, 0)
                    self.assertGreater(cancel.width, 0)
                    self.assertIn("Enter 选择", plain[-1])
                    if mode == "reset-password":
                        joined = "\n".join(plain)
                        self.assertIn("姓名", joined)
                        self.assertIn("学号", joined)
                        self.assertIn("下次登录须改密", joined)
                        self.assertNotIn("密码？", joined)
                    if mode == "seed":
                        self.assertIn("不会覆盖已有记录", "\n".join(plain))

    def test_cancel_restores_original_focus_context(self):
        for mode in ("delete", "reset-password", "seed"):
            with self.subTest(mode=mode):
                state = Workspace("students", selected=3, detail_selected=6, detail_scroll=2)
                prior = state.capture_focus_context()
                forms.open_form(state, self.catalog, mode)
                self.assertEqual(state.focus, FocusArea.INSPECTOR)
                self.assertEqual(self.interact(state, "select", "refresh"), ("refresh", 0))
                self.assertIsNone(state.form)
                self.assertEqual(state.capture_focus_context(), prior)

    def test_keyboard_and_mouse_share_confirmation_actions(self):
        for mode in ("delete", "reset-password", "seed"):
            with self.subTest(mode=mode):
                state = Workspace("students", selected=2)
                forms.open_form(state, self.catalog, mode)
                self.assertEqual(self.interact(state, "left", "select"), ("save", 0))
                forms.cancel_form(state)
                for action, expects_save in (("confirm-action", True), ("cancel-action", False)):
                    state = Workspace("students", selected=2)
                    forms.open_form(state, self.catalog, mode)
                    with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 24))):
                        frame = view.render(state, self.catalog)
                    region = next(r for r in frame.regions if r.action == action)
                    sequence = (keys.MouseClick(region.x, region.y),)
                    if not expects_save:
                        sequence += ("refresh",)
                    self.assertEqual(
                        self.interact(state, *sequence),
                        ("save", 0) if expects_save else ("refresh", 0),
                    )
                    forms.cancel_form(state)

    def test_reset_confirmation_calls_same_service(self):
        state = Workspace("students", selected=2)
        number = state.current(self.catalog)["student_no"]
        forms.open_form(state, self.catalog, "reset-password")
        self.assertEqual(self.interact(state, "left", "select"), ("save", 0))
        with patch.object(self.catalog.service, "reset_student_password") as reset:
            forms.apply_form(state, self.catalog)
        reset.assert_called_once_with(str(number))
        self.assertIsNone(state.form)

    def test_demo_confirmation_calls_same_service(self):
        state = Workspace("students")
        forms.open_form(state, self.catalog, "seed")
        self.assertEqual(self.interact(state, "left", "select"), ("save", 0))
        with patch.object(self.catalog.service, "seed_demo") as seed:
            forms.apply_form(state, self.catalog)
        seed.assert_called_once_with()
        self.assertIsNone(state.form)


if __name__ == "__main__":
    unittest.main()
