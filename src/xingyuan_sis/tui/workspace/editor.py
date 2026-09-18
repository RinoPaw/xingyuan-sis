from __future__ import annotations

from typing import TYPE_CHECKING

from .. import screen
from ..layout import WorkspaceLayout
from ..view_common import Board, identity, safe
from .commands import FORM_SAVE
from .data import COLLECTIONS, Catalog

if TYPE_CHECKING:
    from .state import Workspace


def render_editor(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    form = state.form
    layout = WorkspaceLayout(board.width, board.height)
    heading_row = layout.panel_heading_row(state.key)
    content_row = layout.panel_content_row(state.key)

    if form.options is not None:
        board.put(
            x, heading_row, "选择 / " + form.fields[form.position].label,
            screen._BOLD + screen._TEXT_ACCENT, width=width,
        )
        option_row = content_row + 1
        capacity = max(1, board.height - option_row - 3)
        first = min(max(0, form.option_index - capacity + 1), max(0, len(form.options) - capacity))
        for i, (_, label) in enumerate(form.options[first:first + capacity], start=first):
            text = screen._pad_cells(screen._clip_cells(safe(label), width), width)
            selected_style = screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED if i == form.option_index else ""
            board.put(x, option_row + i - first, text, selected_style, f"option:{i}", width)
        if not form.options:
            board.put(x, option_row, "暂无可选记录，请先创建。", screen._TEXT_SECONDARY, width=width)
        return

    titles = {
        "create": "新建 · " + COLLECTIONS[state.key].noun if state.key in COLLECTIONS else "新建",
        "delete": "删除记录",
        "import": "导入学生 CSV",
        "export": "导出学生 CSV",
        "seed": "建立演示校园",
        "reset-password": "重置学生密码",
    }
    board.put(x, heading_row, titles[form.mode], screen._BOLD + screen._TEXT_ACCENT, width=width)

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
        capacity = max(1, board.height - 3 - content_row)
        spacing = 2 if capacity >= len(messages) * 2 else 1
        for index, (message, style) in enumerate(messages[:capacity]):
            y = content_row + index * spacing
            if y < board.height - 3:
                board.put(x, y, message, style, width=width)
    else:
        if not layout.compact:
            board.put(x, content_row, "* 必填  ·  更改暂存，保存后生效", screen._TEXT_SECONDARY, width=width)
        field_row = content_row if layout.compact else content_row + 2
        capacity = max(1, board.height - field_row - (3 if layout.compact else 4))
        first = min(max(0, form.position - capacity + 1), max(0, len(form.fields) - capacity))
        for i, field in enumerate(form.fields[first:first + capacity], start=first):
            value = safe(form.values.get(field.key))
            if form.mode == "create":
                options = catalog.options(state.key, field.key, form.values)
                if options is not None:
                    value = next((label for key, label in options if key == form.values.get(field.key)), value)
            label_width = min(12, max(4, width // 3))
            label = screen._pad_cells(
                screen._clip_cells(field.label + ("*" if field.required else ""), label_width),
                label_width,
            )
            if i == form.position and not form.focus_save:
                text = screen._pad_cells(screen._clip_cells(f"{label}  {value}", width), width)
                board.put(
                    x, field_row + i - first, text,
                    screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED,
                    f"field:{i}", width,
                )
            else:
                text = (
                    screen._ansi(label, screen._TEXT_SECONDARY)
                    + "  "
                    + screen._ansi(value, screen._TEXT_PRIMARY)
                )
                board.put(x, field_row + i - first, text, action=f"field:{i}", width=width)
        if len(form.fields) > capacity and not layout.compact:
            board.put(
                x, board.height - 4,
                f"字段 {form.position + 1}/{len(form.fields)}  ·  ↑↓ 切换",
                screen._TEXT_SECONDARY, width=width,
            )

    save_label = FORM_SAVE.hint if form.fields else "Enter 确认"
    next_x = board.button(x, board.height - 3, save_label, "save", selected=form.focus_save or not form.fields)
    if next_x < x + width:
        board.put(next_x, board.height - 3, "Esc 取消", screen._TEXT_SECONDARY, width=max(1, x + width - next_x))
