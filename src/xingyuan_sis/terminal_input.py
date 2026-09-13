"""Line input shared by the TUI and the plain CLI.

Interactive TUI text editing is backed by :mod:`xingyuan_sis.tui.text_edit`,
which owns the editable buffer and raw key decoding. Plain CLI prompts still
use Python's normal ``input()`` / ``getpass()`` behavior.
"""
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
import getpass
import os
import shutil
import sys

from .tui.text_edit import TextBuffer, display_width, input_mode, read_event
from .tui.tokens import _RESET, _SURFACE, _SELECTED as _FIELD_SURFACE


_ACTIVE = ContextVar("menu_input_style", default=False)


@contextmanager
def input_style(enabled: bool):
    token = _ACTIVE.set(enabled)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def _display_width(text: str) -> int:
    return display_width(text)


def _terminal_columns() -> int:
    try:
        return max(8, os.get_terminal_size(sys.stdout.fileno()).columns)
    except (OSError, ValueError, AttributeError):
        return max(8, shutil.get_terminal_size((80, 24)).columns)


def _visible_input(
    chars: list[str], cursor: int, width: int, *, secret: bool = False
) -> tuple[str, int]:
    """Compatibility wrapper around the shared TUI text buffer viewport."""
    buffer = TextBuffer(list(chars), max(0, min(cursor, len(chars))))
    return buffer.view(width, secret=secret)


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


def _refresh_idle(on_idle: Callable[[str], None], value: str, redraw: Callable[[], None]) -> None:
    """Refresh an animated surface without exposing intermediate cursor moves."""
    hide_cursor = sys.stdout.isatty()
    if hide_cursor:
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()
    try:
        on_idle(value)
        redraw()
    finally:
        if hide_cursor:
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()


def _read_interactive_line(
    prompt: str,
    *,
    colored: bool,
    secret: bool = False,
    field_width: int | None = None,
    on_idle: Callable[[str], None] | None = None,
    idle_interval: float = 0.15,
    initial_value: str = "",
) -> str:
    buffer = TextBuffer.from_value(initial_value)

    def redraw() -> None:
        _redraw_line(
            prompt,
            buffer.chars,
            buffer.cursor,
            colored=colored,
            secret=secret,
            field_width=field_width,
        )

    redraw()
    with input_mode():
        while True:
            event = read_event(max(0.01, idle_interval) if on_idle is not None else None)
            if event is None:
                if on_idle is not None:
                    _refresh_idle(on_idle, buffer.value, redraw)
                continue

            before = (buffer.value, buffer.cursor)
            action = buffer.apply(event)
            if action == "submit":
                return buffer.value
            if action == "cancel":
                raise KeyboardInterrupt
            if (buffer.value, buffer.cursor) != before:
                redraw()


def read_input(
    prompt: str,
    *,
    secret: bool = False,
    field_width: int | None = None,
    on_idle: Callable[[str], None] | None = None,
    idle_interval: float = 0.15,
    initial_value: str = "",
) -> str:
    interactive = _ACTIVE.get() and sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        return getpass.getpass(prompt) if secret else input(prompt)

    colored = os.environ.get("NO_COLOR") is None
    kwargs: dict[str, object] = {"colored": colored}
    if secret:
        kwargs["secret"] = True
    if field_width is not None:
        kwargs["field_width"] = field_width
    if on_idle is not None:
        kwargs["on_idle"] = on_idle
        kwargs["idle_interval"] = idle_interval
    if initial_value:
        kwargs["initial_value"] = initial_value
    try:
        return _read_interactive_line(prompt, **kwargs)
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
