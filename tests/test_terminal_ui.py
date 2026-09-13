from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from xingyuan_sis import basic_ui, terminal_ui
from xingyuan_sis.tui import app as menu, screen, keys, animation, theme
from xingyuan_sis.database import initialize_database
from xingyuan_sis.entry import main
from xingyuan_sis.seed_data import seed_demo


LABELS = ("学生", "教务", "课程", "成绩", "数据", "退出")


class KeyboardMenuTests(unittest.TestCase):
    def test_plain_keys_and_interrupts(self) -> None:
        for char, expected in (("\r", "select"), (" ", "select"), ("j", "down"),
                               ("K", "up"), ("0", "back"), ("\x7f", "back"),
                               ("Q", "back"), ("3", "3"), ("p", "pause")):
            with self.subTest(char=char):
                self.assertEqual(keys._plain_key(char), expected)
        with self.assertRaises(KeyboardInterrupt):
            keys._plain_key("\x03")
        with self.assertRaises(EOFError):
            keys._plain_key("")

    def test_home_remembers_selection_after_return(self) -> None:
        with patch.object(menu.sys.stdin, "isatty", return_value=True), \
             patch.object(menu.sys.stdout, "isatty", return_value=True), \
             patch.object(menu, "_home", side_effect=[2, None]) as home, \
             patch.object(menu, "_courses") as courses, patch.object(screen, "_clear"), \
             redirect_stdout(StringIO()):
            # Redirecting stdout changes the object tested by run().
            with patch("sys.stdout.isatty", return_value=True):
                menu.run("example.db")
        self.assertEqual(home.call_args_list[1].kwargs["selected"], 2)
        courses.assert_called_once_with("example.db")

    def test_layout_fits_terminal_and_keeps_every_action(self) -> None:
        for size in ((80, 24), (40, 16), (30, 12), (120, 30)):
            for selected in range(6):
                with self.subTest(size=size, selected=selected), \
                     patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
                    lines = menu._home_lines(LABELS, selected, {}, 1.0)
                self.assertEqual(len(lines), size[1])
                self.assertTrue(all(screen._display_width(line) < size[0] for line in lines))
                for label in LABELS:
                    self.assertIn(label, "\n".join(lines))

    def test_highlight_uses_explicit_colors_and_clipping_preserves_them(self) -> None:
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            highlighted = screen._ansi("学生档案      ", screen._SELECTED)
            clipped = screen._clip_cells(highlighted, 6)
        self.assertIn("\x1b[48;5;238m", clipped)
        self.assertTrue(clipped.endswith(screen._RESET))
        self.assertEqual(screen._display_width(clipped), 5)
        self.assertNotIn(";7m", highlighted)
        self.assertEqual(screen._display_width("e\u0301学生"), 5)

    def test_paint_clears_old_background_and_never_uses_newlines(self) -> None:
        with redirect_stdout(StringIO()) as output, patch("sys.stdout.isatty", return_value=True), \
             patch.dict(os.environ, {"NO_COLOR": "1"}):
            screen._paint(["one", "two"])
        self.assertEqual(output.getvalue(),
                         "\x1b[0m\x1b[2J\x1b[H"
                         "\x1b[1;1H\x1b[0m\x1b[2Kone\x1b[0m"
                         "\x1b[2;1H\x1b[0m\x1b[2Ktwo\x1b[0m")

    def test_animation_and_single_bottom_bar_at_every_size(self) -> None:
        for size in ((30, 12), (40, 16), (80, 20), (80, 24), (160, 48)):
            with self.subTest(size=size), patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
                first = menu._home_lines(LABELS, 0, {}, 0)
                second = menu._home_lines(LABELS, 0, {}, 1)
                self.assertNotEqual(first[:-1], second[:-1])
                self.assertTrue(any(0x2800 < ord(char) <= 0x28ff for line in first for char in line))
                self.assertEqual(first[-1], second[-1])
                self.assertIn("方向键", first[-1])
                self.assertNotIn("p", first[-1])
                self.assertNotIn("q/0", first[-1])
                self.assertNotIn("\n", first[-1])
                self.assertLess(screen._display_width(first[-1]), size[0])

    def test_live_terminal_dimensions_override_stale_environment(self) -> None:
        with patch.dict(os.environ, {"COLUMNS": "200", "LINES": "60"}), \
             patch("sys.stdout.fileno", return_value=1), \
             patch("os.get_terminal_size", return_value=os.terminal_size((80, 20))):
            self.assertEqual(screen._terminal_size(), (80, 20))

    def test_home_preview_changes_with_selection(self) -> None:
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 24))):
            text = "\n".join(menu._home_lines(LABELS, 3, {}, 0, animate=False))
        self.assertIn("选课与成绩", text)
        self.assertNotIn("p 播放", text)
        self.assertIn("记录选课", text)

    def test_pausing_animation_and_interrupt_restore_cursor(self) -> None:
        output = StringIO()
        preferences = {"animate": True}
        with redirect_stdout(output), patch("sys.stdout.isatty", return_value=True), \
             patch("xingyuan_sis.service.XingyuanService") as service, \
             patch.object(keys, "_read_key", side_effect=["pause", KeyboardInterrupt]), \
             patch.object(screen, "_clear"):
            service.return_value.stats.return_value = {}
            with self.assertRaises(KeyboardInterrupt):
                menu._home(None, LABELS, preferences=preferences)
        self.assertFalse(preferences["animate"])
        self.assertTrue(output.getvalue().endswith("\x1b[?25h"))

    def test_animation_resume_continues_from_paused_phase(self) -> None:
        preferences = {"animate": True, "angle": 10.0}
        angles = []

        def frame(*args, **kwargs):
            angles.append(args[3])
            return screen.ScreenFrame([""], [])

        with patch.object(menu.time, "monotonic", side_effect=[0.0, 1.0, 5.0, 6.0, 7.0]), \
             patch.object(menu, "_home_frame", side_effect=frame), \
             patch.object(keys, "_read_key", side_effect=["pause", None, "pause", "back"]), \
             patch.object(screen, "_paint"):
            result = menu._home_loop(LABELS, {}, None, 0, preferences, 10.0, [])

        self.assertIsNone(result)
        self.assertEqual(len(angles), 4)
        self.assertAlmostEqual(angles[0], 10.85)
        self.assertAlmostEqual(angles[1], 10.85)
        self.assertAlmostEqual(angles[2], 10.85)
        self.assertAlmostEqual(angles[3], 11.70)

    @unittest.skipIf(os.name == "nt", "POSIX terminal sequences")
    def test_key_typed_before_read_is_preserved(self) -> None:
        import pty
        import termios

        try:
            master, slave = pty.openpty()
        except OSError as error:
            self.skipTest(f"PTY unavailable in this environment: {error}")
        try:
            previous = termios.tcgetattr(slave)
            os.write(master, b"2")
            with patch("sys.stdin.fileno", return_value=slave):
                self.assertEqual(keys._read_key_posix(timeout=0.5), "2")
            self.assertEqual(termios.tcgetattr(slave), previous)
        finally:
            os.close(master)
            os.close(slave)

    @unittest.skipIf(os.name == "nt", "POSIX terminal sequences")
    def test_escape_sequences_and_terminal_restore(self) -> None:
        # tty imports termios functions by value; load it before mocking them.
        import tty

        for sequence, expected in ((b"[A", "up"), (b"OB", "down"),
                                   (b"[D", "left"), (b"OC", "right"),
                                   (b"[H", "home"), (b"[4~", "end"),
                                   (b"[3~", "other"), (b"", "back")):
            with self.subTest(sequence=sequence), patch("sys.stdin.fileno", return_value=10), \
                 patch("termios.tcgetattr", return_value=[1, 2, 3]), patch("tty.setcbreak") as cbreak, \
                 patch("termios.tcsetattr") as restore, patch("os.read", return_value=b"\x1b"), \
                 patch.object(keys, "_read_escape_sequence", return_value=sequence):
                self.assertEqual(keys._read_key_posix(), expected)
                import termios
                cbreak.assert_called_once_with(10, termios.TCSANOW)
                restore.assert_called_once()


