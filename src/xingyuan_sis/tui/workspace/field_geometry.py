from __future__ import annotations

from .. import screen


FIELD_GUTTER = 2
_CONTROL_MIN_WIDTH = 10
_CONTROL_MAX_WIDTH = 28
_CONTROL_PADDING = 1


def control_width(text: str, available: int) -> int:
    """Return a bounded editor width derived from visible terminal-cell content."""
    available = max(1, available)
    content = "" if text in {"", "—"} else text
    natural = screen._display_width(content) + _CONTROL_PADDING * 2
    preferred = min(_CONTROL_MAX_WIDTH, max(_CONTROL_MIN_WIDTH, natural))
    return min(available, preferred)


def control_text(text: str, width: int) -> str:
    """Render a field value inside the same balanced box used while editing."""
    width = max(1, width)
    if width <= _CONTROL_PADDING * 2:
        return screen._pad_cells(screen._clip_cells(text, width), width)
    inner = width - _CONTROL_PADDING * 2
    body = screen._pad_cells(screen._clip_cells(text, inner), inner)
    return " " * _CONTROL_PADDING + body + " " * _CONTROL_PADDING
