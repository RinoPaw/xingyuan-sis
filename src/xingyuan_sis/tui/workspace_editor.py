from __future__ import annotations

from typing import TYPE_CHECKING

from . import screen
from .view_common import Board, identity, safe
from .workspace_data import COLLECTIONS, Catalog

if TYPE_CHECKING:
    from .workspace import Workspace


def render_editor(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    form = state.form
    if form.options is not None:
        board.put(
            x, 8, "选择 / " + form.fields[form.position].label,
            screen._BOLD + screen._TEXT_ACCENT, width=width,
        )
        capacity = max(1, board.height - 13)
        first = min(max(0, form.option_index - capacity + 1), max(0, len(form.options) - capacity))
        for i, (_, label) in enumerate(form.options[first:first + capacity], start=first):
            marker = "› " if i == form.option_index else "  "
            text = screen._pad_cells(screen._clip_cells(marker + safe(label), width), width)
            selected_style = screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED if i == form.option_index else ""
            board.put(x, 10 + i - first, text, selected_style, f"option:{i}", width)
        if not form.options:
            board.put(x, 10, "暂无可选记录，请先创建。", screen._TEXT_SECONDARY, width=width)
        return

    titles = {
        "create": "新建 · " + COLLECTIONS[state.key].noun if state.key in COLLECTIONS else "新建",
        "edit": "编辑 · " + COLLECTIONS[state.key].noun if state.key in COLLECTIONS else "编辑",
        "delete": "删除记录",
        "import": "导入学生 CSV",
        "export": "导出学生 CSV",
        "seed": "建立演示校园",
    }
    board.put(x, 8, titles[form.mode], screen._BOLD + screen._TEXT_ACCENT, width=width)

    if form.mode in {"delete", "seed"}:
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
        for index, (message, style) in enumerate(messages):
            board.put(x, 10 + index * 2, message, style, width=width)
    else:
        board.put(x, 9, "* 必填  ·  更改暂存，保存后生效", screen._TEXT_SECONDARY, width=width)
        capacity = max(1, board.height - 15)
        first = min(max(0, form.position - capacity + 1), max(0, len(form.fields) - capacity))
        for i, field in enumerate(form.fields[first:first + capacity], start=first):
            value = safe(form.values.get(field.key))
            if form.mode in {"create", "edit"}:
                options = catalog.options(state.key, field.key)
                if options is not None:
                    value = next((label for key, label in options if key == form.values.get(field.key)), value)
            label_width = min(12, max(4, width // 3))
            label = screen._pad_cells(screen._clip_cells(field.label + ("*" if field.required else ""), label_width), label_width)
            if i == form.position:
                text = screen._pad_cells(screen._clip_cells(f"› {label}  {value}", width), width)
                board.put(
                    x, 11 + i - first, text,
                    screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED,
                    f"field:{i}", width,
                )
            else:
                text = (
                    screen._ansi("  " + label, screen._TEXT_SECONDARY)
                    + "  "
                    + screen._ansi(value, screen._TEXT_PRIMARY)
                )
                board.put(x, 11 + i - first, text, action=f"field:{i}", width=width)
        if len(form.fields) > capacity:
            board.put(
                x, board.height - 4,
                f"字段 {form.position + 1}/{len(form.fields)}  ·  ↑↓ 切换",
                screen._TEXT_SECONDARY, width=width,
            )

    board.put(x, board.height - 3, "Esc 取消", screen._TEXT_SECONDARY, width=width)
