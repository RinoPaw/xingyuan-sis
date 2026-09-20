from contextlib import redirect_stderr
from io import StringIO
import unittest
from unittest.mock import patch

from xingyuan_sis import entry


class GuiEntryTests(unittest.TestCase):
    def test_missing_tkinter_shows_install_hint_without_traceback(self):
        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 1 and name == "gui.app":
                raise ModuleNotFoundError("No module named 'tkinter'", name="tkinter")
            return original_import(name, globals, locals, fromlist, level)

        output = StringIO()
        with (
            patch.object(entry, "initialize_database"),
            patch("builtins.__import__", side_effect=fake_import),
            redirect_stderr(output),
        ):
            code = entry._run_gui(None)

        text = output.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("当前 Python 未安装 Tkinter/Tcl-Tk", text)
        self.assertIn("python -m tkinter", text)
        self.assertNotIn("Traceback", text)

    def test_unrelated_import_error_is_not_hidden(self):
        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 1 and name == "gui.app":
                raise ModuleNotFoundError("No module named 'other_package'", name="other_package")
            return original_import(name, globals, locals, fromlist, level)

        with patch.object(entry, "initialize_database"), patch(
            "builtins.__import__", side_effect=fake_import
        ):
            with self.assertRaises(ModuleNotFoundError):
                entry._run_gui(None)


if __name__ == "__main__":
    unittest.main()
