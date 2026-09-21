"""Transient roster animations for student create/delete mutations."""
from __future__ import annotations

from collections.abc import Iterator
from copy import copy
from dataclasses import dataclass
import os
import sys
import time

from .. import screen
from .data import Catalog
from .roster import roster_row_body
from .state import FocusArea, Workspace

_FRAME_INTERVAL = 1 / 60
_BURN_BLANK = "\u00a0"


@dataclass(frozen=True)
class RosterEffectSnapshot:
    """One visual row captured around a real student mutation.

    Delete captures before persistence so the disappearing row still exists;
    playback happens only after the delete succeeds. Create captures after the
    record exists. The animation therefore belongs to the mutation, independent
    of whether that mutation was reached by mouse, keyboard shortcut, or Enter.
    """

    kind: str
    lines: tuple[str, ...]
    x: int
    y: int
    width: int
    text: str


def _one_line(frame: str) -> str:
    lines = frame.splitlines()
    return (lines[0] if lines else "").replace(_BURN_BLANK, " ")


def _configure_terminal(effect, width: int) -> None:
    """Let TTE animate one exact roster span while Xingyuan owns the screen."""
    effect.terminal_config.canvas_width = max(1, width)
    effect.terminal_config.canvas_height = 1
    effect.terminal_config.ignore_terminal_dimensions = True
    effect.terminal_config.frame_rate = 0
    effect.terminal_config.no_color = os.environ.get("NO_COLOR") is not None


def _print_frames(text: str, width: int) -> Iterator[str]:
    """Use the official Print showroom example configuration."""
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
    config.print_head_return_speed = 1.5
    config.print_speed = 2
    config.print_head_easing = easing.in_out_quad
    _configure_terminal(effect, width)
    yield from effect


def _burn_frames(text: str, width: int) -> Iterator[str]:
    """Use official TTE Burn with its native random ignition order."""
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
    # Smoke rises outside this one-row roster span and would overwrite adjacent
    # students. Ignition, Prim growth, burn scenes and colors remain TTE's own.
    config.smoke_chance = 0.0
    config.final_gradient_stops = (Color("#00c3ff"), Color("#ffff1c"))
    config.final_gradient_steps = 12
    config.final_gradient_direction = Gradient.Direction.VERTICAL
    _configure_terminal(effect, width)
    yield from effect


def _effect_frames(kind: str, text: str, width: int) -> Iterator[str]:
    """Dispatch to the one supported implementation: TerminalTextEffects."""
    if kind == "print":
        yield from _print_frames(text, width)
    elif kind == "burn":
        yield from _burn_frames(text, width)
    else:
        raise ValueError(f"未知名册特效：{kind}")


def _burn_canvas(text: str, width: int) -> str:
    """Make visually blank terminal cells real Burn graph vertices."""
    padded = screen._pad_cells(screen._clip_cells(text, width), width)
    return padded.replace(" ", _BURN_BLANK)


def _surface() -> str:
    return (screen._SURFACE_DEFAULT + screen._TEXT_PRIMARY) if os.environ.get("NO_COLOR") is None else ""


def _draw_row(x: int, y: int, width: int, raw: str) -> None:
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


def capture_student_roster_effect(
    state: Workspace,
    catalog: Catalog,
    record_id: int,
    kind: str,
) -> RosterEffectSnapshot | None:
    """Capture the target row without mutating the live workspace state."""
    if state.key != "students" or kind not in {"print", "burn"}:
        return None

    rows = state.rows(catalog)
    index = next((i for i, row in enumerate(rows) if row["id"] == record_id), None)
    if index is None:
        return None

    from .view import render

    preview = copy(state)
    preview.form = None
    preview.field_session = None
    preview.select_row(index)
    if kind == "burn":
        preview.set_focus(FocusArea.ROSTER)
        preview.detail_scroll = 0
        preview.detail_selected = 0

    frame = render(preview, catalog)
    region = next((item for item in frame.regions if item.action == f"row:{index}"), None)
    if region is None or region.width <= 2:
        return None

    body_width = region.width - 2
    body = roster_row_body(preview, catalog, index, body_width)
    if not body.strip():
        return None

    if kind == "print":
        return RosterEffectSnapshot(
            kind,
            tuple(frame.lines),
            region.x + 2,
            region.y,
            body_width,
            body.rstrip(),
        )

    return RosterEffectSnapshot(
        kind,
        tuple(frame.lines),
        region.x,
        region.y,
        region.width,
        screen._pad_cells(screen._clip_cells("  " + body, region.width), region.width),
    )


def play_student_roster_effect(effect: RosterEffectSnapshot | None) -> bool:
    """Play the captured mutation effect through TerminalTextEffects only."""
    if effect is None or not sys.stdout.isatty():
        return False

    try:
        screen._paint(effect.lines)
        if effect.kind == "print":
            _draw_row(effect.x, effect.y, effect.width, "")
            text = effect.text
        else:
            # Remove the selection marker before ignition; the deleted record is
            # already no longer current from the workspace's point of view.
            _draw_row(effect.x, effect.y, effect.width, effect.text)
            text = _burn_canvas(effect.text, effect.width)

        for raw in _effect_frames(effect.kind, text, effect.width):
            _draw_row(effect.x, effect.y, effect.width, raw)
            time.sleep(_FRAME_INTERVAL)

        if effect.kind == "burn":
            _draw_row(effect.x, effect.y, effect.width, "")
        return True
    except Exception:
        # A failed decorative effect never gets a second implementation path and
        # never rolls back an already-successful data mutation.
        return False
