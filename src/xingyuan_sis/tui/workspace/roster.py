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
    """Allocate roster width from real content before truncating any value.

    Preferred sizes are shrink targets, not reserved padding. A column whose
    real content is shorter than its preferred size never wastes cells that a
    longer column could use. When the natural table is genuinely too wide,
    columns with content beyond their preferred size give up that excess first.
    Compact columns therefore stay intact while long text such as names or class
    labels may eventually receive an ellipsis.
    """
    available = max(1, available)
    columns: list[list[Any]] = []
    for key, label, preferred_size in definitions:
        label_width = screen._display_width(label)
        natural_width = max(
            [label_width, *(screen._display_width(safe(row.get(key))) for row in rows)]
        )
        shrink_target = max(label_width, min(natural_width, preferred_size))
        columns.append([key, label, natural_width, shrink_target])

    if not columns:
        return []

    separators = len(columns) - 1
    usable = max(1, available - separators)
    widths = [column[2] for column in columns]
    shortage = max(0, sum(widths) - usable)

    # First reclaim only genuinely flexible width: values that are wider than
    # their preferred size. Columns already shorter than their preferred size
    # do not reserve invisible padding and therefore never need "compression".
    while shortage:
        candidates = [
            index
            for index, column in enumerate(columns)
            if widths[index] > column[3]
        ]
        if not candidates:
            break
        # Take one cell from the column with the most remaining excess. This
        # avoids arbitrarily sacrificing the first column when several long
        # text columns are present.
        index = max(candidates, key=lambda item: widths[item] - columns[item][3])
        widths[index] -= 1
        shortage -= 1

    # Extremely narrow terminals can still be smaller than the sum of all
    # preferred targets. Keep every column present and spend the remaining loss
    # on columns that can still shrink without clipping their heading. The
    # board will provide the unavoidable hard edge only if even headings do not
    # fit, which should occur only in compact layouts.
    while shortage:
        candidates = [
            index
            for index, column in enumerate(columns)
            if widths[index] > screen._display_width(column[1])
        ]
        if not candidates:
            break
        index = max(candidates, key=lambda item: widths[item] - screen._display_width(columns[item][1]))
        widths[index] -= 1
        shortage -= 1

    return [
        [key, label, max(1, width)]
        for (key, label, _natural, _target), width in zip(columns, widths)
    ]


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
            screen._pad_cells(screen._clip_cells(safe(row.get(key)), size), size)
            for key, _, size in columns
        )
        body_width = max(1, width - 3)
        body = screen._pad_cells(screen._clip_cells(raw, body_width), body_width)
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
