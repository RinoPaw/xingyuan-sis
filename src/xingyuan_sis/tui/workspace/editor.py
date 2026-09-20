from __future__ import annotations

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
from .picker import prepare_candidates
from .presentation import delete_impacts, display_value, project_record
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
    """Render destructive context as one aligned inspector-side task."""
    form = state.form
    title, identifier = identity(state.key, form.original)
    rows: list[tuple[str, str, str]] = [
        ("记录", title, screen._TEXT_PRIMARY),
        ("标识", identifier, screen._TEXT_SECONDARY),
        *(
            (label, value, screen._TEXT_PRIMARY)
            for label, value in delete_impacts(catalog, state.key, form.original)
        ),
        ("风险", "删除后无法撤销", screen._BOLD + screen._TEXT_DANGER),
    ]

    board.put(x, y, "确认删除以下记录？", screen._BOLD + screen._TEXT_PRIMARY, width=width)
    if y + 1 < bottom:
        board.put(x, y + 1, "─" * width, screen._BORDER_SUBTLE, width=width)

    label_width = 6
    value_x = x + label_width + 2
    value_width = max(1, width - label_width - 2)
    for index, (label, value, style) in enumerate(rows):
        row_y = y + 3 + index
        if row_y >= bottom:
            break
        board.put(
            x,
            row_y,
            screen._pad_cells(screen._clip_cells(label, label_width), label_width),
            screen._TEXT_SECONDARY,
            width=label_width,
        )
        board.put(value_x, row_y, value, style, width=value_width)


def _field_label(field, width: int) -> str:
    """Render a complete field label; geometry, not clipping, decides its width."""
    label = screen._ansi(field.label, screen._TEXT_SECONDARY)
    required = screen._ansi(" *", screen._TEXT_PRIMARY) if field.required else ""
    used = screen._display_width(field.label) + (2 if field.required else 0)
    padding = screen._ansi(" " * max(0, width - used), screen._TEXT_SECONDARY)
    return label + required + padding


def _render_form_heading(
    board: Board,
    state: Workspace,
    x: int,
    y: int,
    width: int,
    heading: str,
) -> None:
    """Keep task identity and mouse save action in one row."""
    board.put(x, y, panel_heading(heading, True), width=width)
    form = state.form
    if form is None or not form.fields:
        return

    save = theme.button("保存")
    save_width = screen._display_width(save)
    if save_width <= width:
        board.put(x + width - save_width, y, save, action="save", width=save_width)


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
    bottom = board.height - 1

    titles = {
        "delete": "删除记录",
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
                prepare_candidates(session)
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
