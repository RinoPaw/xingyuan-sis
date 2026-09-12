from __future__ import annotations

from dataclasses import dataclass
import os
import sys


@dataclass(frozen=True)
class TerminalCapabilities:
    interactive: bool
    ansi_output: bool
    immediate_input: bool

    @property
    def supports_tui(self) -> bool:
        return self.interactive and self.ansi_output and self.immediate_input


def _windows_ansi_output() -> bool:
    try:
        import ctypes
        import msvcrt

        handle = msvcrt.get_osfhandle(sys.stdout.fileno())
        mode = ctypes.c_uint()
        kernel32 = ctypes.windll.kernel32
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        enable_virtual_terminal_processing = 0x0004
        if mode.value & enable_virtual_terminal_processing:
            return True
        return bool(
            kernel32.SetConsoleMode(
                handle,
                mode.value | enable_virtual_terminal_processing,
            )
        )
    except (AttributeError, OSError, ValueError):
        return bool(os.environ.get("WT_SESSION") or os.environ.get("ANSICON"))


def _ansi_output_supported() -> bool:
    if os.name == "nt":
        return _windows_ansi_output()
    term = os.environ.get("TERM", "")
    return term.lower() != "dumb"


def _immediate_input_supported() -> bool:
    try:
        if os.name == "nt":
            import msvcrt  # noqa: F401
        else:
            import select  # noqa: F401
            import termios  # noqa: F401
        return True
    except ImportError:
        return False


def detect_terminal() -> TerminalCapabilities:
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        return TerminalCapabilities(False, False, False)
    return TerminalCapabilities(
        interactive=True,
        ansi_output=_ansi_output_supported(),
        immediate_input=_immediate_input_supported(),
    )
