from __future__ import annotations

from typing import TYPE_CHECKING

from .. import screen, theme
from ..layout import WorkspaceLayout
from ..view_common import Board, identity, panel_heading, safe
from .data import COLLECTIONS, Catalog
from .picker import PICKER_GUTTER, prepare_candidates
from .presentation import display_value, project_record
from .state import FieldSessionOwner

if TYPE_CHECKING:
    from .state import Workspace


_SELECTION_GUTTER = PICKER_GUTTER


def render_editor(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    """Render a complete transaction while FieldSession owns any active field edit."""
    form = state.form
    layout = WorkspaceLayout(board.width, board.height)
    heading_row = layout.panel_heading_row(state.key)
    content_row = layout.panel_content_row(state.key)
    bottom = board.height - 1

    titles = {
        "delete": "删除记录",
        "import": "导入学生 CSV",
        "export": "导出学生 CSV",
        "seed": "建立演示校园",
        "reset-password": "重置学生密码",
    }
    heading = "档案" if form.mode == "create" and state.key in COLLECTIONS else titles.get(form.mode, "档案")
    board.put(x, heading_row, panel_heading(heading, True), width=width)

    if form.mode in {"delete", "seed", "reset-password"}:
        messages: list[tuple[str, str]] = [
            ("将写入一组完整的演示数据。", screen._TEXT_PRIMARY),
            ("仅支持空数据库，已有记录会保留。", screen._TEXT_SECONDARY),
        ]
        if form.mode == "delete":
            title, identifier = identity(state.key, form.original)
            messages = [
                (f"确认删除 {title}？", screen._BOLD + screen._TEXT_PRIMARY),
                (identifier, screen._TEXT_SECONDARY),
                ("! 删除后无法撤销。", screen._BOLD + screen._TEXT_DANGER),
            ]
            if state.key in {"students", "courses"}:
                _, related = catalog.related(state.key, form.original)
                messages.append((f"同时移除 {len(related)} 条关联选课。", screen._TEXT_PRIMARY))
            elif state.key == "classes":
                _, students = catalog.related(state.key, form.original)
                notices = sum(row["class_id"] == form.original["id"] for row in catalog.records["announcements"])
                messages[2:] = [
                    (f"! {len(students)} 名学生将变为未分班。", screen._TEXT_DANGER),
                    (f"删除 {notices} 条班级公告，无法撤销。", screen._TEXT_DANGER),
                ]
        elif form.mode == "reset-password":
            title, identifier = identity(state.key, form.original)
            messages = [
                (f"重置 {title} 的密码？", screen._TEXT_PRIMARY),
                (identifier, screen._TEXT_SECONDARY),
                ("旧密码将失效，下次登录须改密。", screen._TEXT_SECONDARY),
            ]
        capacity = max(1, bottom - content_row)
        spacing = 2 if capacity >= len(messages) * 2 else 1
        for index, (message, style) in enumerate(messages[:capacity]):
            y = content_row + index * spacing
            if y < bottom:
                board.put(x, y, message, style, width=width)
        return

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

    capacity = max(1, bottom - content_row)
    first = min(
        max(0, selected_entry - capacity + 1),
        max(0, len(entries) - capacity),
    )
    label_width = min(12, max(4, width // 3))
    value_x = x + label_width + 2
    value_width = max(1, width - label_width - 2)
    field_x = value_x + _SELECTION_GUTTER
    field_width = max(1, value_width - _SELECTION_GUTTER)

    for visible_index, (kind, index, payload) in enumerate(entries[first:first + capacity]):
        y = content_row + visible_index
        if kind == "option":
            selected = session is not None and index == session.option_index
            marker = "> " if selected else "  "
            marker_style = theme.selection_marker_style() if selected else screen._TEXT_SECONDARY
            board.put(value_x, y, marker, marker_style, action=f"option:{index}", width=_SELECTION_GUTTER)

            body = screen._pad_cells(screen._clip_cells(safe(payload), field_width), field_width)
            body_style = (
                theme.selection_style(screen._TEXT_SECONDARY)
                if selected
                else screen._TEXT_SECONDARY
            )
            board.put(field_x, y, body, body_style, action=f"option:{index}", width=field_width)
            continue
        if kind == "empty":
            board.put(field_x, y, safe(payload), screen._TEXT_SECONDARY, width=field_width)
            continue

        field = payload
        label = screen._pad_cells(screen._clip_cells(field.label, label_width), label_width)
        board.put(x, y, label, screen._TEXT_SECONDARY, width=label_width)

        row_selected = index == form.position and session is None
        if row_selected:
            board.put(
                value_x,
                y,
                theme.selection_prefix(selected=True),
                theme.selection_marker_style(),
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
                    board.put(cursor, y, "-", screen._TEXT_SECONDARY, width=1)
                    cursor += 1
                if cursor >= right:
                    break
                available = min(slot_width, right - cursor)
                raw = values.get(key)
                text = "" if raw is None else str(raw)
                text = screen._pad_cells(screen._clip_cells(text, available), available)
                selected = session.active_key == key and session.options is None
                style = theme.selection_style() if selected else screen._TEXT_PRIMARY
                board.put(cursor, y, text, style, f"field:{key}", available)
                cursor += available
            continue

        value = (
            display_value(catalog, state.key, values, field.key)
            if state.key in COLLECTIONS
            else safe(values.get(field.key))
        )
        style = theme.selection_style() if row_selected else screen._TEXT_PRIMARY
        text = screen._pad_cells(screen._clip_cells(value, field_width), field_width)
        board.put(field_x, y, text, style, f"field:{field.key}", field_width)
