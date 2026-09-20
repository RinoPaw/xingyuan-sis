"""Shared record-field geometry, rendering, hit targets and navigation."""
from __future__ import annotations

from typing import Any

from .. import screen, theme
from ..layout import WorkspaceLayout, visible_start
from ..view_common import Board, identity, panel_heading, safe
from .data import Catalog
from .picker import prepare_candidates
from .presentation import display_value
from .state import FieldSession, FocusArea, Workspace

Segment = tuple[str, str, str]
Line = list[Segment]


def field_segment(
    catalog: Catalog,
    collection: str,
    values: dict[str, Any],
    field_key: str,
    text: str | None = None,
    style: str = screen._TEXT_PRIMARY,
) -> Segment:
    """Create the stable target for one displayed field.

    ``field:<key>`` is the field's identity in every inspector state. Editability
    is deliberately absent from this function; Enter resolves that separately.
    """
    shown = display_value(catalog, collection, values, field_key)
    return shown if text is None else text, style, f"field:{field_key}"


def _target_indent(lines: list[Line], target: str) -> int:
    """Return the rendered cell offset at which one semantic field begins."""
    for line in lines:
        used = 0
        for text, _, action in line:
            if action == target:
                return used
            used += screen._display_width(text)
    return 0


def expand_options(lines: list[Line], session: FieldSession | None) -> list[Line]:
    if session is None or session.options is None:
        return lines

    prepare_candidates(session)
    target = f"field:{session.active_key}"
    insert_at = next(
        (i + 1 for i, line in enumerate(lines) if any(action == target for _, _, action in line)),
        len(lines),
    )
    indent = _target_indent(lines, target)
    prefix: Line = [(" " * indent, screen._TEXT_PRIMARY, "")] if indent else []
    options = [prefix + [(
        safe(label),
        screen._TEXT_SECONDARY,
        f"option:{i}",
    )] for i, (_, label) in enumerate(session.options)]
    lines[insert_at:insert_at] = options or [prefix + [("暂无其他候选项", screen._TEXT_SECONDARY, "")]]
    return lines


def wrap_lines(lines: list[Line], width: int) -> list[Line]:
    """Wrap terminal cells while retaining field and link identities."""
    result: list[Line] = []
    width = max(1, width)
    for line in lines:
        current: Line = []
        used = 0
        for text, style, action in line:
            fragment = ""
            for char in text:
                size = screen._display_width(char)
                if char == "\n" or used + size > width:
                    if fragment:
                        current.append((fragment, style, action))
                    result.append(current)
                    current, fragment, used = [], "", 0
                    if char == "\n":
                        continue
                fragment += char
                used += size
            if fragment:
                current.append((fragment, style, action))
        result.append(current)
    return result


def content_offset(lines: list[Line], layout: WorkspaceLayout) -> int:
    """Return the compact heading offset from final wrapped geometry."""
    first_is_field = bool(
        lines and any(action.startswith("field:") for _, _, action in lines[0])
    )
    return 1 if layout.compact and not first_is_field else 0


def layout_lines(lines: list[Line], width: int, layout: WorkspaceLayout) -> list[Line]:
    """Produce the single final geometry used by rendering, hit testing and navigation."""
    wrapped = wrap_lines(lines, width)
    return wrapped[content_offset(wrapped, layout):]


def action_line_map(lines: list[Line], *, include_options: bool = False) -> dict[str, list[int]]:
    """Map each semantic target to every physical line it occupies."""
    result: dict[str, list[int]] = {}
    for index, line in enumerate(lines):
        actions = dict.fromkeys(
            action for _, _, action in line
            if action and (include_options or not action.startswith("option:"))
        )
        for action in actions:
            result.setdefault(action, []).append(index)
    return result


def action_targets(lines: list[Line]) -> list[tuple[int, str]]:
    """Return semantic targets in display order, anchored at their first line."""
    return [(indexes[0], action) for action, indexes in action_line_map(lines, include_options=True).items()]


def _student_grade_column(action: str) -> int | None:
    """Return the semantic column inside a student's course/score pair."""
    if action.startswith("field:related:grades:") and action.endswith(":score"):
        return 1
    if action.startswith("related:grades:"):
        return 0
    return None


def _student_grade_row(row: list[str]) -> bool:
    return len(row) >= 2 and {_student_grade_column(action) for action in row} >= {0, 1}


def directional_target(lines: list[Line], current: str, direction: str) -> str | None:
    """Navigate directly on the final visible semantic geometry.

    Consecutive physical lines carrying the same actions are one semantic row,
    so wrapping or multiline content never creates a second navigation stop.
    Student course/score rows form a two-column grid: vertical movement keeps
    the current column, and entering that grid defaults to the course column.
    """
    rows: list[list[str]] = []
    for line in lines:
        row = list(dict.fromkeys(
            action for _, _, action in line
            if action and not action.startswith("option:")
        ))
        if row and (not rows or row != rows[-1]):
            rows.append(row)

    location = next(((i, row.index(current)) for i, row in enumerate(rows) if current in row), None)
    if location is None:
        return None
    row, column = location
    if direction == "left":
        return rows[row][column - 1] if column else None
    if direction == "right":
        return rows[row][min(column + 1, len(rows[row]) - 1)]

    target_row = min(max(0, row + (-1 if direction == "up" else 1)), len(rows) - 1)
    target = rows[target_row]
    if _student_grade_row(target):
        current_column = _student_grade_column(current)
        wanted = 0 if current_column is None else current_column
        return next(
            (action for action in target if _student_grade_column(action) == wanted),
            target[0],
        )
    return target[-1]