class InteractionTests(unittest.TestCase):
    def test_paging_forward_back_and_exit(self) -> None:
        frames = []
        output = StringIO()
        def clear() -> None:
            frames.append(output.getvalue())
            output.seek(0)
            output.truncate()
        with patch.object(terminal_ui.shutil, "get_terminal_size", return_value=os.terminal_size((80, 8))), \
             patch("builtins.input", side_effect=["", "p", "q"]), redirect_stdout(output):
            terminal_ui.show_output("\n".join(f"row-{i}" for i in range(7)), clear)
        self.assertIn("row-0", frames[1])
        self.assertIn("第 2/3 页", frames[2])
        self.assertIn("row-0", output.getvalue())
        self.assertNotIn("row-6", output.getvalue())

    def test_long_chinese_lines_wrap_without_losing_content(self) -> None:
        text = "星原大学学生信息系统 / 20260001"
        lines = terminal_ui._wrap_line(text, 10)
        self.assertEqual("".join(lines), text)
        self.assertTrue(all(screen._display_width(line) <= 10 for line in lines))

    def test_invalid_numbers_retry_in_place(self) -> None:
        with patch("builtins.input", side_effect=["nan", "inf", "-1", "101", "92.5"]), \
             redirect_stdout(StringIO()) as output:
            self.assertEqual(terminal_ui.read_number("成绩", maximum=100), "92.5")
        self.assertEqual(output.getvalue().count("请输入"), 4)
        with patch("builtins.input", side_effect=["1.5", "48"]), redirect_stdout(StringIO()):
            self.assertEqual(terminal_ui.read_number("课时", integer=True), "48")

    def test_number_edit_preserves_blank_and_clear(self) -> None:
        for raw in ("", "-"):
            with patch("builtins.input", return_value=raw):
                self.assertEqual(terminal_ui.read_number("成绩", maximum=100, clearable=True), raw)

    def test_basic_menu_reports_invalid_choice_and_accepts_q(self) -> None:
        action = Mock()
        with patch.object(basic_ui, "_clear"), patch("builtins.input", side_effect=["9", "1", "q"]), \
             redirect_stdout(StringIO()) as output:
            basic_ui._menu("学生", [("1", "列表", action)])
        self.assertIn("没有这个选项", output.getvalue())
        action.assert_called_once()

    def test_basic_menu_input_end_exits_cleanly(self) -> None:
        with patch.object(basic_ui, "_clear"), patch("builtins.input", side_effect=EOFError), \
             redirect_stdout(StringIO()) as output:
            basic_ui.run()
        self.assertIn("已退出", output.getvalue())

    def test_both_menus_search_real_student_data(self) -> None:
        with TemporaryDirectory() as directory:
            db = Path(directory) / "test.db"
            initialize_database(db)
            seed_demo(db)
            for ui in (basic_ui,):
                with self.subTest(ui=ui.__name__), patch.object(ui, "_clear"), \
                     patch("builtins.input", side_effect=["林岚", ""]), \
                     redirect_stdout(StringIO()) as output:
                    terminal_ui.search_students(lambda args: ui._command(db, args))
                self.assertIn("20260001", output.getvalue())
                self.assertNotIn("20260002", output.getvalue())

    def test_database_failure_is_readable_and_has_nonzero_exit(self) -> None:
        with TemporaryDirectory() as directory, redirect_stderr(StringIO()) as errors:
            code = main(["--db", directory, "stu", "ls"])
        self.assertEqual(code, 1)
        self.assertIn("操作失败", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
