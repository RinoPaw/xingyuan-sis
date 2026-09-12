from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis import entry
from xingyuan_sis.terminal_capabilities import TerminalCapabilities, detect_terminal


class TerminalCapabilityTests(unittest.TestCase):
    def test_non_tty_never_supports_tui(self):
        with patch("sys.stdin.isatty", return_value=False), patch("sys.stdout.isatty", return_value=True):
            capabilities = detect_terminal()
        self.assertEqual(capabilities, TerminalCapabilities(False, False, False))
        self.assertFalse(capabilities.supports_tui)

    def test_detected_features_control_tui_support(self):
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), \
             patch("xingyuan_sis.terminal_capabilities._ansi_output_supported", return_value=True), \
             patch("xingyuan_sis.terminal_capabilities._immediate_input_supported", return_value=True):
            capabilities = detect_terminal()
        self.assertTrue(capabilities.supports_tui)

    def test_auto_mode_falls_back_to_basic(self):
        from xingyuan_sis import basic_ui

        with TemporaryDirectory() as directory, \
             patch.object(entry, "detect_terminal", return_value=TerminalCapabilities(True, False, True)), \
             patch.object(basic_ui, "run") as basic_run:
            db = Path(directory) / "test.db"
            code = entry.main(["--db", str(db)])
        self.assertEqual(code, 0)
        basic_run.assert_called_once_with(db)

    def test_auto_mode_uses_tui_when_supported(self):
        from xingyuan_sis.tui import app

        with TemporaryDirectory() as directory, \
             patch.object(entry, "detect_terminal", return_value=TerminalCapabilities(True, True, True)), \
             patch.object(app, "run") as tui_run:
            db = Path(directory) / "test.db"
            code = entry.main(["--db", str(db)])
        self.assertEqual(code, 0)
        tui_run.assert_called_once_with(db)

    def test_tui_flag_bypasses_capability_fallback(self):
        from xingyuan_sis.tui import app

        with TemporaryDirectory() as directory, \
             patch.object(entry, "detect_terminal", return_value=TerminalCapabilities(True, False, False)), \
             patch.object(app, "run") as tui_run:
            db = Path(directory) / "test.db"
            code = entry.main(["--db", str(db), "--tui"])
        self.assertEqual(code, 0)
        tui_run.assert_called_once_with(db)


if __name__ == "__main__":
    unittest.main()