def render_inspector(
    board: Board,
    state: Workspace,
    catalog: Catalog,
    x: int,
    width: int,
    raw_lines: list[Line],
) -> None:
    layout = WorkspaceLayout(board.width, board.height)
    top = layout.panel_content_row(state.key)
    bottom = board.height - 1
    row = state.current(catalog)
    focused = state.focus is FocusArea.INSPECTOR
    if row is None:
        board.put(x, layout.panel_heading_row(state.key), panel_heading("档案", focused), width=width)
        board.put(
            x, top + 1,
            "没有匹配的记录" if state.query else "暂无记录",
            screen._TEXT_SECONDARY,
            width=width,
        )
        if state.query:
            board.button(x, top + 3, "清除搜索", "reset-search")
        elif not catalog.read_only:
            board.button(x, top + 3, "新建记录", "create")
        return

    session = state.field_session
    heading = identity(state.key, row)[0] if layout.compact else "档案"
    board.put(
        x,
        layout.panel_heading_row(state.key),
        panel_heading(heading, focused or session is not None),
        action="focus-details" if session is None else None,
        width=width,
    )

    lines = layout_lines(raw_lines, width, layout)
    capacity = layout.panel_capacity(state.key)

    selected_action = ""
    target_line = 0
    if session is not None:
        selected_action = (
            f"option:{session.option_index}"
            if session.options
            else (
                f"field:{session.anchor_key}"
                if session.anchor_key.startswith("related:")
                else f"field:{session.active_key}"
            )
        )
    else:
        targets = action_targets(lines)
        if targets and state.detail_selected >= 0:
            state.detail_selected = min(state.detail_selected, len(targets) - 1)
            target_line, selected_action = targets[state.detail_selected]
        elif not targets:
            state.detail_selected = -1

    spans = action_line_map(lines, include_options=True)
    occupied = spans.get(selected_action, [target_line]) if selected_action else [target_line]
    if occupied:
        target_line = occupied[0]

    max_scroll = max(0, len(lines) - capacity)
    state.detail_scroll = min(max(0, state.detail_scroll), max_scroll)
    if session is not None or (focused and selected_action):
        first_visible = state.detail_scroll
        last_visible = state.detail_scroll + capacity - 1
        if not any(first_visible <= line <= last_visible for line in occupied):
            target_line = occupied[-1] if occupied[-1] < first_visible else occupied[0]
            state.detail_scroll = visible_start(target_line, len(lines), capacity, state.detail_scroll)

    visible = lines[state.detail_scroll:state.detail_scroll + capacity]
    show_selection_marker = session is None or session.options is not None
    for offset_in_view, segments in enumerate(visible):
        y = top + offset_in_view
        cursor = x
        content_right = x + width
        for segment_index, (text, style, action) in enumerate(segments):
            strong = bool(action and action == selected_action and (focused or session is not None))
            weak = bool(action and action == selected_action and not strong)
            if (strong or weak) and show_selection_marker:
                marker = theme.selection_prefix(selected=strong, current=weak)
                marker_width = min(screen._display_width(marker), max(0, content_right - cursor))
                if marker_width:
                    marker_style = theme.selection_marker_style() if strong else screen._TEXT_SECONDARY
                    if action.startswith("option:") and cursor - marker_width >= x:
                        # Picker rows reserve their marker to the left of the
                        # candidate text.  Selection never moves the text.
                        board.put(
                            cursor - marker_width,
                            y,
                            marker,
                            marker_style,
                            action,
                            width=marker_width,
                        )
                    else:
                        board.put(cursor, y, marker, marker_style, action, width=marker_width)
                        cursor += marker_width

            remaining = max(0, content_right - cursor)
            if remaining <= 0:
                break
            shown = screen._clip_cells(text, remaining)
            display = screen._display_width(shown)
            drawn_style = theme.selection_style(style) if strong else style

            if action:
                hit_width = max(1, display)
                if (
                    session is not None
                    and action == selected_action
                    and session.options is None
                    and segment_index == len(segments) - 1
                ):
                    hit_width = max(hit_width, remaining)
                board.regions.append(screen.HitRegion(cursor + 1, y + 1, hit_width, action))
            board.put(cursor, y, shown, drawn_style, width=remaining)
            cursor += display

    if session is None:
        board.regions.extend(
            screen.HitRegion(x + 1, y + 1, width, "focus-details")
            for y in range(top, bottom)
        )
