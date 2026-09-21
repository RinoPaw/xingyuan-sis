"""Student roster animations driven by committed create/delete mutations."""
from __future__ import annotations

from collections.abc import Iterator
from copy import copy
from dataclasses import dataclass
from itertools import chain
import os

from .. import animation, screen
from .data import Catalog
from .roster import roster_row_body
from .state import FocusArea, Workspace

_BURN_BLANK = "\u00a0"


@dataclass(frozen=True)
class RosterEffectSnapshot:
    """Visual state required to animate one roster mutation."""

    kind: str
    lines: tuple[str, ...]
    x: int
    y: int
    width: int
    text: str


def _one_line(frame: str) -> str:
    return frame.splitlines()[0].replace(_BURN_BLANK, " ")


def _configure_terminal(effect, width: int) -> None:
    """Constrain TTE to the roster row owned by the workspace."""
    effect.terminal_config.canvas_width = width
    effect.terminal_config.canvas_height = 1
    effect.terminal_config.ignore_terminal_dimensions = True
    effect.terminal_config.frame_rate = 0
    effect.terminal_config.no_color = os.environ.get("NO_COLOR") is not None


def _print_frames(text: str, width: int) -> Iterator[str]:
    """Run the official Print showroom configuration."""
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
    """Run TTE Burn with its native random Prim ignition order."""
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
    config.smoke_chance = 0.0
    config.final_gradient_stops = (Color("#00c3ff"), Color("#ffff1c"))
    config.final_gradient_steps = 12
    config.final_gradient_direction = Gradient.Direction.VERTICAL
    _configure_terminal(effect, width)
    yield from effect


def _effect_frames(kind: str, text: str, width: int) -> Iterator[str]:
    if kind == "print":
        yield from _print_frames(text, width)
    elif kind == "burn":
        yield from _burn_frames(text, width)
    else:
        raise ValueError(f"未知名册特效：{kind}")


def _burn_canvas(text: str, width: int) -> str:
    """Represent visually blank roster cells as burnable TTE characters."""
    padded = screen._pad_cells(screen._clip_cells(text, width), width)
    return padded.replace(" ", _BURN_BLANK)


def capture_student_roster_effect(
    state: Workspace,
    catalog: Catalog,
    record_id: int,
    kind: str,
) -> RosterEffectSnapshot | None:
    """Capture the concrete roster row that belongs to one mutation."""
    if state.key != "students":
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
    region = next(item for item in frame.regions if item.action == f"row:{index}")
    body_width = region.width - 2
    body = roster_row_body(preview, catalog, index, body_width)

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


def play_student_roster_effect(effect: RosterEffectSnapshot | None) -> None:
    """Play one captured roster mutation through the shared animation layer."""
    if effect is None:
        return

    if effect.kind == "print":
        frames = chain(
            ("",),
            (_one_line(frame) for frame in _effect_frames("print", effect.text, effect.width)),
        )
    else:
        burn_text = _burn_canvas(effect.text, effect.width)
        frames = chain(
            (effect.text,),
            (_one_line(frame) for frame in _effect_frames("burn", burn_text, effect.width)),
            ("",),
        )

    animation.play_region_frames(
        effect.lines,
        effect.x,
        effect.y,
        effect.width,
        frames,
    )
