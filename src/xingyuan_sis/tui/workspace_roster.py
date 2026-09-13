from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import screen
from .layout import visible_start
from .view_common import Board, panel_heading, safe
from .workspace_data import COLLECTIONS, Catalog

if TYPE_CHECKING:
    from .workspace import Workspace


def roster_window(state: Workspace, row_count: int, capacity: int) -> int:
    state.roster_scroll = visible_start(state.selected, row_count, capacity, state.roster_scroll)
    return state.roster_scroll


def render_roster(board: Board, state: Workspace, catalog: Catalog, width: int) -> None:
    rows = state.rows(catalog)
    focused = not state.details and not state.action_focus and state.form is None
    capacity = max(1, board.height - 12)
    first = roster_window(state, len(rows), capacity)
    heading = panel_heading("名册", focused)
    range_text = f"  {len(rows):02d}" + (
        f"  /  {first + 1}–{min(first + capacity, len(rows))}" if rows else ""
    )
    board.put(1, 8, heading + screen._ansi(range_text, screen._TEXT_SECONDARY), width=width - 1)

    definitions = COLLECTIONS[state.key].columns
    available = max(1, width - 4)
    columns: list[list[Any]] = []
    remaining = available
    for key, label, base_size in definitions:
        size = min(base_size, remaining) if not columns else base_size
        if size > remaining:
            break
        columns.append([key, label, size])
        remaining -= size + 1

    if columns and remaining > 0:
        for column in columns:
            key, label, size = column
            desired = max(
                screen._display_width(label),
                *(screen._display_width(safe(row.get(key))) for row in rows),
                size,
            )
            growth = min(max(0, desired - size), remaining)
            column[2] += growth
            remaining -= growth
            if remaining <= 0:
                break

    header = "  " + " ".join(screen._pad_cells(label, size) for _, label, size in columns)
    board.put(1, 9, header, screen._TEXT_SECONDARY, width=width - 1)
    for index, row in enumerate(rows[first:first + capacity], start=first):
        text = " ".join(
            screen._pad_cells(screen._clip_cells(safe(row.get(key)), size), size)
            for key, _, size in columns
        )
        text = screen._pad_cells(screen._clip_cells("  " + text, width - 1), width - 1)
        if index == state.selected:
            selected_style = (
                screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
                if focused
                else screen._SURFACE_INTERACTIVE + screen._TEXT_PRIMARY
            )
        else:
            selected_style = screen._TEXT_PRIMARY
        board.put(1, 10 + index - first, text, selected_style, f"row:{index}", width - 1)

    if not rows:
        board.put(
            1, 11,
            "没有匹配的记录" if state.query or state.view else "名册还是空白的",
            screen._BOLD + screen._TEXT_PRIMARY, width=width - 1,
        )
        if state.query or state.view:
            board.put(1, 13, "清除搜索或切换上方视图。", screen._TEXT_SECONDARY, width=width - 1)
        else:
            board.put(1, 13, "可使用上方“增加”建立第一条记录。", screen._TEXT_SECONDARY, width=width - 1)
            if state.key == "students":
                board.button(1, 15, "导入学生 CSV", "import")
            if not any(catalog.records.values()):
                board.button(1, 17, "体验演示校园", "seed")
