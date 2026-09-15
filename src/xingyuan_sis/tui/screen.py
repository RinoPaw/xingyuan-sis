"""Terminal cells, hit regions and surface lifecycle."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
import os
import re
import shutil
import sys
import unicodedata
from typing import Sequence

from .keys import MouseClick
from .tokens import (
    _RESET,
    _BOLD,
    _TEXT_PRIMARY,
    _TEXT_SECONDARY,
    _TEXT_ACCENT,
    _TEXT_ON_SELECTED,
    _BORDER_SUBTLE,
    _SURFACE_DEFAULT,
    _SURFACE_TOPBAR,
    _SURFACE_FOOTER,
    _SURFACE_INTERACTIVE,
    _SURFACE_SELECTED,
    _TEXT_DANGER,
    _DECORATIVE_GOLD,
)


_PAGE_STYLE = _SURFACE_DEFAULT + _TEXT_PRIMARY
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _ansi(text: str, style: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR") is not None:
        return text
    return f"{style}{text}{_RESET}"


def _display_width(text: str) -> int:
    plain = _ANSI_RE.sub("", text)
    return sum(_cell_width(char) for char in plain)


def _cell_width(char: str) -> int:
    if unicodedata.combining(char) or unicodedata.category(char) in {"Cf", "Mn", "Me"}:
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def _pad_cells(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _terminal_size() -> os.terminal_size:
    # Termux/proot can retain stale COLUMNS/LINES after pinch-to-zoom.
    # Prefer the live PTY dimensions over environment variables.
    try:
        return os.get_terminal_size(sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):
        return shutil.get_terminal_size((80, 24))


def _clear() -> None:
    if sys.stdout.isatty():
        surface = _PAGE_STYLE if os.environ.get("NO_COLOR") is None else ""
        print(_RESET + surface + "\x1b[2J\x1b[H", end="", flush=True)
    else:
        print("\n" * 40)


@contextmanager
def _terminal_session():
    """Keep the terminal padding and unused cells on the application surface."""
    try:
        sys.stdout.write("\x1b[?1049h")
        _clear()
        yield
    finally:
        sys.stdout.write(_RESET + "\x1b[?1049l\x1b[?25h")
        sys.stdout.flush()


class NavigateTo(Exception):
    """Unwind nested menus until the requested breadcrumb is reached."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.path = path


@dataclass(frozen=True)
class HitRegion:
    x: int
    y: int
    width: int
    action: str


@dataclass
class ScreenFrame:
    lines: list[str]
    regions: list[HitRegion]


def _hit_action(click: MouseClick, regions: Sequence[HitRegion]) -> str | None:
    return next((region.action for region in regions
                 if click.y == region.y and region.x <= click.x < region.x + region.width), None)


def _breadcrumb(title: str, width: int, row: int = 2) -> tuple[str, list[HitRegion]]:
    parts = ["首页", *title.split(" / ")]
    text = ""
    regions = []
    for index, label in enumerate(parts):
        if index:
            text += _ansi(" / ", _BORDER_SUBTLE)
        cell = _display_width(text)
        clickable = index < len(parts) - 1 and cell + _display_width(label) <= width
        if clickable:
            path = " / ".join(parts[1:index + 1])
            regions.append(HitRegion(cell + 1, row, _display_width(label), f"navigate:{path}"))
        text += _ansi(label, _TEXT_ACCENT + "\x1b[4m" if clickable else _TEXT_SECONDARY)
    return _clip_cells(text, width), regions


def _clip_cells(text: str, width: int) -> str:
    """Clip terminal cells without dropping or splitting SGR sequences."""
    if width <= 0:
        return ""
    if _display_width(text) <= width:
        return text
    result: list[str] = []
    used = 0
    for token in re.split(f"({_ANSI_RE.pattern})", text):
        if _ANSI_RE.fullmatch(token):
            result.append(token)
            continue
        for char in token:
            cells = _cell_width(char)
            if used + cells > width - 1:
                return "".join(result) + "…" + (_RESET if "\x1b" in text else "")
            result.append(char)
            used += cells
    return "".join(result)


def _paint(lines: Sequence[str], previous: Sequence[str] = ()) -> None:
    if sys.stdout.isatty():
        # Absolute row positions work even when the terminal disables ONLCR.
        # Reset before erasing so a selected background cannot bleed.
        surface = _PAGE_STYLE if os.environ.get("NO_COLOR") is None else ""
        if len(lines) != len(previous) or max(map(_display_width, lines), default=0) != max(map(_display_width, previous), default=0):
            _clear()
            previous = ()
        frame = "".join(
            f"\x1b[{row};1H{_RESET}{surface}\x1b[2K"
            + line.replace(_RESET, _RESET + surface)
            + _RESET
            for row, line in enumerate(lines, start=1)
            if row > len(previous) or line != previous[row - 1]
        )
        sys.stdout.write(frame)
        sys.stdout.flush()
        return
    print("\n".join(lines))
