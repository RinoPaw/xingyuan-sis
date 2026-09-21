"""Transient TerminalTextEffects animations for student roster mutations."""
from __future__ import annotations

from collections.abc import Iterator
import os
import sys
import time

from .. import screen
from .data import Catalog
from .roster import roster_row_body
from .state import FocusArea, Workspace

_FRAME_INTERVAL = 1 / 60
_BURN_BLANK = "\u00a0"


def _one_line(frame: str) -> str:
    """Extract the embedded one-row canvas and restore invisible burn blanks."""
    lines = frame.splitlines()
    return (lines[0] if lines else "").replace(_BURN_BLANK, " ")


def _configure_terminal(effect) -> None:
    """Keep TTE responsible for the effect while Xingyuan owns the screen."""
    effect.terminal_config.canvas_width = -1
    effect.terminal_config.canvas_height = 1
    effect.terminal_config.ignore_terminal_dimensions = True
    effect.terminal_config.frame_rate = 0
    effect.terminal_config.no_color = os.environ.get("NO_COLOR") is not None


def _print_frames(text: str) -> Iterator[str]:
    """Use the Print showroom configuration verbatim."""
    from terminaltexteffects import Color, Gradient, easing
    from terminaltexteffects.effects.effect_print import Print

    effect = Print(text)
    config = effect.effect_config
    config.final_gradient_stops = (
        Color("#02b8bd"),
        Color("#c1f0e3"),
        Color("#00ffa0"),
    )
    config.final_gradient_steps = 12
    config.final_gradient_direction = Gradient.Direction.DIAGONAL
    config.print_head_return_speed = 1.25
    config.print_speed = 1
    config.print_head_easing = easing.in_out_quad
    _configure_terminal(effect)
    yield from effect


def _burn_frames(text: str) -> Iterator[str]:
    """Use TTE Burn, but ignite the complete roster row from its centre."""
    from terminaltexteffects import Color, Gradient
    from terminaltexteffects.effects.effect_burn import Burn

    effect = Burn(text)
    config = effect.effect_config
    config.starting_color = Color("#837373")
    config.burn_colors = (
        Color("#ffffff"),
        Color("#fff75d"),
        Color("#fe650d"),
        Color("#8a003c"),
        Color("#510100"),
    )
    # The showroom example uses smoke=0.2. Smoke rises into adjacent terminal
    # rows, which would overwrite neighbouring students, so the embedded
    # one-row version intentionally keeps only the official ignition/burn.
    config.smoke_chance = 0.0
    config.final_gradient_stops = (Color("#00c3ff"), Color("#ffff1c"))
    config.final_gradient_steps = 12
    config.final_gradient_direction = Gradient.Direction.VERTICAL
    _configure_terminal(effect)

    iterator = iter(effect)
    # Burn's stock Prim tree chooses a random origin. Reorder the already-built
    # official ignition sequence by terminal-cell distance from the row centre,
    # so the same Burn scenes spread outwards from the middle in both directions.
    centre = (iterator.terminal.canvas.text_left + iterator.terminal.canvas.text_right) / 2
    iterator.algo.char_link_order.sort(
        key=lambda character: abs(character.input_coord.column - centre)
    )
    yield from iterator


def _frames(kind: str, text: str) -> Iterator[str]:
    if kind == "print":
        yield from _print_frames(text)
    elif kind == "burn":
        yield from _burn_frames(text)
    else:
        raise ValueError(f"未知名册特效：{kind}")


def _burn_canvas(text: str, width: int) -> str:
    """Make every terminal cell burnable, including visually blank cells."""
    padded = screen._pad_cells(screen._clip_cells(text, width), width)
    return padded.replace(" ", _BURN_BLANK)


def _surface() -> str:
    return (screen._SURFACE_DEFAULT + screen._TEXT_PRIMARY) if os.environ.get("NO_COLOR") is None else ""


def _draw_row(x: int, y: int, width: int, raw: str) -> None:
    """Replace exactly one roster-row span without disturbing neighbouring rows."""
    surface = _surface()
    shown = screen._clip_cells(_one_line(raw), width)
    if os.environ.get("NO_COLOR") is not None:
        shown = screen._ANSI_RE.sub("", shown)
    elif surface:
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


def play_student_roster_effect(
    state: Workspace,
    catalog: Catalog,
    record_id: int,
    kind: str,
) -> bool:
    """Animate one student entry using TTE while preserving workspace semantics."""
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
    body = roster_row_body(state, catalog, index, body_width)
    if not body.strip():
        return False

    body_x = region.x + 2
    y = region.y
    try:
        screen._paint(frame.lines)
        if kind == "print":
            text = body.rstrip()
            _draw_row(body_x, y, body_width, "")
            for raw in _frames("print", text):
                _draw_row(body_x, y, body_width, raw)
                time.sleep(_FRAME_INTERVAL)
            # Let the normal renderer restore canonical weak-context styling on
            # the next interaction frame; the animation itself keeps TTE color.
            return True

        # Burn owns the complete rendered student row, marker gutter included.
        # Spaces become NBSP only inside TTE so every cell participates while
        # remaining visually blank until its flame scene reaches that cell.
        text = _burn_canvas("  " + body, region.width)
        _draw_row(region.x, y, region.width, _BURN_BLANK * region.width)
        for raw in _frames("burn", text):
            _draw_row(region.x, y, region.width, raw)
            time.sleep(_FRAME_INTERVAL)
        _draw_row(region.x, y, region.width, "")
        return True
    except Exception:
        # Animation is decorative and must never prevent the confirmed mutation.
        if kind == "print":
            try:
                _draw_row(body_x, y, body_width, body.rstrip())
            except Exception:
                pass
        return False
