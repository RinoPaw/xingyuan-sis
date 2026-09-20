from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import screen, theme
from ..layout import WorkspaceLayout, visible_start
from ..view_common import Board, panel_heading, safe
from .data import COLLECTIONS, Catalog
from .state import FocusArea

if TYPE_CHECKING:
    from .state import Workspace


def roster_window(state: Workspace, row_count: int, capacity: int) -> int:
    state.roster_scroll = visible_start(state.selected, row_count, capacity, state.roster_scroll)
    return state.roster_scroll


def _fit_columns(
    definitions: tuple[tuple[str, str, int], ...],
    rows: list[dict[str, Any]],
    available: int,
) -> list[list[Any]]:
    """Show only columns whose labels and values can be rendered in full.

    Column order is also priority order. Every visible column gets its exact
    natural terminal-cell width. When the roster is too narrow, lower-priority
    columns disappear as whole columns instead of forcing ellipses into values.
    The historical preferred sizes are deliberately ignored here: empty padding
    must never steal space from real content.
    """
    available = max(1, available)
    measured: list[list[Any]] = []
    for key, label, _preferred_size in definitions:
        width = max(
            [screen._display_width(label), *(screen._display_width(safe(row.get(key))) for row in rows)]
        )
        measured.append([key, label, max(1, width)])

    # Keep adding columns in semantic priority order while every visible value
    # still fits in full. If even the first column is wider than the viewport,
    # give it the viewport and let the board provide the unavoidable hard edge;
    # normal roster columns are expected to be much narrower than this.
    columns: list[list[Any]] = []
    used = 0
    for key, label, natural_width in measured:
        separator = 1 if columns else 0
        needed = separator + natural_width
        if used + needed > available:
            break
        columns.append([key, label, natural_width])
        used += needed

    if not columns and measured:
        key, label, natural_width = measured[0]
        columns.append([key, label, min(natural_width, available)])
    return columns


def render_roster(board: Board, state: Workspace, catalog: Catalog, width: int) -> None:
    rows = state.rows(catalog)
    focused = state.focus is FocusArea.ROSTER and state.form is None
    layout = WorkspaceLayout(board.width, board.height)
    heading_row = layout.panel_heading_row(state.key)
    header_row = layout.panel_content_row(state.key)
    data_row = header_row + 1
    capacity = layout.roster_capacity(state.key)
    first = roster_window(state, len(rows), capacity)
    heading = panel_heading("名册", focused)
    range_text = f"  {len(rows):02d}" + (
        f"  /  {first + 1}–{min(first + capacity, len(rows))}" if rows else ""
    )
    board.put(1, heading_row, heading + screen._ansi(range_text, screen._TEXT_SECONDARY), width=width - 1)

    available = max(1, width - 3)
    columns = _fit_columns(COLLECTIONS[state.key].columns, rows, available)

    header = "  " + " ".join(screen._pad_cells(label, size) for _, label, size in columns)
    board.put(1, header_row, header, screen._TEXT_SECONDARY, width=width - 1)
    for index, row in enumerate(rows[first:first + capacity], start=first):
        raw = " ".join(
            screen._pad_cells(safe(row.get(key)), size)
            for key, _, size in columns
        )
        body_width = max(1, width - 3)
        body = screen._pad_cells(raw, body_width)
        is_current = index == state.selected
        text = theme.contextual_item(
            body,
            selected=is_current and focused,
            current=is_current and not focused,
        )
        board.put(1, data_row + index - first, text, action=f"row:{index}", width=width - 1)

    if not rows:
        message_row = data_row + 1
        board.put(
            1, message_row,
            "没有匹配的记录" if state.query or state.view else "名册还是空白的",
            screen._BOLD + screen._TEXT_PRIMARY, width=width - 1,
        )
        if state.query or state.view:
            board.put(1, message_row + 2, "清除搜索或切换上方视图。", screen._TEXT_SECONDARY, width=width - 1)
        elif catalog.read_only:
            board.put(1, message_row + 2, "暂无可查询记录。", screen._TEXT_SECONDARY, width=width - 1)
        else:
            board.put(1, message_row + 2, "可使用上方“增加”建立第一条记录。", screen._TEXT_SECONDARY, width=width - 1)
            if state.key == "students":
                board.button(1, message_row + 4, "导入学生 CSV", "import")
            if not any(catalog.records.values()):
                board.button(1, message_row + 6, "体验演示校园", "seed")
