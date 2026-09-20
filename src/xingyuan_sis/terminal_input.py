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
from .tui.tokens import (
    _RESET,
    _TEXT_PRIMARY,
    _TEXT_ON_SELECTED,
    _SURFACE_DEFAULT,
    _SURFACE_SELECTED,
)


_ACTIVE = ContextVar("menu_input_style", default=False)
_PAGE_STYLE = _SURFACE_DEFAULT + _TEXT_PRIMARY
_FIELD_STYLE = _SURFACE_SELECTED + _TEXT_ON_SELECTED
_CURSOR_BLINK_SECONDS = 0.45


@contextmanager
def input_style(enabled: bool):
    token = _ACTIVE.set(enabled)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def _set_cursor_visible(visible: bool) -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[?25h" if visible else "\x1b[?25l")
        sys.stdout.flush()


@contextmanager
def editing_cursor():
    """Expose an editor cursor and keep it visible when the editor exits."""
    enabled = sys.stdout.isatty()
    if enabled:
        sys.stdout.write("\x1b[?25h\x1b[?12h\x1b[1 q")
        sys.stdout.flush()
    try:
        yield
    finally:
        if enabled:
            sys.stdout.write("\x1b[?25h\x1b[0 q")
            sys.stdout.flush()


def _display_width(text: str) -> int:
    return display_width(text)


def _terminal_columns() -> int:
    try:
        return max(8, os.get_terminal_size(sys.stdout.fileno()).columns)
    except (OSError, ValueError, AttributeError):
        return max(8, shutil.get_terminal_size((80, 24)).columns)


def _redraw_line(
    prompt: str,
    buffer: TextBuffer,
    *,
    colored: bool,
    secret: bool = False,
    field_width: int | None = None,
) -> None:
    prefix = f"  {prompt}" if colored else prompt
    if field_width is None:
        available = max(1, _terminal_columns() - _display_width(prefix) - 1)
        visible, cursor_cells = buffer.view(available, secret=secret)
        surface = _PAGE_STYLE if colored else ""
        sys.stdout.write("\r" + surface + "\x1b[2K" + prefix + visible)
        tail = _display_width(visible) - cursor_cells
        if tail > 0:
            sys.stdout.write(f"\x1b[{tail}D")
        sys.stdout.flush()
        return

    box_width = max(3, field_width)
    inner_width = max(1, box_width - 2)
    visible, cursor_cells = buffer.view(inner_width, secret=secret)
    content = " " + visible
    content += " " * max(0, box_width - _display_width(content))
    surface = _PAGE_STYLE if colored else ""
    field_surface = _FIELD_STYLE if colored else ""
    sys.stdout.write("\r" + surface + "\x1b[2K" + prefix + field_surface + content + surface)
    tail = box_width - 1 - cursor_cells
    if tail > 0:
        sys.stdout.write(f"\x1b[{tail}D")
    sys.stdout.flush()


def _redraw_inline(
    row: int,
    column: int,
    width: int,
    buffer: TextBuffer,
    *,
    colored: bool,
    secret: bool = False,
) -> None:
    """Redraw only an existing field value without clearing its terminal row."""
    field_width = max(1, width)
    visible, cursor_cells = buffer.view(field_width, secret=secret)
    content = visible + " " * max(0, field_width - _display_width(visible))
    style = _FIELD_STYLE if colored else ""
    surface = _PAGE_STYLE if colored else ""
    sys.stdout.write(f"\x1b[{max(1, row)};{max(1, column)}H" + style + content + surface)
    sys.stdout.write(f"\x1b[{max(1, row)};{max(1, column) + min(cursor_cells, field_width - 1)}H")
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
            buffer,
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


def _read_interactive_inline(
    *,
    row: int,
    column: int,
    width: int,
    colored: bool,
    secret: bool = False,
    initial_value: str = "",
) -> str:
    buffer = TextBuffer.from_value(initial_value)

    def redraw() -> None:
        _redraw_inline(
            row,
            column,
            width,
            buffer,
            colored=colored,
            secret=secret,
        )

    redraw()
    cursor_visible = True
    with input_mode(), editing_cursor():
        while True:
            event = read_event(_CURSOR_BLINK_SECONDS)
            if event is None:
                cursor_visible = not cursor_visible
                _set_cursor_visible(cursor_visible)
                continue
            if not cursor_visible:
                cursor_visible = True
                _set_cursor_visible(True)
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


def read_inline_input(
    prompt: str,
    *,
    row: int,
    column: int,
    width: int,
    secret: bool = False,
    initial_value: str = "",
) -> str:
    """Edit a value in place inside an already rendered TUI field."""
    interactive = _ACTIVE.get() and sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        return getpass.getpass(prompt) if secret else input(prompt)

    colored = os.environ.get("NO_COLOR") is None
    try:
        return _read_interactive_inline(
            row=row,
            column=column,
            width=width,
            colored=colored,
            secret=secret,
            initial_value=initial_value,
        )
    finally:
        if colored:
            sys.stdout.write(_RESET)
            sys.stdout.flush()


def heading(title: str) -> None:
    text = f"✦ 星原 / {title}"
    if _ACTIVE.get() and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        print(f"{_PAGE_STYLE}{text}{_RESET}\n")
    else:
        print(text + "\n")
