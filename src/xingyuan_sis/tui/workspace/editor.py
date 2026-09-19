from __future__ import annotations

from typing import TYPE_CHECKING

from .. import screen
from ..layout import WorkspaceLayout
from ..view_common import Board, identity, panel_heading, safe
from .data import COLLECTIONS, Catalog

if TYPE_CHECKING:
    from .state import Workspace


def render_editor(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    """Render a transaction in the same panel geometry used by the record inspector."""
    form = state.form
    layout = WorkspaceLayout(board.width, board.height)
    heading_row = layout.panel_heading_row(state.key)
    content_row = layout.panel_content_row(state.key)
    bottom = board.height - 2

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

    entries: list[tuple[str, int, object]] = []
    selected_entry = 0
    for index, field in enumerate(form.fields):
        entries.append(("field", index, field))
        if index == form.position:
            selected_entry = len(entries) - 1
            if form.options is not None:
                if form.options:
                    for option_index, (_, label) in enumerate(form.options):
                        entries.append(("option", option_index, label))
                        if option_index == form.option_index:
                            selected_entry = len(entries) - 1
                else:
                    entries.append(("empty", 0, "暂无可选记录，请先创建。"))
                    selected_entry = len(entries) - 1

    capacity = max(1, bottom - content_row)
    first = min(
        max(0, selected_entry - capacity + 1),
        max(0, len(entries) - capacity),
    )
    label_width = min(12, max(4, width // 3))

    for visible_index, (kind, index, payload) in enumerate(entries[first:first + capacity]):
        y = content_row + visible_index
        if kind == "option":
            text = screen._pad_cells(screen._clip_cells("  " + safe(payload), width), width)
            style = (
                screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
                if index == form.option_index
                else screen._TEXT_PRIMARY
            )
            board.put(x, y, text, style, f"option:{index}", width)
            continue
        if kind == "empty":
            board.put(x, y, safe(payload), screen._TEXT_SECONDARY, width=width)
            continue

        field = payload
        value = safe(form.values.get(field.key))
        if form.mode == "create":
            options = catalog.options(state.key, field.key, form.values)
            if options is not None:
                value = next((label for key, label in options if key == form.values.get(field.key)), value)
        label = screen._pad_cells(
            screen._clip_cells(field.label + ("*" if field.required else ""), label_width),
            label_width,
        )
        text = screen._pad_cells(screen._clip_cells(f"{label}  {value}", width), width)
        selected = index == form.position and form.options is None
        style = screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED if selected else screen._TEXT_PRIMARY
        board.put(x, y, text, style, f"field:{index}", width)
