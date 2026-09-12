from contextlib import nullcontext
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.auth import Identity
from xingyuan_sis.tui import app, auth_view, keys, screen


class TuiAuthViewTests(unittest.TestCase):
    def test_login_and_initialization_are_full_screen_pages(self):
        for size in ((80, 24), (40, 16), (30, 12)):
            with self.subTest(size=size), patch.object(
                screen, "_terminal_size", return_value=os.terminal_size(size)
            ):
                login = auth_view.frame("login", {"username": "", "password": ""})
                setup = auth_view.frame(
                    "initialize",
                    {"username": "Administrator", "password": "", "confirm": ""},
                )
            self.assertEqual(len(login.lines), size[1])
            self.assertEqual(len(setup.lines), size[1])
            self.assertTrue(all(screen._display_width(line) == size[0] - 1 for line in login.lines))
            self.assertTrue(all(screen._display_width(line) == size[0] - 1 for line in setup.lines))
            login_text = "\n".join(login.lines)
            setup_text = "\n".join(setup.lines)
            self.assertIn("登录", login_text)
            self.assertIn("账号", login_text)
            self.assertIn("密码", login_text)
            self.assertIn("设置管理员密码", setup_text)
            self.assertIn("账号", setup_text)
            self.assertIn("Administrator", setup_text)
            self.assertNotIn("管理员账号", setup_text)
            self.assertNotIn("创建唯一管理员", setup_text)
            self.assertEqual(
                [field[1] for field in auth_view._fields("initialize")],
                ["账号", "密码", "确认"],
            )

    def test_portal_uses_tui_login_when_session_is_missing(self):
        identity = Identity("Administrator", "admin")
        preferences = {"animate": False}
        with patch.object(app, "read_session", return_value=None), \
             patch.object(app.auth_view, "login", return_value=identity) as login, \
             patch("xingyuan_sis.service.XingyuanService") as service, \
             patch.object(keys, "_mouse_tracking", return_value=nullcontext()), \
             patch.object(keys, "_read_key", return_value="back"), \
             patch.object(screen, "_paint"), patch.object(screen, "_clear"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 24))):
            service.return_value.stats.return_value = {}
            result = app._portal_home("test.db", selected=0, preferences=preferences)
        self.assertIsNone(result)
        login.assert_called_once_with("test.db")
        self.assertEqual(preferences["identity"], identity)


if __name__ == "__main__":
    unittest.main()
