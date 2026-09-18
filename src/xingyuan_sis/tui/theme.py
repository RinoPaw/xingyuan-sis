"""Shared styling primitives for the interactive terminal UI."""
from __future__ import annotations

from typing import Sequence

from . import screen


_BUTTON = screen._SURFACE_INTERACTIVE + screen._TEXT_PRIMARY
_BUTTON_CURRENT = screen._SURFACE_INTERACTIVE + screen._TEXT_ACCENT
_BAR_SURFACE = screen._SURFACE_FOOTER + screen._TEXT_PRIMARY
_TOPBAR = screen._SURFACE_TOPBAR + screen._TEXT_ACCENT + screen._BOLD
_SECONDARY = screen._SURFACE_INTERACTIVE + screen._TEXT_PRIMARY
_SECONDARY_FOCUS = screen._SURFACE_SELECTED + screen._TEXT_ACCENT + screen._BOLD


def bar_space(count: int) -> str:
    return screen._ansi(" " * max(0, count), _BAR_SURFACE)


def button(
    label: str,
    *,
    selected: bool = False,
    current: bool = False,
    width: int | None = None,
) -> str:
    """Render an action button; color/surface carry focus without chevrons."""
    marker = "·" if current and not selected else " "
    shown = f"[{marker}{label} ]"
    if width is not None:
        shown = screen._pad_cells(screen._clip_cells(shown, width), width)
    if selected:
        style = screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
    elif current:
        style = _BUTTON_CURRENT
    else:
        style = _BUTTON
    return screen._ansi(shown, style)


def secondary_item(label: str, *, selected: bool = False, width: int = 10) -> str:
    """Render compact second-level navigation without brackets or arrows."""
    width = max(1, width)
    shown = screen._pad_cells(screen._clip_cells(f" {label}", width), width)
    return screen._ansi(shown, _SECONDARY_FOCUS if selected else _SECONDARY)


def nav_item(
    label: str,
    *,
    selected: bool = False,
    current: bool = False,
    width: int | None = None,
) -> str:
    """Render navigation with strong focus and weak current-location states."""
    marker = "▌" if selected else "▏" if current else " "
    shown = f"{marker} {label}"
    if width is not None:
        shown = screen._pad_cells(screen._clip_cells(shown, width), width)
    if selected:
        style = screen._BOLD + screen._TEXT_ACCENT
    elif current:
        style = screen._TEXT_ACCENT
    else:
        style = screen._TEXT_PRIMARY
    return screen._ansi(shown, style)


def topbar(width: int, *, database: str | None = None, context: str = "") -> str:
    """One application identity; account and storage are secondary context."""
    left = screen._clip_cells("✦ 星原 SIS", width)
    available = width - screen._display_width(left)
    database_text = f"LOCAL  {database}" if database else ""
    right = "   ".join(part for part in (context, database_text) if part)
    if screen._display_width(right) + 2 > available:
        right = database_text if screen._display_width(database_text) + 2 <= available else ""
    gap = max(0, available - screen._display_width(right))
    return (
        screen._ansi(left, _TOPBAR)
        + screen._ansi(" " * gap + right, screen._SURFACE_TOPBAR + screen._TEXT_SECONDARY)
    )


def view_labels(width: int, choices: Sequence[tuple[str, int | None, str, bool]]) -> list[str]:
    """Fit all views before sacrificing their descriptive labels."""
    full = [
        f"{i + 1} {label}" + (f" · {count}" if count is not None else "")
        for i, (label, count, _, _) in enumerate(choices)
    ]
    short = [
        f"{i + 1} · {count}" if count is not None else f"{i + 1} {label}"
        for i, (label, count, _, _) in enumerate(choices)
    ]
    for labels in (full, short):
        if sum(screen._display_width(label) + 5 for label in labels) <= width:
            return labels
    return [str(i + 1) for i in range(len(choices))]


def notice(message: str, *, error: bool = False) -> str:
    style = screen._TEXT_DANGER if error else screen._TEXT_SECONDARY
    return screen._ansi(("! " if error else "· ") + message, style) if message else ""


def footer(
    width: int,
    *,
    switch_focus: bool = False,
    command_hints: Sequence[str] = (),
    enter: str = "打开",
    escape: str = "返回",
) -> str:
    """Render navigation plus shortcuts derived from commands active here."""
    required = [
        *( ["[ Tab 切换区域 ]"] if switch_focus else []),
        "[ 方向键 移动 ]",
        f"[ Enter {enter} ]",
        f"[ Esc {escape} ]",
    ]
    optional = [f"[ {hint} ]" for hint in command_hints]
    labels = required + optional
    while optional and sum(screen._display_width(label) for label in labels) + len(labels) + 1 > width:
        optional.pop()
        labels = required + optional

    total = sum(screen._display_width(label) for label in labels)
    if total < width:
        free = width - total
        slots = len(labels) + 1
        base_gap, extra = divmod(free, slots)
        gaps = [base_gap + (1 if index < extra else 0) for index in range(slots)]
        parts: list[str] = [bar_space(gaps[0])]
        for index, label in enumerate(labels):
            parts.append(screen._ansi(label, _BUTTON))
            parts.append(bar_space(gaps[index + 1]))
        return "".join(parts)

    compact = (
        ("Tab · " if switch_focus else "")
        + f"↑↓←→ · Enter {enter} · Esc {escape}"
    )
    for hint in command_hints:
        candidate = compact + f" · {hint}"
        if screen._display_width(candidate) > width:
            break
        compact = candidate
    return screen._ansi(screen._clip_cells(compact, width), _BAR_SURFACE)
