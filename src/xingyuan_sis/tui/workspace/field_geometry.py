from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from .. import screen


FIELD_GUTTER = 2
CONTROL_MIN_WIDTH = 10
_CONTROL_MAX_WIDTH = 28
_CONTROL_PADDING = 1
_LABEL_VALUE_GAP = 2


class FieldLike(Protocol):
    label: str
    required: bool


@dataclass(frozen=True)
class FormFieldGeometry:
    """Content-driven geometry for one-column transaction forms."""

    stacked: bool
    label_width: int
    marker_offset: int
    control_offset: int
    control_available: int
    row_height: int


def field_label_width(field: FieldLike) -> int:
    """Return the exact terminal width needed by a label and its required marker."""
    return screen._display_width(field.label) + (2 if field.required else 0)


def form_field_geometry(fields: Iterable[FieldLike], available: int) -> FormFieldGeometry:
    """Measure the form before placing it; labels are never sacrificed to guessed ratios.

    Inline layout is used when the complete longest label, the focus gutter and a
    useful control all fit. Otherwise the field becomes a two-row stack: label on
    the first row and marker/control on the second.
    """
    available = max(1, available)
    fields = tuple(fields)
    natural_label_width = max((field_label_width(field) for field in fields), default=0)
    inline_control_offset = natural_label_width + _LABEL_VALUE_GAP + FIELD_GUTTER
    inline_control_available = available - inline_control_offset

    if inline_control_available >= CONTROL_MIN_WIDTH:
        return FormFieldGeometry(
            stacked=False,
            label_width=natural_label_width,
            marker_offset=natural_label_width + _LABEL_VALUE_GAP,
            control_offset=inline_control_offset,
            control_available=inline_control_available,
            row_height=1,
        )

    # In compact terminals there is still enough horizontal room for every
    # normal form label, but not necessarily for label and editor side by side.
    # Keep the label whole and spend the next row on the editor instead of
    # truncating the label with an ellipsis.
    control_offset = FIELD_GUTTER
    return FormFieldGeometry(
        stacked=True,
        label_width=natural_label_width,
        marker_offset=0,
        control_offset=control_offset,
        control_available=max(1, available - control_offset),
        row_height=2,
    )


def control_width(text: str, available: int) -> int:
    """Return a bounded editor width derived from visible terminal-cell content."""
    available = max(1, available)
    content = "" if text in {"", "—"} else text
    natural = screen._display_width(content) + _CONTROL_PADDING * 2
    preferred = min(_CONTROL_MAX_WIDTH, max(CONTROL_MIN_WIDTH, natural))
    return min(available, preferred)


def control_text(text: str, width: int) -> str:
    """Render a field value inside the same balanced box used while editing."""
    width = max(1, width)
    if width <= _CONTROL_PADDING * 2:
        return screen._pad_cells(screen._clip_cells(text, width), width)
    inner = width - _CONTROL_PADDING * 2
    body = screen._pad_cells(screen._clip_cells(text, inner), inner)
    return " " * _CONTROL_PADDING + body + " " * _CONTROL_PADDING
