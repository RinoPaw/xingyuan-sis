"""Browse records and stage edits without leaving the current workspace."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from typing import Any

from . import screen, keys
from ..terminal_input import input_style, read_input
from .workspace_data import ACADEMICS, COLLECTIONS, Catalog, Field


@dataclass
class Form:
    mode: str
    fields: tuple[Field, ...] = ()
    values: dict[str, Any] = field(default_factory=dict)
    original: dict[str, Any] | None = None
    position: int = 0
    options: list[tuple[Any, str]] | None = None
    option_index: int = 0


@dataclass
class Workspace:
    key: str
    view: int = 0
    query: str = ""
    selected: int = 0
    details: bool = False
    detail_scroll: int = 0
    notice: str = ""
    form: Form | None = None
    report: list[str] = field(default_factory=list)
    history: list[tuple[str, int, str, int]] = field(default_factory=list)

    def rows(self, catalog: Catalog) -> list[dict[str, Any]]:
        rows = catalog.rows(self.key, self.view, self.query) if self.key != "data" else []
        self.selected = min(max(0, self.selected), max(0, len(rows) - 1))
        return rows

    def current(self, catalog: Catalog) -> dict[str, Any] | None:
        rows = self.rows(catalog)
        return rows[self.selected] if rows else None

    def switch(self, key: str) -> None:
        self.key, self.view, self.query, self.selected = key, 0, "", 0
        self.details, self.detail_scroll, self.form = False, 0, None


def _open_form(state: Workspace, catalog: Catalog, mode: str) -> None:
    row = state.current(catalog)
    if mode in {"edit", "delete"} and row is None:
        state.notice = "先选择一条记录。"
        return
    if mode in {"create", "edit"}:
        state.form = Form(mode, catalog.fields(state.key, mode == "edit"),
                          catalog.defaults(state.key, row if mode == "edit" else None),
                          row if mode == "edit" else None)
        if state.key == "grades" and mode == "edit":
            state.form.position = 1  # Go straight to the score, keeping its enrollment attached.
    elif mode in {"import", "export"}:
        state.form = Form(mode, (Field("path", "CSV 文件路径", True),), {"path": "data/students.csv"})
    else:
        state.form = Form(mode, original=row)
    state.notice = "更改尚未保存；点击字段或按 Enter 编辑，s 保存，q 取消。"
    state.detail_scroll = 0


def _apply_form(state: Workspace, catalog: Catalog) -> None:
    form = state.form
    if form is None:
        return
    if form.mode in {"create", "edit"}:
        record_id = catalog.save(state.key, form.values, form.original)
        # Preserve the active filter. If the record no longer matches, say so.
        rows = state.rows(catalog)
        state.selected = next((i for i, row in enumerate(rows) if row["id"] == record_id), state.selected)
        state.notice = "已保存。" if any(row["id"] == record_id for row in rows) else "已保存；这条记录不符合当前筛选条件。"
    elif form.mode == "delete":
        catalog.delete(state.key, form.original)
        state.notice = "记录已删除。"
    elif form.mode == "seed":
        from ..seed_data import seed_demo

        if any(catalog.records.values()):
            raise ValueError("已有校园记录，请使用空数据库体验演示校园。")
        seed_demo(catalog.service.db_path)
        catalog.refresh()
        state.notice = "演示校园已就绪，可浏览学生、课程和成绩。"
    else:
        path = Path(form.fields[0].parse(form.values.get("path"))).expanduser()
        if form.mode == "export":
            count = catalog.service.export_students(path)
            state.notice = f"已导出 {count} 名学生至 {path}"
        else:
            result = catalog.service.import_students(path)
            catalog.refresh()
            state.notice = f"已导入 {result.imported} 名学生；{len(result.errors)} 行未导入。"
            state.report = result.errors
            if result.errors:
                state.switch("data")
    state.form = None
    state.detail_scroll = 0


def _interact(state: Workspace, catalog: Catalog) -> tuple[str, int] | None:
    from .workspace_view import render

    previous: list[str] = []
    while True:
        frame = render(state, catalog)
        if frame.lines != previous:
            screen._paint(frame.lines, previous)
            previous = frame.lines
        key = keys._read_key(0.15)
        if isinstance(key, keys.MouseScroll):
            if not state.form and any(r.action == "focus-details" for r in frame.regions):
                state.details = any(r.action == "focus-details" and r.y == key.y
                                    and r.x <= key.x < r.x + r.width for r in frame.regions)
            key = key.direction
        if isinstance(key, screen.MouseClick):
            key = screen._hit_action(key, frame.regions)
        if not key:
            continue
        if key == "back" or key == "cancel":
            if state.form and state.form.options is not None:
                state.form.options = None
            elif state.form:
                state.form = None
                state.notice = "已取消，记录保持原样。"
            elif state.details:
                state.details = False
                state.detail_scroll = 0
            elif state.history:
                state.key, state.view, state.query, state.selected = state.history.pop()
                state.detail_scroll = 0
            else:
                return None
            continue
        if state.form:
            form = state.form
            if form.options is not None:
                if key in {"up", "down", "home", "end"}:
                    index = form.option_index + (-1 if key == "up" else 1)
                    if key == "home":
                        index = 0
                    elif key == "end":
                        index = len(form.options) - 1
                    form.option_index = min(max(0, index), max(0, len(form.options) - 1))
                elif key == "select" or key.startswith("option:"):
                    if form.options:
                        index = int(key.split(":")[1]) if key.startswith("option:") else form.option_index
                        form.values[form.fields[form.position].key] = form.options[index][0]
                        form.options = None
                        state.notice = "已选择；s 保存全部更改。"
                continue
            if key == "save":
                return "save", 0
            if key == "select" and state.form.fields:
                return "field", state.form.position
            if key.startswith("field:"):
                state.form.position = int(key.split(":")[1])
                return "field", state.form.position
            if key in {"up", "down", "home", "end"}:
                position = state.form.position + (-1 if key == "up" else 1)
                if key == "home":
                    position = 0
                elif key == "end":
                    position = len(state.form.fields) - 1
                state.form.position = min(max(0, position), max(0, len(state.form.fields) - 1))
            continue
        if key.startswith("navigate:"):
            path = key.removeprefix("navigate:")
            if not path:
                raise screen.NavigateTo("")
            if path == "教务":
                state.switch("departments")
            continue
        if key.startswith("collection:"):
            state.history.clear()
            state.switch(key.split(":")[1])
        elif key.startswith("related:"):
            _, collection, identifier = key.split(":")
            state.history.append((state.key, state.view, state.query, state.selected))
            state.switch(collection)
            state.selected = next((i for i, row in enumerate(state.rows(catalog)) if str(row["id"]) == identifier), 0)
        elif key.startswith("row:"):
            state.selected = int(key.split(":")[1])
            state.detail_scroll = 0
            state.details = screen._terminal_size().columns < 76
        elif key.startswith("edit-field:"):
            _open_form(state, catalog, "edit")
            field_key = key.split(":")[1]
            state.form.position = next(i for i, f in enumerate(state.form.fields) if f.key == field_key)
            return "field", state.form.position
        elif key == "focus-details":
            state.details = True
        elif key == "select" or key == "focus":
            state.details = not state.details
            state.detail_scroll = 0
        elif key in {"up", "down", "page_up", "page_down", "home", "end"}:
            amount = max(1, screen._terminal_size().lines - 11) if key.startswith("page_") else 1
            amount *= -1 if key in {"up", "page_up"} else 1
            if state.details or state.key == "data":
                state.detail_scroll = max(0, state.detail_scroll + amount)
                if key == "home":
                    state.detail_scroll = 0
                elif key == "end":
                    state.detail_scroll = 10**6  # Render clamps against the actual detail length.
            else:
                state.selected += amount
                if key == "home":
                    state.selected = 0
                elif key == "end":
                    state.selected = len(state.rows(catalog)) - 1
                state.detail_scroll = 0
        elif key.startswith("view:") or key in {"1", "2", "3", "4"}:
            index = int(key.split(":")[1]) if key.startswith("view:") else int(key) - 1
            if state.key == "data":
                state.switch(("students", "courses", "grades", "departments")[index])
            elif state.key in ACADEMICS and index < len(ACADEMICS):
                state.switch(ACADEMICS[index])
            elif state.key != "data" and index < len(COLLECTIONS[state.key].views):
                state.view, state.selected, state.detail_scroll = index, 0, 0
        elif key == "search" and state.key != "data":
            return "search", 0
        elif key == "reset-search":
            state.query, state.selected = "", 0
        elif key == "refresh":
            return "refresh", 0
        elif key in {"create", "edit", "delete"} and state.key != "data":
            _open_form(state, catalog, key)
        elif key in {"import", "export", "seed"}:
            _open_form(state, catalog, key)


def _read_value(state: Workspace, catalog: Catalog, event: tuple[str, int]) -> None:
    from .workspace_view import render, safe

    kind, index = event
    if kind == "search":
        label, current = "搜索姓名、编号、班级等", state.query
        state.notice = "支持多个关键词；留空清除筛选，Ctrl+C 取消。"
    else:
        field_ = state.form.fields[index]
        state.form.position = index
        options = catalog.options(state.key, field_.key) if state.form.mode in {"create", "edit"} else None
        if options is not None:
            state.form.options = options
            state.form.option_index = next((i for i, (value, _) in enumerate(options)
                                           if value == state.form.values.get(field_.key)), 0)
            state.notice = "选择已有记录；无需记住编号。"
            return
        label, current = field_.label, state.form.values.get(field_.key)
        state.notice = f"当前：{safe(current)} · 留空保持" + ("；输入 - 清空" if not field_.required else "") + "；Ctrl+C 取消"
    frame = render(state, catalog)
    screen._paint(frame.lines)
    height = len(frame.lines)
    # Native line input keeps IME/paste support and leaves the records on screen.
    screen.sys.stdout.write(f"\x1b[{max(1, height - 1)};1H")
    screen.sys.stdout.flush()
    with input_style(True):
        raw = read_input(screen._clip_cells(label, max(4, screen._terminal_size().columns - 8)) + " > ").strip()
    if kind == "search":
        state.query, state.selected, state.detail_scroll = raw, 0, 0
        state.notice = f"搜索：{raw}" if raw else "已显示全部记录。"
    elif raw:
        value = None if raw == "-" and not field_.required else raw
        state.form.values[field_.key] = field_.parse(value)
        state.notice = "字段已暂存；s 保存全部更改，q 取消。"


def run(db_path: Path | str | None, collection: str) -> None:
    catalog, state = Catalog(db_path), Workspace(collection)
    while True:
        try:
            with keys._mouse_tracking():
                event = _interact(state, catalog)
            if event is None:
                return
            if event[0] in {"field", "search"}:
                try:
                    _read_value(state, catalog, event)
                except KeyboardInterrupt:
                    state.notice = "已取消输入。"
            elif event[0] == "save":
                _apply_form(state, catalog)
            elif event[0] == "refresh":
                row = state.current(catalog)
                catalog.refresh()
                state.selected = next((i for i, r in enumerate(state.rows(catalog)) if row and r["id"] == row["id"]), 0)
                state.notice = "已刷新。"
        except KeyboardInterrupt:
            if state.form:
                state.form = None
                state.notice = "已取消编辑，记录保持原样。"
            else:
                return
        except (ValueError, sqlite3.Error, OSError) as error:
            state.notice = f"未完成：{error}"
