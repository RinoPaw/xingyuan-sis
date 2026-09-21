"""Student roster animations driven by committed create/delete mutations.

The local print/burn progression is adapted from TerminalTextEffects 0.15's
Print and Burn effects for a single fixed roster row. See THIRD_PARTY_NOTICES.md.
"""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from itertools import chain

from .. import animation, screen
from .data import Catalog
from .roster import roster_row_body
from .state import FocusArea, Workspace

_PRINT_STEP = 3
_BURN_SPREAD_CELLS = 3
_BURN_STAGES = (
    ("original", screen._DECORATIVE_GOLD),
    ("*", screen._TEXT_DANGER),
    ("·", screen._DECORATIVE_GOLD),
    ("'", screen._TEXT_SECONDARY),
)


@dataclass(frozen=True)
class RosterEffectSnapshot:
    """Visual state required to animate one roster mutation."""

    kind: str
    lines: tuple[str, ...]
    x: int
    y: int
    width: int
    text: str


@dataclass(frozen=True)
class _Glyph:
    symbol: str
    column: int
    width: int


def _glyphs(text: str, width: int) -> tuple[_Glyph, ...]:
    """Split text into fixed terminal cells without breaking wide glyphs."""
    glyphs: list[_Glyph] = []
    column = 0
    for symbol in text:
        symbol_width = max(1, screen._display_width(symbol))
        if column + symbol_width > width:
            break
        glyphs.append(_Glyph(symbol, column, symbol_width))
        column += symbol_width
    return tuple(glyphs)


def _styled(symbol: str, style: str | None) -> str:
    return screen._ansi(symbol, style) if style else symbol


def _render_glyphs(
    glyphs: tuple[_Glyph, ...],
    width: int,
    appearance,
) -> str:
    """Render transformed glyphs while preserving their original cell geometry."""
    chunks: list[str] = []
    cursor = 0
    for index, glyph in enumerate(glyphs):
        if glyph.column > cursor:
            chunks.append(" " * (glyph.column - cursor))

        symbol, style = appearance(index, glyph)
        symbol = screen._clip_cells(symbol, glyph.width)
        shown_width = screen._display_width(symbol)
        chunks.append(_styled(symbol, style))
        if shown_width < glyph.width:
            chunks.append(" " * (glyph.width - shown_width))
        cursor = glyph.column + glyph.width

    if cursor < width:
        chunks.append(" " * (width - cursor))
    return "".join(chunks)


def _print_frames(text: str, width: int):
    """Reveal one roster row with a light print-head sweep.

    The original TTE Print effect types characters in order behind a print head.
    A roster row does not need carriage-return or block-head machinery, so this
    adaptation keeps the ordered reveal and replaces the heavy block animation
    with one thin cursor.
    """
    glyphs = _glyphs(text, width)
    if not glyphs:
        yield " " * width
        return

    for end in range(_PRINT_STEP, len(glyphs) + _PRINT_STEP, _PRINT_STEP):
        end = min(end, len(glyphs))

        def appearance(index: int, glyph: _Glyph) -> tuple[str, str | None]:
            if index < end:
                return glyph.symbol, screen._TEXT_PRIMARY
            return " " * glyph.width, None

        frame = _render_glyphs(glyphs, width, appearance)
        if end < len(glyphs):
            cursor_column = glyphs[end - 1].column + glyphs[end - 1].width
            if cursor_column < width:
                cursor = _styled("▏", screen._TEXT_ACCENT)
                frame = (
                    screen._clip_cells(frame, cursor_column)
                    + cursor
                    + " " * max(0, width - cursor_column - 1)
                )
        yield frame

    yield _render_glyphs(
        glyphs,
        width,
        lambda _index, glyph: (glyph.symbol, screen._TEXT_PRIMARY),
    )


def _burn_ignition_frames(glyphs: tuple[_Glyph, ...]) -> dict[int, int]:
    """Assign a deterministic spreading ignition time to each non-space glyph."""
    burnable = [index for index, glyph in enumerate(glyphs) if not glyph.symbol.isspace()]
    if not burnable:
        return {}

    seed = burnable[len(burnable) // 3]
    seed_column = glyphs[seed].column
    ignition: dict[int, int] = {}
    for index in burnable:
        glyph = glyphs[index]
        distance = abs(glyph.column - seed_column) // _BURN_SPREAD_CELLS
        # Small deterministic jitter keeps the front from looking like a ruler.
        jitter = (glyph.column * 17 + ord(glyph.symbol[0]) * 7) % 3
        ignition[index] = distance + jitter
    return ignition


def _burn_frames(text: str, width: int):
    """Consume one roster row into sparse embers instead of solid block fire."""
    glyphs = _glyphs(text, width)
    ignition = _burn_ignition_frames(glyphs)
    if not ignition:
        yield " " * width
        return

    last_frame = max(ignition.values()) + len(_BURN_STAGES)
    for tick in range(last_frame + 1):

        def appearance(index: int, glyph: _Glyph) -> tuple[str, str | None]:
            if glyph.symbol.isspace():
                return " " * glyph.width, None

            age = tick - ignition[index]
            if age < 0:
                return glyph.symbol, screen._TEXT_PRIMARY
            if age >= len(_BURN_STAGES):
                return " " * glyph.width, None

            symbol, style = _BURN_STAGES[age]
            if symbol == "original":
                symbol = glyph.symbol
            return symbol, style

        yield _render_glyphs(glyphs, width, appearance)


def _frames(kind: str, text: str, width: int):
    if kind == "print":
        yield from _print_frames(text, width)
    elif kind == "burn":
        yield from _burn_frames(text, width)
    else:
        raise ValueError(f"unknown roster effect: {kind}")


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
