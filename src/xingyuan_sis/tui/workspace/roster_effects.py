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
    """Create the locally ported TTE effect without changing its canvas geometry."""
    try:
        effect_cls = _EFFECTS[kind]
    except KeyError as exc:
        raise ValueError(f"unknown roster effect: {kind}") from exc

    effect = effect_cls(text)
    terminal = effect.terminal_config
    # The application owns output timing and placement. Leave TTE's canvas
    # width/height and effect state machine untouched so yielded frames remain
    # the native frames for this exact input.
    terminal.ignore_terminal_dimensions = True
    terminal.frame_rate = 0
    terminal.no_color = os.environ.get("NO_COLOR") is not None
    return effect


def _frames(kind: str, text: str):
    """Yield each complete upstream effect frame without projection or rewriting."""
    yield from _effect(kind, text)


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
    frames = chain(before, _frames(effect.kind, effect.text), after)
    animation.play_region_frames(effect.lines, effect.x, effect.y, effect.width, frames)
