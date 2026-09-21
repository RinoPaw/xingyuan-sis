"""Transient effects for mutations that enter or leave the student roster."""
from __future__ import annotations

from collections.abc import Iterator
import os
import random
import sys
import time

from .. import screen
from .data import Catalog
from .roster import roster_row_body
from .state import FocusArea, Workspace

_FRAME_INTERVAL = 1 / 60


def _one_line(frame: str) -> str:
    """Extract the single-row canvas embedded into the roster."""
    lines = frame.splitlines()
    return lines[0] if lines else ""


def _tte_frames(kind: str, text: str) -> Iterator[str]:
    """Yield the real TerminalTextEffects animation without owning the terminal."""
    if kind == "print":
        from terminaltexteffects.effects.effect_print import Print

        effect = Print(text)
        # One character per animation step keeps a single roster row visibly
        # printable without turning a short name into an instant flash.
        effect.effect_config.print_speed = 1
    elif kind == "burn":
        from terminaltexteffects.effects.effect_burn import Burn

        effect = Burn(text)
        # Smoke needs vertical canvas space. The embedded roster effect owns one
        # row, so keep the actual ignition/burn sequence and suppress clipped
        # particles rather than letting them overwrite neighboring students.
        effect.effect_config.smoke_chance = 0.0
    else:
        raise ValueError(f"未知名册特效：{kind}")

    effect.terminal_config.canvas_width = -1
    effect.terminal_config.canvas_height = 1
    effect.terminal_config.ignore_terminal_dimensions = True
    effect.terminal_config.frame_rate = 0
    effect.terminal_config.no_color = os.environ.get("NO_COLOR") is not None
    yield from effect


def _print_fallback_frames(text: str) -> Iterator[str]:
    """Small dependency-free Print fallback for an already-running old venv."""
    chars = list(text)
    for index, char in enumerate(chars):
        head_width = max(1, screen._display_width(char))
        yield "".join(chars[:index]) + "█" * head_width
    yield text


def _burn_fallback_frames(text: str) -> Iterator[str]:
    """Dependency-free row-local burn used only when TTE is unavailable."""
    chars = list(text)
    burnable = [index for index, char in enumerate(chars) if not char.isspace()]
    if not burnable:
        yield ""
        return

    # Stable but irregular ignition order; each character progresses through a
    # flame-like glyph/color sequence before disappearing.
    seed = sum((index + 1) * ord(char) for index, char in enumerate(chars))
    random.Random(seed).shuffle(burnable)
    ignition = {index: order for order, index in enumerate(burnable)}
    symbols = ("█", "▓", "▒", "░", "·")
    colors = (
        "\x1b[38;5;255m",
        "\x1b[38;5;226m",
        "\x1b[38;5;208m",
        "\x1b[38;5;196m",
        "\x1b[38;5;88m",
    )
    color_enabled = os.environ.get("NO_COLOR") is None

    for frame_index in range(len(burnable) + len(symbols) + 1):
        parts: list[str] = []
        for index, char in enumerate(chars):
            order = ignition.get(index)
            if order is None:
                parts.append(char)
                continue
            stage = frame_index - order
            if stage < 0:
                if color_enabled:
                    parts.append(screen._TEXT_PRIMARY)
                parts.append(char)
            elif stage < len(symbols):
                if color_enabled:
                    parts.append(colors[stage])
                parts.append(symbols[stage] * max(1, screen._display_width(char)))
            else:
                parts.append(" " * max(1, screen._display_width(char)))
        yield "".join(parts)


def _frames(kind: str, text: str) -> Iterator[str]:
    """Prefer TTE itself, but never silently lose the requested animation."""
    try:
        yield from _tte_frames(kind, text)
        return
    except Exception:
        # A source checkout can still be running inside a venv created before
        # terminaltexteffects became a project dependency. The mutation must
        # remain usable and visibly animated in that state.
        pass

    if kind == "print":
        yield from _print_fallback_frames(text)
    elif kind == "burn":
        yield from _burn_fallback_frames(text)
    else:
        raise ValueError(f"未知名册特效：{kind}")


def _surface() -> str:
    return (screen._SURFACE_DEFAULT + screen._TEXT_PRIMARY) if os.environ.get("NO_COLOR") is None else ""


def _draw_body(x: int, y: int, width: int, raw: str) -> None:
    """Replace only the body cells of one roster row."""
    surface = _surface()
    shown = screen._clip_cells(_one_line(raw), width)
    if os.environ.get("NO_COLOR") is not None:
        shown = screen._ANSI_RE.sub("", shown)
    elif surface:
        # TTE frames contain resets of their own. Reapply Xingyuan's page
        # surface after each one so the animated row never punches holes in the
        # TUI background.
        shown = shown.replace(screen._RESET, screen._RESET + surface)
    remaining = max(0, width - screen._display_width(shown))
    sys.stdout.write(
        f"\x1b[{y};{x}H"
        + screen._RESET
        + surface
        + shown
        + " " * remaining
        + screen._RESET
        + surface
    )
    sys.stdout.flush()


def _clear_roster_marker(x: int, y: int) -> None:
    """A confirmed delete immediately stops presenting the record as selected."""
    surface = _surface()
    sys.stdout.write(
        f"\x1b[{y};{x}H"
        + screen._RESET
        + surface
        + "  "
        + screen._RESET
        + surface
    )
    sys.stdout.flush()


def play_student_roster_effect(
    state: Workspace,
    catalog: Catalog,
    record_id: int,
    kind: str,
) -> bool:
    """Animate exactly one student row while preserving the owning panel's focus.

    ``print`` runs after a create commit and leaves the inspector focused while
    the new weak-context row appears at its actual sorted position. ``burn``
    runs before the delete commit; focus moves to the roster, its record marker
    disappears immediately, and the row burns away before becoming a gap.
    """
    if state.key != "students":
        return False

    rows = state.rows(catalog)
    index = next((i for i, row in enumerate(rows) if row["id"] == record_id), None)
    if index is None:
        return False

    state.select_row(index)
    if kind == "burn":
        state.set_focus(FocusArea.ROSTER)
        state.detail_scroll = 0
        state.detail_selected = 0

    if not sys.stdout.isatty():
        return False

    from .view import render

    # The delete confirmation panel is no longer the visible owner after the
    # user confirms it. Temporarily detach the Form while measuring the normal
    # split roster; apply_form still receives the same Form afterwards.
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

    body_x = region.x + 2  # HitRegion coordinates are already terminal/1-based.
    y = region.y
    try:
        screen._paint(frame.lines)
        if kind == "print":
            # The new row exists in layout immediately, but its body starts
            # blank and is introduced by Print while the inspector keeps focus.
            _draw_body(body_x, y, body_width, "")
        else:
            # Deletion focus belongs to the empty slot, not to the record that
            # is about to disappear. Burn only the record body itself.
            _clear_roster_marker(region.x, y)

        for raw in _frames(kind, text):
            _draw_body(body_x, y, body_width, raw)
            time.sleep(_FRAME_INTERVAL)

        if kind == "burn":
            _draw_body(body_x, y, body_width, "")
        else:
            _draw_body(body_x, y, body_width, text)
    except Exception:
        # Effects are decoration; never strand a confirmed save/delete because
        # a terminal rejects cursor movement or a third-party effect changes.
        if kind == "print":
            try:
                _draw_body(body_x, y, body_width, text)
            except Exception:
                pass
        return False

    return True
