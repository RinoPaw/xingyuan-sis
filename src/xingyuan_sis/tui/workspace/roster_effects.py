"""Student roster animations driven by committed create/delete mutations."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from itertools import chain
import os

from .. import animation, screen
from ..effects.effect_burn import Burn
from ..effects.effect_print import Print
from .data import Catalog
from .roster import roster_row_body
from .state import FocusArea, Workspace

_EFFECTS = {"print": Print, "burn": Burn}
_BURN_SPACE = "\u00a0"


@dataclass(frozen=True)
class RosterEffectSnapshot:
    """Visual state required to animate one roster mutation."""

    kind: str
    lines: tuple[str, ...]
    x: int
    y: int
    width: int
    text: str


def _effect(kind: str, text: str):
    """Create one locally ported TTE effect with roster-specific input/config."""
    try:
        effect_cls = _EFFECTS[kind]
    except KeyError as exc:
        raise ValueError(f"unknown roster effect: {kind}") from exc

    # Burn's upstream algorithm skips plain ASCII spaces. NBSP occupies the same
    # terminal cell but remains a real input character, so the random spanning
    # tree can propagate through every cell of the fixed-width roster row.
    effect = effect_cls(text.replace(" ", _BURN_SPACE) if kind == "burn" else text)
    terminal = effect.terminal_config
    terminal.ignore_terminal_dimensions = True
    terminal.frame_rate = 0
    terminal.no_color = os.environ.get("NO_COLOR") is not None

    if kind == "print":
        # Print is designed for whole documents; a roster mutation is one row.
        effect.effect_config.print_speed = 4

    return effect


def _burn_frames(effect: Burn):
    """Project upstream Burn onto delete semantics without changing its burn algorithm."""
    iterator = iter(effect)
    source_chars = tuple(iterator.algo.char_link_order)
    burning = set()
    burned = set()

    for _ in iterator:
        for char in source_chars:
            scene = char.animation.active_scene
            if scene is not None and scene.scene_id == "burn":
                burning.add(char)
            elif char in burning and char not in burned:
                # Upstream Burn restores the original symbol after the burn scene.
                # A successful delete has no final symbol, so hide it at exactly
                # that state transition instead of letting the source text return.
                iterator.terminal.set_character_visibility(char, is_visible=False)
                burned.add(char)

        yield iterator.terminal.get_formatted_output_string()
        if len(burned) == len(source_chars):
            # Do not wait through the upstream final-color/smoke tail: the deleted
            # roster record has already finished its only meaningful transition.
            break


def _frames(kind: str, text: str):
    """Yield effect frames through the mutation semantics owned by this module."""
    effect = _effect(kind, text)
    if kind == "burn":
        yield from _burn_frames(effect)
    else:
        yield from effect


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

    before = ("",) if effect.kind == "print" else ()
    after = () if effect.kind == "print" else ("",)
    frames = chain(before, _frames(effect.kind, effect.text), after)
    animation.play_region_frames(effect.lines, effect.x, effect.y, effect.width, frames)
