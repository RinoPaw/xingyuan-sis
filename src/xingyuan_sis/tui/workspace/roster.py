from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import screen
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
    """Fit columns to their actual content before truncating any cell."""
    measured: list[list[Any]] = []
    for key, label, preferred_size in definitions:
        label_width = screen._display_width(label)
        natural_width = max(
            [label_width, *(screen._display_width(safe(row.get(key))) for row in rows)]
        )
        preferred_width = min(natural_width, max(label_width, preferred_size))
        measured.append([key, label, preferred_width, natural_width])

    columns: list[list[Any]] = []
    used = 0
    for key, label, preferred_width, natural_width in measured:
        separator = 1 if columns else 0
        if used + separator + preferred_width > available:
            if not columns:
                columns.append([key, label, max(1, available), natural_width])
            break
        columns.append([key, label, preferred_width, natural_width])
        used += separator + preferred_width

    remaining = max(0, available - used)
    while remaining and any(column[2] < column[3] for column in columns):
        for column in columns:
            if column[2] >= column[3]:
                continue
            column[2] += 1
            remaining -= 1
            if remaining == 0:
                break

    return [[key, label, size] for key, label, size, _ in columns]


def render_roster(board: Board, state: Workspace, catalog: Catalog, width: int) -> None:
    rows = state.rows(catalog)
    focused = state.focus is FocusArea.ROSTER and state.form is None
    layout = WorkspaceLayout(board.width, board.height)
    heading_row = layout.panel_heading_row(state.key)
    header_row = layout.panel_content_row(state.key)
    data_row = header_row + 1
    capacity = layout.panel_capacity(state.key)
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
        text = " ".join(
            screen._pad_cells(screen._clip_cells(safe(row.get(key)), size), size)
            for key, _, size in columns
        )
        marker = ("▌ " if focused else "▏ ") if index == state.selected else "  "
        text = screen._pad_cells(screen._clip_cells(marker + text, width - 1), width - 1)
        if index == state.selected:
            selected_style = (
                screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
                if focused
                else screen._SURFACE_INTERACTIVE + screen._TEXT_PRIMARY
            )
        else:
            selected_style = screen._TEXT_PRIMARY
        board.put(1, data_row + index - first, text, selected_style, f"row:{index}", width - 1)

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
