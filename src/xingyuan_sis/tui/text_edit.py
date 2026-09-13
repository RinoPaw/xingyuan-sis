"""State and raw key decoding for editable TUI text fields."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import os
import select
import sys
import time
import unicodedata


_RAW_ACTIVE = ContextVar("tui_text_input_mode", default=False)


def _cell_width(char: str) -> int:
    if unicodedata.combining(char) or unicodedata.category(char) in {"Cf", "Mn", "Me"}:
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def display_width(text: str) -> int:
    return sum(_cell_width(char) for char in text)


@dataclass(frozen=True)
class TextEvent:
    kind: str
    text: str = ""


@dataclass
class TextBuffer:
    chars: list[str]
    cursor: int

    @classmethod
    def from_value(cls, value: str = "") -> "TextBuffer":
        chars = list(value)
        return cls(chars, len(chars))

    @property
    def value(self) -> str:
        return "".join(self.chars)

    def apply(self, event: TextEvent) -> str | None:
        kind = event.kind
        if kind == "insert":
            if event.text:
                parts = list(event.text)
                self.chars[self.cursor:self.cursor] = parts
                self.cursor += len(parts)
            return None
        if kind == "left":
            self.cursor = max(0, self.cursor - 1)
            return None
        if kind == "right":
            self.cursor = min(len(self.chars), self.cursor + 1)
            return None
        if kind == "home":
            self.cursor = 0
            return None
        if kind == "end":
            self.cursor = len(self.chars)
            return None
        if kind == "delete":
            if self.cursor < len(self.chars):
                del self.chars[self.cursor]
            return None
        if kind == "backspace":
            if self.cursor:
                self.cursor -= 1
                del self.chars[self.cursor]
            return None
        if kind == "clear":
            self.chars.clear()
            self.cursor = 0
            return None
        if kind == "kill-end":
            del self.chars[self.cursor:]
            return None
        if kind in {"submit", "cancel", "up", "down", "tab"}:
            return kind
        return None

    def view(self, width: int, *, secret: bool = False) -> tuple[str, int]:
        """Return the visible viewport and cursor cell inside it."""
        width = max(1, width)
        rendered = ["•"] * len(self.chars) if secret else self.chars
        start = 0
        while start < self.cursor and display_width("".join(rendered[start:self.cursor])) >= width:
            start += 1

        shown: list[str] = []
        used = 0
        for char in rendered[start:]:
            cells = _cell_width(char)
            if shown and used + cells > width:
                break
            if not shown and cells > width:
                break
            shown.append(char)
            used += cells

        cursor_cells = min(width, display_width("".join(rendered[start:self.cursor])))
        return "".join(shown), cursor_cells


@contextmanager
def input_mode():
    """Keep the terminal in raw-enough text mode for a whole form event loop."""
    if _RAW_ACTIVE.get():
        yield
        return

    token = _RAW_ACTIVE.set(True)
    previous = None
    fd = None
    if os.name != "nt" and sys.stdin.isatty():
        import termios
        import tty

        fd = sys.stdin.fileno()
        previous = termios.tcgetattr(fd)
        tty.setcbreak(fd, termios.TCSANOW)
    try:
        yield
    finally:
        try:
            if previous is not None and fd is not None:
                import termios

                termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        finally:
            _RAW_ACTIVE.reset(token)


def _read_escape_sequence(fd: int) -> bytes:
    sequence = bytearray()
    while len(sequence) < 32:
        ready, _, _ = select.select([fd], [], [], 0.035)
        if not ready:
            break
        chunk = os.read(fd, 1)
        if not chunk:
            break
        sequence += chunk
        byte = chunk[0]
        if len(sequence) >= 2 and sequence.startswith((b"[", b"O")) and 0x40 <= byte <= 0x7E:
            break
    return bytes(sequence)


def _read_utf8_char(fd: int, first: bytes) -> str:
    lead = first[0]
    if lead < 0x80:
        return first.decode("ascii", errors="ignore")
    if 0xC2 <= lead <= 0xDF:
        needed = 1
    elif 0xE0 <= lead <= 0xEF:
        needed = 2
    elif 0xF0 <= lead <= 0xF4:
        needed = 3
    else:
        return ""
    data = bytearray(first)
    for _ in range(needed):
        data += os.read(fd, 1)
    return bytes(data).decode("utf-8", errors="ignore")


def _escape_event(sequence: bytes) -> TextEvent:
    if not sequence:
        return TextEvent("cancel")
    if sequence in {b"[A", b"OA"}:
        return TextEvent("up")
    if sequence in {b"[B", b"OB"}:
        return TextEvent("down")
    if sequence in {b"[D", b"OD"}:
        return TextEvent("left")
    if sequence in {b"[C", b"OC"}:
        return TextEvent("right")
    if sequence in {b"[H", b"OH", b"[1~", b"[7~"}:
        return TextEvent("home")
    if sequence in {b"[F", b"OF", b"[4~", b"[8~"}:
        return TextEvent("end")
    if sequence == b"[3~":
        return TextEvent("delete")
    return TextEvent("other")


def _read_event_posix(timeout: float | None) -> TextEvent | None:
    fd = sys.stdin.fileno()
    if timeout is not None:
        ready, _, _ = select.select([fd], [], [], max(0.0, timeout))
        if not ready:
            return None

    raw = os.read(fd, 1)
    if not raw:
        return TextEvent("cancel")
    if raw == b"\x1b":
        return _escape_event(_read_escape_sequence(fd))
    if raw in {b"\r", b"\n"}:
        return TextEvent("submit")
    if raw in {b"\x03", b"\x04"}:
        return TextEvent("cancel")
    if raw in {b"\x08", b"\x7f"}:
        return TextEvent("backspace")
    if raw == b"\x01":
        return TextEvent("home")
    if raw == b"\x05":
        return TextEvent("end")
    if raw == b"\x15":
        return TextEvent("clear")
    if raw == b"\x0b":
        return TextEvent("kill-end")
    if raw == b"\t":
        return TextEvent("tab")

    char = _read_utf8_char(fd, raw)
    if char and all(part.isprintable() for part in char):
        return TextEvent("insert", char)
    return TextEvent("other")


def _read_event_windows(timeout: float | None) -> TextEvent | None:
    import msvcrt

    if timeout is not None:
        deadline = time.monotonic() + max(0.0, timeout)
        while not msvcrt.kbhit():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(0.01, remaining))

    char = msvcrt.getwch()
    if char in {"\x00", "\xe0"}:
        code = msvcrt.getwch()
        return {
            "H": TextEvent("up"),
            "P": TextEvent("down"),
            "K": TextEvent("left"),
            "M": TextEvent("right"),
            "G": TextEvent("home"),
            "O": TextEvent("end"),
            "S": TextEvent("delete"),
        }.get(code, TextEvent("other"))
    if char == "\x1b" or char in {"\x03", "\x04"}:
        return TextEvent("cancel")
    if char in {"\r", "\n"}:
        return TextEvent("submit")
    if char in {"\x08", "\x7f"}:
        return TextEvent("backspace")
    if char == "\x01":
        return TextEvent("home")
    if char == "\x05":
        return TextEvent("end")
    if char == "\x15":
        return TextEvent("clear")
    if char == "\x0b":
        return TextEvent("kill-end")
    if char == "\t":
        return TextEvent("tab")
    if char and char.isprintable():
        return TextEvent("insert", char)
    return TextEvent("other")


def read_event(timeout: float | None = None) -> TextEvent | None:
    """Read one text-editing event. Use input_mode() around repeated reads."""
    if not _RAW_ACTIVE.get():
        with input_mode():
            return read_event(timeout)
    if os.name == "nt":
        return _read_event_windows(timeout)
    return _read_event_posix(timeout)
