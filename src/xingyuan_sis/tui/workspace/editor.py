from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from .. import screen, theme
from ..layout import WorkspaceLayout
from ..view_common import Board, identity, panel_heading, safe
from .data import COLLECTIONS, Catalog
from .field_geometry import (
    FIELD_GUTTER,
    control_text,
    control_width,
    form_field_geometry,
)
from .presentation import delete_identity, delete_impacts, display_value, project_record
from .state import FieldSessionOwner

if TYPE_CHECKING:
    from .state import Workspace


_SELECTION_GUTTER = FIELD_GUTTER


def _render_delete_panel(
    board: Board,
    state: Workspace,
    catalog: Catalog,
    x: int,
    y: int,
    width: int,
    bottom: int,
) -> None:
    """Compact, risk-first confirmation with explicit keyboard and mouse choices."""
    form = state.form
    identity_rows = delete_identity(state.key, form.original)
    impacts = delete_impacts(catalog, state.key, form.original)

    # Reserve the controls before laying out details. Small terminals must
    # still expose the destructive choice and a visible cancellation path.
    label_delete = "确认删除" if width >= 22 else "删除"
    button_space = screen._display_width(theme.button(label_delete)) + screen._display_width(theme.button("取消")) + 1
    side_by_side = button_space <= width
    action_height = 1 if side_by_side else 2
    action_top = max(y, bottom - action_height)
    capacity = max(0, action_top - y)

    # Prefer showing consequences over secondary identifiers on short screens.
    lines: list[tuple[str, str, str]] = [
        ("field", identity_rows[0][0], identity_rows[0][1]),
        ("field", identity_rows[1][0], identity_rows[1][1]),
        *(("impact", "", text) for text in impacts),
        ("risk", "", "删除后无法撤销"),
    ]
    if len(lines) > capacity:
        lines.pop(1)  # Identifier is the first detail to hide under pressure.
    while len(lines) > capacity and len(lines) > 2:
        lines.pop(-2)  # Retain the record name and irreversible-risk warning.
    if len(lines) > capacity:
        lines = lines[-capacity:] if capacity else []

    label_width = min(max(screen._display_width(label) for label, _ in identity_rows), max(1, width // 2))
    value_x = x + label_width + 2
    value_width = max(1, width - label_width - 2)
    spacious = bottom - y >= len(lines) + action_height + 3
    for index, (kind, label, value) in enumerate(lines):
        line_y = y + index + (1 if spacious and index >= 2 else 0)
        if line_y >= action_top:
            break
        if kind == "field":
            board.put(x, line_y, screen._pad_cells(label, label_width), screen._TEXT_SECONDARY, width=label_width)
            if value_x < x + width:
                board.put(value_x, line_y, value, screen._TEXT_PRIMARY, width=value_width)
        elif kind == "impact":
            board.put(x, line_y, value, screen._TEXT_SECONDARY, width=width)
        else:
            board.put(x, line_y, value, screen._BOLD + screen._TEXT_DANGER, width=width)

    control_y = min(bottom - action_height, y + len(lines) + (2 if spacious else 1))
    control_y = max(y, control_y)
    next_x = board.button(x, control_y, label_delete, "confirm-delete", selected=form.position == 0)
    if side_by_side:
        board.button(next_x, control_y, "取消", "cancel-delete", selected=form.position == 1)
    elif control_y + 1 < bottom:
        board.button(x, control_y + 1, "取消", "cancel-delete", selected=form.position == 1)


def _field_label(field, width: int) -> str:
    """Render a complete field label with required markers in one aligned column."""
    if field.required:
        label_width = max(0, width - 2)
        label = screen._pad_cells(field.label, label_width)
        return (
            screen._ansi(label, screen._TEXT_SECONDARY)
            + screen._ansi(" *", screen._TEXT_PRIMARY)
        )
    return screen._ansi(screen._pad_cells(field.label, width), screen._TEXT_SECONDARY)


def _render_form_heading(
    board: Board,
    state: Workspace,
    x: int,
    y: int,
    width: int,
    heading: str,
) -> None:
    """Render only the task identity; the transaction action lives below the archive."""
    board.put(x, y, panel_heading(heading, True), width=width)


def _render_form_action(board: Board, mode: str, x: int, y: int) -> None:
    label = {
        "seed": "确认",
        "reset-password": "确认",
        "import": "执行",
        "export": "执行",
    }.get(mode, "保存")
    board.button(x, y, label, "save")


def _entry_height(kind: str, row_height: int) -> int:
    return row_height if kind == "field" else 1


def _visible_entries(
    entries: list[tuple[str, int, object]],
    selected: int,
    capacity: int,
    row_height: int,
) -> list[tuple[tuple[str, int, object], int]]:
    """Fit semantic entries by their real rendered height, not by entry count."""
    capacity = max(1, capacity)
    first = 0
    while first < selected:
        needed = sum(
            _entry_height(kind, row_height)
            for kind, _, _ in entries[first:selected + 1]
        )
        if needed <= capacity:
            break
        first += 1

    visible: list[tuple[tuple[str, int, object], int]] = []
    used = 0
    for entry in entries[first:]:
        height = _entry_height(entry[0], row_height)
        if used + height > capacity:
            break
        visible.append((entry, used))
        used += height
    return visible


def render_editor(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    """Render a complete transaction while FieldSession owns any active field edit."""
    form = state.form
    layout = WorkspaceLayout(board.width, board.height)
    heading_row = layout.panel_heading_row(state.key)
    status_row = heading_row + 1
    content_row = max(layout.panel_content_row(state.key), status_row + 1)
    action_row = board.height - 2
    bottom = action_row

    titles = {
        "import": "导入学生 CSV",
        "export": "导出学生 CSV",
        "seed": "建立演示校园",
        "reset-password": "重置学生密码",
    }
    heading = (
        f"新增{COLLECTIONS[state.key].title}"
        if form.mode == "create" and state.key in COLLECTIONS
        else titles.get(form.mode, "档案")
    )
    if form.mode == "delete":
        board.put(x, heading_row, "▌ " + "删除" + COLLECTIONS[state.key].title, screen._BOLD + screen._TEXT_DANGER, width=width)
    else:
        _render_form_heading(board, state, x, heading_row, width, heading)

    if form.mode == "delete":
        _render_delete_panel(board, state, catalog, x, content_row, width, bottom)
        return

    if form.mode in {"seed", "reset-password"}:
        messages: list[tuple[str, str]] = [
            ("将写入一组完整的演示数据。", screen._TEXT_PRIMARY),
            ("仅支持空数据库，已有记录会保留。", screen._TEXT_SECONDARY),
        ]
        if form.mode == "reset-password":
            title, identifier = identity(state.key, form.original)
            messages = [
                (f"重置 {title} 的密码？", screen._TEXT_PRIMARY),
                (identifier, screen._TEXT_SECONDARY),
                ("密码将恢复为学号；下次登录须改密。", screen._TEXT_SECONDARY),
            ]
        capacity = max(1, bottom - content_row)
        spacing = 2 if capacity >= len(messages) * 2 else 1
        for index, (message, style) in enumerate(messages[:capacity]):
            y = content_row + index * spacing
            if y < bottom:
                board.put(x, y, message, style, width=width)
        _render_form_action(board, form.mode, x, action_row)
        return

    if state.notice and status_row < bottom:
        is_error = state.notice.startswith("未完成：")
        board.put(
            x,
            status_row,
            theme.notice(state.notice, error=is_error),
            width=width,
        )

    session = state.field_session
    if session is not None and session.owner is not FieldSessionOwner.FORM:
        session = None
    values = project_record(form.values, session)

    entries: list[tuple[str, int, object]] = []
    selected_entry = 0
    for index, field in enumerate(form.fields):
        entries.append(("field", index, field))
        if index == form.position:
            selected_entry = len(entries) - 1
            session_on_field = session is not None and (
                session.active_key == field.key
                or (field.key == "birth_date" and session.anchor_key == "birth_date")
            )
            if session_on_field and session.options is not None:
                if session.options:
                    for option_index, (_, label) in enumerate(session.options):
                        entries.append(("option", option_index, label))
                        if option_index == session.option_index:
                            selected_entry = len(entries) - 1
                else:
                    entries.append(("empty", 0, "暂无其他候选项"))
                    selected_entry = len(entries) - 1

    geometry = form_field_geometry(form.fields, width)
    marker_x = x + geometry.marker_offset
    field_x = x + geometry.control_offset
    field_width = geometry.control_available
    capacity = max(1, bottom - content_row)
    if capacity < geometry.row_height:
        # One available content line cannot contain a two-row stacked field.
        # Keep the selected control reachable instead of rendering no field.
        control_offset = min(width - 1, max(_SELECTION_GUTTER, width // 2))
        geometry = replace(
            geometry,
            stacked=False,
            label_width=max(0, control_offset - _SELECTION_GUTTER),
            marker_offset=max(0, control_offset - _SELECTION_GUTTER),
            control_offset=control_offset,
            control_available=max(1, width - control_offset),
            row_height=1,
        )
    visible = _visible_entries(entries, selected_entry, capacity, geometry.row_height)

    for (kind, index, payload), row_offset in visible:
        y = content_row + row_offset
        if kind == "option":
            selected = session is not None and index == session.option_index
            marker = "> " if selected else "  "
            marker_style = screen._TEXT_ACCENT if selected else screen._TEXT_SECONDARY
            board.put(
                marker_x,
                y,
                marker,
                marker_style,
                action=f"option:{index}",
                width=_SELECTION_GUTTER,
            )

            value = safe(payload)
            width_for_option = control_width(value, field_width)
            body = control_text(value, width_for_option)
            body_style = (
                theme.selection_style(screen._TEXT_SECONDARY)
                if selected
                else screen._TEXT_SECONDARY
            )
            board.put(
                field_x,
                y,
                body,
                body_style,
                action=f"option:{index}",
                width=width_for_option,
            )
            continue
        if kind == "empty":
            board.put(field_x, y, safe(payload), screen._TEXT_SECONDARY, width=field_width)
            continue

        field = payload
        label_y = y
        control_y = y + 1 if geometry.stacked else y
        board.put(
            x,
            label_y,
            _field_label(field, geometry.label_width),
            width=geometry.label_width,
        )

        row_selected = index == form.position and session is None
        if row_selected:
            board.put(
                marker_x,
                control_y,
                theme.selection_prefix(selected=True),
                screen._TEXT_ACCENT,
                width=_SELECTION_GUTTER,
            )

        birth_editing = (
            field.key == "birth_date"
            and session is not None
            and session.anchor_key == "birth_date"
        )
        if birth_editing:
            cursor = field_x
            right = field_x + field_width
            parts = (("birth_year", 4), ("birth_month", 2), ("birth_day", 2))
            for part_index, (key, slot_width) in enumerate(parts):
                if part_index:
                    board.put(cursor, control_y, "-", screen._TEXT_SECONDARY, width=1)
                    cursor += 1
                if cursor >= right:
                    break
                available = min(slot_width, right - cursor)
                raw = values.get(key)
                text = "" if raw is None else str(raw)
                text = screen._pad_cells(screen._clip_cells(text, available), available)
                selected = session.active_key == key and session.options is None
                style = theme.selection_style() if selected else screen._TEXT_PRIMARY
                board.put(cursor, control_y, text, style, f"field:{key}", available)
                cursor += available
            continue

        value = (
            display_value(catalog, state.key, values, field.key)
            if state.key in COLLECTIONS
            else safe(values.get(field.key))
        )
        editing = (
            session is not None
            and session.options is None
            and session.active_key == field.key
        )
        width_for_field = control_width(value, field_width)
        style = theme.selection_style() if row_selected or editing else screen._TEXT_PRIMARY
        text = control_text(value, width_for_field)
        board.put(
            field_x,
            control_y,
            text,
            style,
            f"field:{field.key}",
            width_for_field,
        )

    _render_form_action(board, form.mode, x, action_row)
