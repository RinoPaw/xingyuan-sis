"""Line input shared by the TUI and the plain CLI.

The default TUI uses a tiny stdlib line editor so Esc has deterministic
"cancel the innermost interaction" semantics. Plain CLI prompts still use
Python's normal ``input()`` unchanged.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import getpass
import os
import select
import shutil
import sys
import unicodedata

_ACTIVE = ContextVar("menu_input_style", default=False)
_SURFACE = "\x1b[48;5;235m\x1b[38;5;252m"
_FIELD_SURFACE = "\x1b[48;5;238m\x1b[38;5;255m"
_RESET = "\x1b[0m"


@contextmanager
def input_style(enabled: bool):
    token = _ACTIVE.set(enabled)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def _cell_width(char: str) -> int:
    if unicodedata.combining(char) or unicodedata.category(char) in {"Cf", "Mn", "Me"}:
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def _display_width(text: str) -> int:
    return sum(_cell_width(char) for char in text)


def _terminal_columns() -> int:
    try:
        return max(8, os.get_terminal_size(sys.stdout.fileno()).columns)
    except (OSError, ValueError, AttributeError):
        return max(8, shutil.get_terminal_size((80, 24)).columns)


def _visible_input(
    chars: list[str], cursor: int, width: int, *, secret: bool = False
) -> tuple[str, int]:
    """Return a one-line viewport and the cursor cell inside it."""
    width = max(1, width)
    rendered = ["•"] * len(chars) if secret else chars
    start = 0
    while start < cursor and _display_width("".join(rendered[start:cursor])) >= width:
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
    cursor_cells = min(width, _display_width("".join(rendered[start:cursor])))
    return "".join(shown), cursor_cells


def _redraw_line(
    prompt: str,
    chars: list[str],
    cursor: int,
    *,
    colored: bool,
    secret: bool = False,
    field_width: int | None = None,
) -> None:
    prefix = f"  {prompt}" if colored else prompt
    if field_width is None:
        available = max(1, _terminal_columns() - _display_width(prefix) - 1)
        visible, cursor_cells = _visible_input(chars, cursor, available, secret=secret)
        style = _SURFACE if colored else ""
        sys.stdout.write("\r" + style + "\x1b[2K" + prefix + visible)
        tail = _display_width(visible) - cursor_cells
        if tail > 0:
            sys.stdout.write(f"\x1b[{tail}D")
        sys.stdout.flush()
        return

    box_width = max(3, field_width)
    inner_width = max(1, box_width - 2)
    visible, cursor_cells = _visible_input(chars, cursor, inner_width, secret=secret)
    content = " " + visible
    content += " " * max(0, box_width - _display_width(content))
    surface = _SURFACE if colored else ""
    field_surface = _FIELD_SURFACE if colored else ""
    sys.stdout.write("\r" + surface + "\x1b[2K" + prefix + field_surface + content + surface)
    tail = box_width - 1 - cursor_cells
    if tail > 0:
        sys.stdout.write(f"\x1b[{tail}D")
    sys.stdout.flush()


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


def _apply_navigation(sequence: bytes, chars: list[str], cursor: int) -> tuple[int, bool]:
    if sequence in {b"[D", b"OD"}:
        return max(0, cursor - 1), True
    if sequence in {b"[C", b"OC"}:
        return min(len(chars), cursor + 1), True
    if sequence in {b"[H", b"OH", b"[1~", b"[7~"}:
        return 0, True
    if sequence in {b"[F", b"OF", b"[4~", b"[8~"}:
        return len(chars), True
    if sequence == b"[3~" and cursor < len(chars):
        del chars[cursor]
        return cursor, True
    return cursor, False


def _read_line_posix(
    prompt: str,
    *,
    colored: bool,
    secret: bool = False,
    field_width: int | None = None,
) -> str:
    import termios
    import tty

    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    chars: list[str] = []
    cursor = 0
    try:
        tty.setcbreak(fd, termios.TCSANOW)
        _redraw_line(
            prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
        )
        while True:
            raw = os.read(fd, 1)
            if not raw:
                raise KeyboardInterrupt
            if raw == b"\x1b":
                sequence = _read_escape_sequence(fd)
                if not sequence:
                    raise KeyboardInterrupt
                cursor, changed = _apply_navigation(sequence, chars, cursor)
                if changed:
                    _redraw_line(
                        prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
                    )
                continue
            if raw in {b"\r", b"\n"}:
                return "".join(chars)
            if raw in {b"\x03", b"\x04"}:
                raise KeyboardInterrupt
            if raw in {b"\x08", b"\x7f"}:
                if cursor:
                    cursor -= 1
                    del chars[cursor]
                    _redraw_line(
                        prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
                    )
                continue
            if raw == b"\x01":
                cursor = 0
                _redraw_line(
                    prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
                )
                continue
            if raw == b"\x05":
                cursor = len(chars)
                _redraw_line(
                    prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
                )
                continue
            if raw == b"\x15":
                chars.clear()
                cursor = 0
                _redraw_line(
                    prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
                )
                continue
            if raw == b"\x0b":
                del chars[cursor:]
                _redraw_line(
                    prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
                )
                continue
            if raw == b"\t":
                continue

            char = _read_utf8_char(fd, raw)
            if char and all(part.isprintable() for part in char):
                chars[cursor:cursor] = list(char)
                cursor += len(char)
                _redraw_line(
                    prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
                )
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def _read_line_windows(
    prompt: str,
    *,
    colored: bool,
    secret: bool = False,
    field_width: int | None = None,
) -> str:
    import msvcrt

    chars: list[str] = []
    cursor = 0
    _redraw_line(
        prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
    )
    while True:
        char = msvcrt.getwch()
        if char in {"\x00", "\xe0"}:
            code = msvcrt.getwch()
            if code == "K":
                cursor = max(0, cursor - 1)
            elif code == "M":
                cursor = min(len(chars), cursor + 1)
            elif code == "G":
                cursor = 0
            elif code == "O":
                cursor = len(chars)
            elif code == "S" and cursor < len(chars):
                del chars[cursor]
            _redraw_line(
                prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
            )
            continue
        if char == "\x1b" or char in {"\x03", "\x04"}:
            raise KeyboardInterrupt
        if char in {"\r", "\n"}:
            return "".join(chars)
        if char in {"\x08", "\x7f"}:
            if cursor:
                cursor -= 1
                del chars[cursor]
                _redraw_line(
                    prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
                )
            continue
        if char == "\t":
            continue
        if char and char.isprintable():
            chars.insert(cursor, char)
            cursor += 1
            _redraw_line(
                prompt, chars, cursor, colored=colored, secret=secret, field_width=field_width
            )


def _read_interactive_line(
    prompt: str,
    *,
    colored: bool,
    secret: bool = False,
    field_width: int | None = None,
) -> str:
    if os.name == "nt":
        return _read_line_windows(
            prompt, colored=colored, secret=secret, field_width=field_width
        )
    return _read_line_posix(
        prompt, colored=colored, secret=secret, field_width=field_width
    )


def read_input(
    prompt: str,
    *,
    secret: bool = False,
    field_width: int | None = None,
) -> str:
    interactive = _ACTIVE.get() and sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        return getpass.getpass(prompt) if secret else input(prompt)

    colored = os.environ.get("NO_COLOR") is None
    try:
        if field_width is None:
            if secret:
                return _read_interactive_line(prompt, colored=colored, secret=True)
            return _read_interactive_line(prompt, colored=colored)
        return _read_interactive_line(
            prompt, colored=colored, secret=secret, field_width=field_width
        )
    finally:
        if colored:
            sys.stdout.write(_RESET)
            sys.stdout.flush()


def heading(title: str) -> None:
    text = f"✦ 星原 / {title}"
    if _ACTIVE.get() and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        print(f"{_SURFACE}{text}{_RESET}\n")
    else:
        print(text + "\n")
