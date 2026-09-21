"""Student roster animations driven by committed create/delete mutations."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from itertools import chain
import os

from terminaltexteffects.effects.effect_burn import Burn
from terminaltexteffects.effects.effect_print import Print
from terminaltexteffects.utils import colorterm

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
    source = screen._TEXT_PRIMARY + text + screen._RESET if kind == "burn" else text
    effect = _EFFECTS[kind](source)
    terminal = effect.terminal_config
    terminal.canvas_width = width
    terminal.canvas_height = 1
    terminal.ignore_terminal_dimensions = True
    terminal.frame_rate = 0
    terminal.no_color = os.environ.get("NO_COLOR") is not None

    if kind == "burn":
        # Input color makes real spaces part of TTE's graph. Their visual
        # adaptation happens after TTE advances the official Burn scene.
        terminal.existing_color_handling = "dynamic"
        effect.effect_config.smoke_chance = 0.0

    return effect


def _burn_frame(iterator, width: int) -> str:
    """Project TTE's Burn state onto a roster-row surface.

    Text cells use the official Burn glyph verbatim. Originally blank cells
    remain blank and expose TTE's fire color as background only while their
    official ``burn`` scene is active.
    """
    chunks: list[str] = []
    cursor = 1
    for character in sorted(iterator.terminal.get_characters(), key=lambda item: item.input_coord.column):
        column = character.input_coord.column
        if column > cursor:
            chunks.append(" " * (column - cursor))

        visual = character.animation.current_character_visual
        input_width = max(1, screen._display_width(character.input_symbol))
        if character.input_symbol == " ":
            scene = character.animation.active_scene
            color = visual._fg_color_code if scene is not None and scene.scene_id == "burn" else None
            shown = f"{colorterm.bg(color)} {screen._RESET}" if color is not None else " "
            shown_width = 1
        else:
            shown = visual.formatted_symbol
            shown_width = screen._display_width(visual.symbol)

        chunks.append(shown)
        if shown_width < input_width:
            chunks.append(" " * (input_width - shown_width))
        cursor = column + input_width

    if cursor <= width:
        chunks.append(" " * (width - cursor + 1))
    return "".join(chunks)


def _frames(kind: str, text: str, width: int):
    effect = _effect(kind, text, width)
    if kind == "print":
        yield from (_one_line(frame) for frame in effect)
        return

    iterator = iter(effect)
    for _ in iterator:
        yield _burn_frame(iterator, width)


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
    frames = chain(before, _frames(effect.kind, effect.text, effect.width), after)
    animation.play_region_frames(effect.lines, effect.x, effect.y, effect.width, frames)
