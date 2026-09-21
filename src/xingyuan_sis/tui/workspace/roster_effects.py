"""Transient effects for mutations that enter or leave the student roster."""
from __future__ import annotations

import os
import sys
import time

from .. import screen
from .data import Catalog
from .roster import roster_row_body
from .state import FocusArea, Workspace

_FRAME_INTERVAL = 1 / 30
_MAX_FRAMES = {"print": 30, "burn": 36}


def _one_line(frame: str) -> str:
    lines = frame.splitlines()
    return lines[0] if lines else ""


def _sample(frames: list[str], limit: int) -> list[str]:
    if len(frames) <= limit:
        return frames
    if limit <= 1:
        return [frames[-1]]
    last = len(frames) - 1
    indexes = [round(index * last / (limit - 1)) for index in range(limit)]
    return [frames[index] for index in indexes]


def _frames(kind: str, text: str) -> list[str]:
    """Generate TTE frames without letting the library own the terminal."""
    if kind == "print":
        from terminaltexteffects.effects.effect_print import Print

        effect = Print(text)
    elif kind == "burn":
        from terminaltexteffects.effects.effect_burn import Burn

        effect = Burn(text)
    else:
        raise ValueError(f"未知名册特效：{kind}")

    # The effect is embedded into one existing roster row, so TTE must only
    # produce the row canvas. Xingyuan keeps ownership of the surrounding TUI.
    effect.terminal_config.canvas_width = -1
    effect.terminal_config.canvas_height = 1
    effect.terminal_config.ignore_terminal_dimensions = True
    effect.terminal_config.frame_rate = 0
    return _sample(list(effect), _MAX_FRAMES[kind])


def _draw_body(x: int, y: int, width: int, raw: str) -> None:
    color_enabled = os.environ.get("NO_COLOR") is None
    surface = (screen._SURFACE_DEFAULT + screen._TEXT_PRIMARY) if color_enabled else ""
    shown = screen._clip_cells(_one_line(raw), width)
    if not color_enabled:
        shown = screen._ANSI_RE.sub("", shown)
    remaining = max(0, width - screen._display_width(shown))
    sys.stdout.write(
        f"\x1b[{y};{x}H"
        + screen._RESET
        + surface
        + shown
        + screen._RESET
        + surface
        + " " * remaining
    )
    sys.stdout.flush()


def play_student_roster_effect(
    state: Workspace,
    catalog: Catalog,
    record_id: int,
    kind: str,
) -> bool:
    """Focus and animate exactly one student row in-place.

    ``burn`` is played while the record still exists, immediately before the
    deletion transaction is applied. ``print`` is played after creation, once
    the new record has reached its sorted/filtered roster position.
    """
    if state.key != "students":
        return False

    rows = state.rows(catalog)
    index = next((i for i, row in enumerate(rows) if row["id"] == record_id), None)
    if index is None:
        return False

    state.selected = index
    state.set_focus(FocusArea.ROSTER)
    state.detail_scroll = 0
    state.detail_selected = 0

    # Tests, redirected output and non-interactive callers still get the focus
    # transition; only a real terminal receives animation frames.
    if not sys.stdout.isatty():
        return False

    from .view import render

    # A confirmed delete no longer needs to keep its confirmation panel on
    # screen. Temporarily detach it while measuring/painting the roster so the
    # same Burn behavior works in both split and compact layouts. The Form is
    # restored before returning because apply_form still owns the transaction.
    form = state.form
    if kind == "burn":
        state.form = None
    try:
        frame = render(state, catalog)
    finally:
        state.form = form

    region = next((item for item in frame.regions if item.action == f"row:{index}"), None)
    if region is None or region.width <= 2:
        return False

    body_width = region.width - 2
    text = roster_row_body(state, catalog, index, body_width).rstrip()
    if not text:
        return False

    try:
        frames = _frames(kind, text)
    except Exception:
        # Effects are decorative; a missing/incompatible runtime must never
        # prevent a confirmed data mutation from completing.
        return False

    x = region.x + 2  # keep the focused ``> `` marker stationary
    y = region.y
    try:
        # Paint the focus transition only after frame generation, so a newly
        # created row cannot sit fully visible while Print prepares its frames.
        screen._paint(frame.lines)
        if kind == "print":
            _draw_body(x, y, body_width, "")
        for raw in frames:
            _draw_body(x, y, body_width, raw)
            time.sleep(_FRAME_INTERVAL)
    except Exception:
        return False

    return True
