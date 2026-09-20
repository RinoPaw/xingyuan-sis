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
NavigationTarget = tuple[str, int]
NavigationRow = list[NavigationTarget]


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


def _navigation_rows(lines: list[Line]) -> list[NavigationRow]:
    """Project rendered lines into semantic targets with terminal-cell columns."""
    rows: list[NavigationRow] = []
    previous_actions: tuple[str, ...] = ()
    for line in lines:
        cursor = 0
        row: NavigationRow = []
        seen: set[str] = set()
        for text, _, action in line:
            if action and not action.startswith("option:") and action not in seen:
                row.append((action, cursor))
                seen.add(action)
            cursor += screen._display_width(text)

        actions = tuple(action for action, _ in row)
        if row and actions != previous_actions:
            rows.append(row)
            previous_actions = actions
    return rows


def directional_target(lines: list[Line], current: str, direction: str) -> str | None:
    """Navigate on final terminal geometry without knowing business semantics.

    Consecutive wrapped lines carrying the same targets are one semantic row.
    Horizontal movement follows target order in that row. Vertical movement
    selects the target whose terminal-cell column is closest to the current one.
    """
    rows = _navigation_rows(lines)
    location = next(
        (
            (row_index, column_index, x)
            for row_index, row in enumerate(rows)
            for column_index, (action, x) in enumerate(row)
            if action == current
        ),
        None,
    )
    if location is None:
        return None

    row_index, column_index, current_x = location
    row = rows[row_index]
    if direction == "left":
        return row[column_index - 1][0] if column_index else None
    if direction == "right":
        return row[min(column_index + 1, len(row) - 1)][0]
    if direction not in {"up", "down"}:
        return None

    target_index = min(
        max(0, row_index + (-1 if direction == "up" else 1)),
        len(rows) - 1,
    )
    target_row = rows[target_index]
    return min(target_row, key=lambda target: abs(target[1] - current_x))[0]


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
            if strong and show_selection_marker:
                marker = theme.selection_prefix(selected=True)
                marker_width = min(screen._display_width(marker), max(0, content_right - cursor))
                if marker_width:
                    if action.startswith("option:") and cursor - marker_width >= x:
                        # Picker rows reserve their marker to the left of the
                        # candidate text.  Selection never moves the text.
                        board.put(
                            cursor - marker_width,
                            y,
                            marker,
                            theme.selection_marker_style(),
                            action,
                            width=marker_width,
                        )
                    else:
                        board.put(
                            cursor,
                            y,
                            marker,
                            theme.selection_marker_style(),
                            action,
                            width=marker_width,
                        )
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
