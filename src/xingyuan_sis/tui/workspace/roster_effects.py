"""Student roster animations driven by committed create/delete mutations."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from itertools import chain
import os

from terminaltexteffects.effects.effect_burn import Burn
from terminaltexteffects.effects.effect_print import Print

from .. import animation, screen
from .data import Catalog
from .roster import roster_row_body
from .state import FocusArea, Workspace

_EFFECTS = {"print": Print, "burn": Burn}


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
    return frame.partition("\n")[0]


def _effect(kind: str, text: str, width: int):
    """Create the official TTE effect constrained to one roster row."""
    if kind == "burn":
        # Burn deliberately treats ANSI-colored spaces as burnable input. Keep
        # the row visually blank in those cells while using TTE's own supported
        # existing-color path instead of substituting fake characters.
        text = screen._TEXT_PRIMARY + text + screen._RESET

    effect = _EFFECTS[kind](text)
    terminal = effect.terminal_config
    terminal.canvas_width = width
    terminal.canvas_height = 1
    terminal.ignore_terminal_dimensions = True
    terminal.frame_rate = 0
    terminal.no_color = os.environ.get("NO_COLOR") is not None

    if kind == "burn":
        terminal.existing_color_handling = "dynamic"
        effect.effect_config.smoke_chance = 0.0

    return effect


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
        x, width, text = region.x + 2, body_width, body.rstrip()
    else:
        x, width = region.x, region.width
        text = screen._pad_cells(screen._clip_cells("  " + body, width), width)

    return RosterEffectSnapshot(kind, tuple(frame.lines), x, region.y, width, text)


def play_student_roster_effect(effect: RosterEffectSnapshot | None) -> None:
    """Play one captured roster mutation through the shared animation layer."""
    if effect is None:
        return

    before = ("",) if effect.kind == "print" else (effect.text,)
    after = () if effect.kind == "print" else ("",)
    frames = chain(
        before,
        (_one_line(frame) for frame in _effect(effect.kind, effect.text, effect.width)),
        after,
    )
    animation.play_region_frames(effect.lines, effect.x, effect.y, effect.width, frames)
