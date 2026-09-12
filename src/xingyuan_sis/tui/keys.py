"""Keyboard and SGR mouse decoding with scoped terminal modes."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
import os
import re
import select
import sys
import time


@dataclass(frozen=True)
class MouseClick:
    x: int
    y: int


@dataclass(frozen=True)
class MouseScroll:
    x: int
    y: int
    direction: str


def _mouse_event(sequence: bytes) -> str | MouseClick | MouseScroll:
    match = re.fullmatch(rb"\[<(\d+);(\d+);(\d+)([Mm])", sequence)
    if match is None:
        return "other"
    button, x, y = (int(match[i]) for i in (1, 2, 3))
    if x < 1 or y < 1:
        return "other"
    # Activate on release, so a pending release sequence cannot leak into
    # the native text input opened by a click.
    if match[4] == b"m":
        return MouseClick(x, y) if button == 0 else "other"
    if button == 64:
        return MouseScroll(x, y, "up")
    if button == 65:
        return MouseScroll(x, y, "down")
    return "other"


@contextmanager
def _mouse_tracking():
    enabled = os.name != "nt" and sys.stdin.isatty() and sys.stdout.isatty()
    if enabled:
        import termios
        import tty

        fd = sys.stdin.fileno()
        previous = termios.tcgetattr(fd)
        # Mouse reports can arrive while painting, between individual reads.
        # Keep echo disabled until tracking ends, including during animations.
        tty.setcbreak(fd, termios.TCSANOW)
    try:
        if enabled:
            sys.stdout.write("\x1b[?25l\x1b[?1000h\x1b[?1006h")
            sys.stdout.flush()
        yield
    finally:
        if enabled:
            try:
                sys.stdout.write("\x1b[?1000l\x1b[?1006l\x1b[?25h")
                sys.stdout.flush()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def _read_key_windows(timeout: float | None = None) -> str | None:
    import msvcrt

    if timeout is not None:
        deadline = time.monotonic() + timeout
        while not msvcrt.kbhit():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(0.01, remaining))

    char = msvcrt.getwch()
    if char in {"\x00", "\xe0"}:
        code = msvcrt.getwch()
        if code == "H":
            return "up"
        if code == "P":
            return "down"
        if code == "G":
            return "home"
        if code == "O":
            return "end"
        return "other"
    return _plain_key(char)


def _plain_key(char: str) -> str:
    if char == "\x03":
        raise KeyboardInterrupt
    if not char or char == "\x04":
        raise EOFError
    if char in {" ", "\r", "\n"}:
        return "select"
    if char in {"\x1b", "\x08", "\x7f", "0"} or char.lower() == "q":
        return "back"
    if char.lower() == "k":
        return "up"
    if char.lower() == "j":
        return "down"
    if char.lower() == "p":
        return "pause"
    if char.lower() == "n":
        return "next"
    shortcuts = {"a": "create", "e": "edit", "d": "delete", "s": "save", "/": "search",
                 "r": "refresh", "\t": "focus", "i": "import", "o": "export", "g": "seed"}
    if char.lower() in shortcuts:
        return shortcuts[char.lower()]
    return char if char in "123456789" else "other"


def _read_escape_sequence(fd: int) -> bytes:
    """Read the bytes following ESC without going through TextIO buffering."""
    sequence = bytearray()
    while len(sequence) < 64:
        ready, _, _ = select.select([fd], [], [], 0.08)
        if not ready:
            break
        chunk = os.read(fd, 1)
        if not chunk:
            break
        sequence += chunk
        byte = chunk[0]
        if len(sequence) >= 2 and 0x40 <= byte <= 0x7E:
            break
    return bytes(sequence)


def _read_key_posix(timeout: float | None = None) -> str | MouseClick | MouseScroll | None:
    import termios
    import tty

    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    try:
        # TCSAFLUSH (the default) discards keys typed while a frame is drawn.
        tty.setcbreak(fd, termios.TCSANOW)
        if timeout is not None:
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                return None
        char = os.read(fd, 1)
        if char == b"\x1b":
            sequence = _read_escape_sequence(fd)
            if sequence.startswith(b"[<"):
                return _mouse_event(sequence)
            if sequence in {b"[A", b"OA"} or (
                sequence.startswith(b"[") and sequence.endswith(b"A")
            ):
                return "up"
            if sequence in {b"[B", b"OB"} or (
                sequence.startswith(b"[") and sequence.endswith(b"B")
            ):
                return "down"
            if sequence == b"[5~":
                return "page_up"
            if sequence == b"[6~":
                return "page_down"
            if sequence in {b"[H", b"OH", b"[1~", b"[7~"}:
                return "home"
            if sequence in {b"[F", b"OF", b"[4~", b"[8~"}:
                return "end"
            return "other" if sequence else "back"
        return _plain_key(char.decode("ascii", errors="replace"))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def _read_key(timeout: float | None = None) -> str | MouseClick | MouseScroll | None:
    if os.name == "nt":
        return _read_key_windows(timeout)
    return _read_key_posix(timeout)
