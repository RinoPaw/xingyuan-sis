from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import importlib.util
import os
import sys
import unittest

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "notepad"


class NotepadExerciseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
        except ImportError as error:
            raise unittest.SkipTest(str(error))
        try:
            root = tk.Tk()
            root.destroy()
        except tk.TclError as error:
            raise unittest.SkipTest(str(error))
        sys.path.insert(0, str(EXAMPLE))
        cls.addClassCleanup(lambda: sys.path.remove(str(EXAMPLE)))
        spec = importlib.util.spec_from_file_location("notepad_exercise", EXAMPLE / "Notepad.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def setUp(self):
        import tkinter as tk
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.app = self.module.NotepadApp(self.root)
        self.root.update()

    def test_toolbar_clipboard_commands_work(self):
        self.app.text.insert("1.0", "星原同窗")
        self.app.text.tag_add("sel", "1.0", "1.2")
        self.app.text.focus_force()
        self.app.tool_buttons[4].invoke()
        self.root.update()
        self.assertEqual(self.root.clipboard_get(), "星原")
        self.app.tool_buttons[3].invoke()
        self.root.update()
        self.assertEqual(self.app.text.get("1.0", "end-1c"), "同窗")
        self.app.text.mark_set("insert", "1.0")
        self.app.tool_buttons[5].invoke()
        self.root.update()
        self.assertEqual(self.app.text.get("1.0", "end-1c"), "星原同窗")

    def test_unsaved_new_can_be_cancelled_and_utf8_roundtrips(self):
        self.app.text.insert("1.0", "星原\n灰狼与赤狐")
        self.root.update()
        with patch.object(self.module.messagebox, "askyesnocancel", return_value=None):
            self.app.new_file()
        self.assertEqual(self.app.text.get("1.0", "end-1c"), "星原\n灰狼与赤狐")
        path = Path(self.temp.name) / "note.txt"
        with patch.object(self.module.filedialog, "asksaveasfilename", return_value=str(path)):
            self.app.tool_buttons[2].invoke()
        self.assertEqual(path.read_text(encoding="utf-8"), "星原\n灰狼与赤狐")
        self.app.new_file()
        self.assertEqual(self.app.text.get("1.0", "end-1c"), "")
        with patch.object(self.module.filedialog, "askopenfilename", return_value=str(path)):
            self.app.tool_buttons[1].invoke()
        self.assertEqual(self.app.text.get("1.0", "end-1c"), "星原\n灰狼与赤狐")

    def test_layouts_repack_toolbar_and_icons_exist(self):
        self.app.apply_layout("vertical")
        self.assertTrue(all(b.pack_info()["side"] == "top" for b in self.app.tool_buttons))
        self.app.apply_layout("compact")
        self.assertTrue(all(b.pack_info()["side"] == "left" for b in self.app.tool_buttons))
        self.assertTrue(all(str(b.cget("image")) for b in self.app.tool_buttons))
        file_menu = self.app.components["menu_bar"].nametowidget(self.app.components["menu_bar"].entrycget(0, "menu"))
        self.assertTrue(file_menu.entrycget(0, "image"))


if __name__ == "__main__":
    unittest.main()
