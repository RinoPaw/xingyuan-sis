"""Shared field rendering, option expansion and viewport for all record inspectors."""
from __future__ import annotations

from typing import Any

from .. import screen
from ..layout import WorkspaceLayout, visible_start
from ..view_common import Board, identity, panel_heading, safe
from .data import Catalog
from .presentation import display_value
from .state import Workspace

Segment = tuple[str, str, str]
Line = list[Segment]


def is_editing(state: Workspace | None) -> bool:
    return state is not None and state.form is not None and state.form.mode == "edit"


def field_segment(
    state: Workspace | None, catalog: Catalog, key: str, row: dict[str, Any],
    field_key: str, text: str | None = None, style: str = screen._TEXT_PRIMARY,
) -> Segment:
    """Render one field.

    Browse targets describe focus, not editability. Every displayed field therefore
    owns a stable ``field-target:<key>`` action. Enter decides separately whether
    the field may be edited. During a field edit, only that local edit session owns
    an interactive ``field:<index>`` action.
    """
    editing = is_editing(state)
    if editing:
        index = next((i for i, field in enumerate(state.form.fields) if field.key == field_key), None)
        action = f"field:{index}" if index is not None else ""
        selected = index == state.form.position and not state.form.focus_save
    else:
        action = f"field-target:{field_key}"
        selected = False
    shown = display_value(catalog, key, row, field_key)
    return (
        shown if text is None else text,
        screen._BOLD + screen._TEXT_ACCENT if selected else style,
        action,
    )


def expand_options(lines: list[Line], state: Workspace | None) -> list[Line]:
    if not is_editing(state) or state.form.options is None:
        return lines
    target = f"field:{state.form.position}"
    insert_at = next(
        (i + 1 for i, line in enumerate(lines) if any(action == target for _, _, action in line)),
        len(lines),
    )
    options = [[(
        "  " + safe(label),
        screen._BOLD + screen._TEXT_ACCENT if i == state.form.option_index else screen._TEXT_PRIMARY,
        f"option:{i}",
    )] for i, (_, label) in enumerate(state.form.options)]
    lines[insert_at:insert_at] = options or [[("  暂无可选记录", screen._TEXT_SECONDARY, "")]]
    return lines


def wrap_lines(lines: list[Line], width: int) -> list[Line]:
    """Wrap terminal cells while retaining field and link hit targets."""
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


def action_targets(lines: list[Line]) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, line in enumerate(lines):
        for _, _, action in line:
            if action and action not in seen:
                result.append((index, action))
                seen.add(action)
    return result


def directional_target(lines: list[Line], current: str, direction: str) -> str | None:
    """Navigate by rendered geometry.

    Vertical movement follows rows and enters the rightmost target of a composite
    row. Horizontal movement stays in the current row. Returning ``None`` on a
    left move means the caller may leave the inspector.
    """
    rows = [list(dict.fromkeys(action for _, _, action in line if action)) for line in lines]
    rows = [row for row in rows if row]
    location = next(((i, row.index(current)) for i, row in enumerate(rows) if current in row), None)
    if location is None:
        return None
    row, column = location
    if direction == "left":
        return rows[row][column - 1] if column else None
    if direction == "right":
        return rows[row][min(column + 1, len(rows[row]) - 1)]
    target = min(max(0, row + (-1 if direction == "up" else 1)), len(rows) - 1)
    return rows[target][-1]


def content_offset(lines: list[Line], layout: WorkspaceLayout) -> int:
    # A compact identity heading may replace a non-focusable title, never a field target.
    field_title = bool(
        lines and any(
            action.startswith(("field:", "field-target:"))
            for _, _, action in lines[0]
        )
    )
    return 1 if layout.compact and not field_title else 0


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
    bottom = board.height - 2
    row = state.current(catalog)
    if row is None:
        board.put(x, layout.panel_heading_row(state.key), panel_heading("档案", state.details), width=width)
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

    editing = is_editing(state)
    heading = identity(state.key, row)[0] if layout.compact else "档案"
    board.put(
        x,
        layout.panel_heading_row(state.key),
        panel_heading(heading, (state.details and not state.action_focus) or editing),
        action="focus-details" if not editing else None,
        width=width,
    )

    # Existing-record editing keeps the archive itself in place. In compact mode
    # the first archive field must not suddenly be consumed by the identity heading
    # just because only the active field owns an editing action.
    offset = 0 if editing else content_offset(raw_lines, layout)
    raw_lines = wrap_lines(raw_lines, width)
    lines = raw_lines[offset:]
    capacity = layout.panel_capacity(state.key)

    selected_action = ""
    target_line = 0
    if editing:
        selected_action = (
            f"option:{state.form.option_index}"
            if state.form.options is not None and state.form.options
            else f"field:{state.form.position}"
        )
        target_line = next(
            (
                index
                for index, line in enumerate(lines)
                if any(action == selected_action for _, _, action in line)
            ),
            0,
        )
    else:
        targets = [
            (line - offset, action)
            for line, action in action_targets(raw_lines)
            if line >= offset
        ]
        if targets and state.detail_selected >= 0:
            state.detail_selected = min(state.detail_selected, len(targets) - 1)
            target_line, selected_action = targets[state.detail_selected]
        elif not targets:
            state.detail_selected = -1

    max_scroll = max(0, len(lines) - capacity)
    state.detail_scroll = min(max(0, state.detail_scroll), max_scroll)
    if editing or (state.details and selected_action):
        state.detail_scroll = visible_start(target_line, len(lines), capacity, state.detail_scroll)

    visible = lines[state.detail_scroll:state.detail_scroll + capacity]
    for offset_in_view, segments in enumerate(visible):
        y = top + offset_in_view
        cursor = x
        for segment_index, (text, style, action) in enumerate(segments):
            remaining = max(0, x + width - cursor)
            if remaining <= 0:
                break
            shown = screen._clip_cells(text, remaining)
            display = screen._display_width(shown)
            selected = bool(
                action
                and action == selected_action
                and (editing or state.details)
                and not (editing and state.form.focus_save)
            )
            drawn_style = (
                screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
                if selected
                else style
            )

            if action:
                hit_width = max(1, display)
                if editing and action.startswith("field:"):
                    field_index = int(action.split(":")[1])
                    field_key = state.form.fields[field_index].key
                    freeform = catalog.options(state.key, field_key, state.form.values) is None
                    if (
                        selected
                        and state.form.options is None
                        and freeform
                        and segment_index == len(segments) - 1
                    ):
                        hit_width = max(hit_width, remaining)
                board.regions.append(screen.HitRegion(cursor + 1, y + 1, hit_width, action))
            board.put(cursor, y, shown, drawn_style, width=remaining)
            cursor += display

    if not editing:
        if len(lines) > capacity and not layout.compact:
            board.put(
                x,
                bottom - 1,
                f"{state.detail_scroll + 1}–{min(len(lines), state.detail_scroll + capacity)} / {len(lines)}",
                screen._TEXT_SECONDARY,
                action="focus",
                width=width,
            )
        board.regions.extend(
            screen.HitRegion(x + 1, y + 1, width, "focus-details")
            for y in range(top, bottom)
        )
