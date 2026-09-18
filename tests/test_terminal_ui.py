from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from xingyuan_sis import basic_ui, terminal_ui
from xingyuan_sis.auth import Identity
from xingyuan_sis.tui import keys, screen
from xingyuan_sis.tui.commands import Command, resolve_shortcut
from xingyuan_sis.database import initialize_database
from xingyuan_sis.entry import main
from xingyuan_sis.seed_data import STUDENTS, seed_demo


class KeyboardAndTerminalTests(unittest.TestCase):
    def test_plain_keys_decode_physical_input_without_business_meaning(self) -> None:
        for char, expected in (
            ("\r", "select"), (" ", " "), ("j", "down"), ("K", "up"),
            ("0", "0"), ("\x7f", "backspace"), ("Q", "Q"), ("3", "3"),
            ("p", "p"), ("a", "a"), ("/", "/"), ("\t", "focus"),
        ):
            with self.subTest(char=char):
                self.assertEqual(keys._plain_key(char), expected)
        with self.assertRaises(KeyboardInterrupt):
            keys._plain_key("\x03")
        with self.assertRaises(EOFError):
            keys._plain_key("")

    def test_printable_shortcuts_are_resolved_by_active_commands(self) -> None:
        create = Command("create", "增加", "a")
        self.assertEqual(resolve_shortcut("a", (create,)), "create")
        self.assertEqual(resolve_shortcut("A", (create,)), "create")
        self.assertEqual(resolve_shortcut("d", (create,)), "d")

    def test_highlight_uses_semantic_selection_tokens_and_clipping_preserves_them(self) -> None:
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            selected_style = screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
            highlighted = screen._ansi("学生档案      ", selected_style)
            clipped = screen._clip_cells(highlighted, 6)
        self.assertIn(screen._SURFACE_SELECTED, clipped)
        self.assertIn(screen._TEXT_ON_SELECTED, clipped)
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

    def test_live_terminal_dimensions_override_stale_environment(self) -> None:
        with patch.dict(os.environ, {"COLUMNS": "200", "LINES": "60"}), \
             patch("sys.stdout.fileno", return_value=1), \
             patch("os.get_terminal_size", return_value=os.terminal_size((80, 20))):
            self.assertEqual(screen._terminal_size(), (80, 20))

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
        import tty

        for sequence, expected in ((b"[A", "up"), (b"OB", "down"),
                                   (b"[D", "left"), (b"OC", "right"),
                                   (b"[H", "home"), (b"[4~", "end"),
                                   (b"[Z", "other"), (b"[5~", "page_up"), (b"[6~", "page_down"),
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
        with patch.object(basic_ui, "read_session", return_value=Identity("Administrator", "admin")), patch.object(basic_ui, "_clear"), patch("builtins.input", side_effect=["9", "1", "q"]), \
             redirect_stdout(StringIO()) as output:
            basic_ui._menu("学生", [("1", "列表", action)])
        self.assertIn("没有这个选项", output.getvalue())
        action.assert_called_once()

    def test_basic_menu_input_end_exits_cleanly(self) -> None:
        with patch.object(basic_ui, "read_session", return_value=Identity("Administrator", "admin")), patch.object(basic_ui, "_clear"), patch("builtins.input", side_effect=EOFError), \
             redirect_stdout(StringIO()) as output:
            basic_ui.run()
        self.assertIn("已退出", output.getvalue())

    def test_basic_menu_searches_current_seed_data(self) -> None:
        target_no, target_name = str(STUDENTS[0][0]), str(STUDENTS[0][1])
        other_no = str(STUDENTS[1][0])
        with TemporaryDirectory() as directory:
            db = Path(directory) / "test.db"
            initialize_database(db)
            seed_demo(db)
            with patch("xingyuan_sis.auth_cli.require_identity", return_value=Identity("Administrator", "admin")), patch.object(basic_ui, "_clear"), \
                 patch("builtins.input", side_effect=[target_name, ""]), \
                 redirect_stdout(StringIO()) as output:
                terminal_ui.search_students(lambda args: basic_ui._command(db, args))
            self.assertIn(target_no, output.getvalue())
            self.assertNotIn(other_no, output.getvalue())

    def test_database_failure_is_readable_and_has_nonzero_exit(self) -> None:
        with TemporaryDirectory() as directory, redirect_stderr(StringIO()) as errors:
            code = main(["--db", directory, "stu", "ls"])
        self.assertEqual(code, 1)
        self.assertIn("操作失败", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
