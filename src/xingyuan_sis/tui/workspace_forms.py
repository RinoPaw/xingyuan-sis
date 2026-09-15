from __future__ import annotations

from pathlib import Path

from ..student_query import parse_student_query
from ..terminal_input import input_style, read_inline_input, read_input
from . import screen
from .view_common import safe
from .workspace_data import Catalog, Field
from .workspace_state import Form, Workspace


_STUDENT_EDIT_ROWS: tuple[tuple[str, ...], ...] = (
    ("name",),
    ("student_no",),
    ("family", "branch"),
    ("enrollment_year",),
    ("class_code",),
    ("status",),
    ("primary_element", "primary_affinity"),
    ("gender",),
    ("birth_date",),
    ("contact",),
    ("dormitory",),
    ("notes",),
)


def open_form(state: Workspace, catalog: Catalog, mode: str) -> None:
    row = state.current(catalog)
    if mode in {"edit", "delete"} and row is None:
        state.notice = "先选择一条记录。"
        return
    if mode in {"create", "edit"}:
        state.form = Form(
            mode,
            catalog.fields(state.key, mode == "edit"),
            catalog.defaults(state.key, row if mode == "edit" else None),
            row if mode == "edit" else None,
        )
        if mode == "edit" and state.key in {"students", "grades"}:
            state.form.position = 1
    elif mode in {"import", "export"}:
        state.form = Form(mode, (Field("path", "CSV 文件路径", True),), {"path": "data/students.csv"})
    else:
        state.form = Form(mode, original=row)
    state.notice = "更改尚未保存。Esc 取消。"
    state.detail_scroll = 0


def _move_linear_form_position(form: Form, direction: str) -> None:
    if not form.fields:
        return
    if direction == "home":
        form.position = 0
    elif direction == "end":
        form.position = len(form.fields) - 1
    elif direction == "up":
        form.position = max(0, form.position - 1)
    elif direction == "down":
        form.position = min(len(form.fields) - 1, form.position + 1)


def move_form_position(state: Workspace, direction: str) -> None:
    """Move form focus according to the rendered geometry when one exists."""
    form = state.form
    if form is None or not form.fields:
        return
    if form.mode != "edit" or state.key != "students":
        _move_linear_form_position(form, direction)
        return

    positions = {field.key: index for index, field in enumerate(form.fields)}
    rows = [tuple(key for key in row if key in positions) for row in _STUDENT_EDIT_ROWS]
    rows = [row for row in rows if row]
    current_key = form.fields[form.position].key
    location = next(
        ((row_index, row.index(current_key)) for row_index, row in enumerate(rows) if current_key in row),
        None,
    )
    if location is None:
        _move_linear_form_position(form, direction)
        return

    row_index, column_index = location
    if direction == "home":
        target = rows[0][0]
    elif direction == "end":
        target = rows[-1][-1]
    elif direction == "left":
        if column_index == 0:
            return
        target = rows[row_index][column_index - 1]
    elif direction == "right":
        if column_index + 1 >= len(rows[row_index]):
            return
        target = rows[row_index][column_index + 1]
    elif direction in {"up", "down"}:
        next_row = row_index + (-1 if direction == "up" else 1)
        if not 0 <= next_row < len(rows):
            return
        target_row = rows[next_row]
        target = target_row[min(column_index, len(target_row) - 1)]
    else:
        return
    form.position = positions[target]


def apply_form(state: Workspace, catalog: Catalog) -> None:
    form = state.form
    if form is None:
        return
    if form.mode in {"create", "edit"}:
        record_id = catalog.save(state.key, form.values, form.original)
        rows = state.rows(catalog)
        state.selected = next((i for i, row in enumerate(rows) if row["id"] == record_id), state.selected)
        state.notice = (
            "已保存。"
            if any(row["id"] == record_id for row in rows)
            else "已保存；这条记录不符合当前筛选条件。"
        )
    elif form.mode == "delete":
        catalog.delete(state.key, form.original)
        state.notice = "记录已删除。"
    elif form.mode == "seed":
        from ..auth import DEMO_STUDENT_PASSWORD, provision_demo_passwords
        from ..seed_data import seed_demo

        if any(catalog.records.values()):
            raise ValueError("已有校园记录，请使用空数据库体验演示校园。")
        seed_demo(catalog.service.db_path)
        provision_demo_passwords(catalog.service.db_path)
        catalog.refresh()
        state.notice = f"演示校园已就绪；学生初始密码为 {DEMO_STUDENT_PASSWORD}。"
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


def _inline_field_geometry(
    frame: screen.ScreenFrame,
    index: int,
    *,
    direct: bool = False,
) -> tuple[int, int, int]:
    region = next(region for region in frame.regions if region.action == f"field:{index}")
    if direct:
        return region.y, region.x, max(1, region.width)
    label_width = min(12, max(4, region.width // 3))
    value_column = region.x + label_width + 2
    value_width = max(1, region.width - label_width - 2)
    return region.y, value_column, value_width


def read_value(state: Workspace, catalog: Catalog, event: tuple[str, int]) -> None:
    from .workspace_view import render

    kind, index = event
    if kind == "search":
        if state.key == "students":
            label = "搜索（可用 --name、--class、--year 等）"
            state.notice = "学生搜索与 xy stu ls 使用同一套查询条件。Esc 取消。"
        else:
            label = "搜索姓名、编号、班级等"
            state.notice = "支持多个关键词。Esc 取消。"
        current = state.query

        frame = render(state, catalog)
        screen._paint(frame.lines)
        height = len(frame.lines)
        screen.sys.stdout.write(f"\x1b[{max(1, height - 1)};1H")
        screen.sys.stdout.flush()
        with input_style(True):
            raw = read_input(
                screen._clip_cells(label, max(4, screen._terminal_size().columns - 8)) + " > ",
                initial_value=current,
            ).strip()

        if state.key == "students":
            try:
                parse_student_query(raw)
            except ValueError as exc:
                state.notice = f"未完成：{exc}"
                return
        state.query, state.selected, state.roster_scroll = raw, 0, 0
        state.detail_scroll, state.detail_selected = 0, 0
        state.notice = f"搜索：{raw}" if raw else "已显示全部记录。"
        return

    field_ = state.form.fields[index]
    state.form.position = index
    options = catalog.options(state.key, field_.key, state.form.values) if state.form.mode in {"create", "edit"} else None
    if options is not None:
        state.form.options = options
        state.form.option_index = next(
            (i for i, (value, _) in enumerate(options) if value == state.form.values.get(field_.key)),
            0,
        )
        state.notice = "↑↓ 选择，Enter 暂存。Esc 取消。"
        return

    current = state.form.values.get(field_.key)
    state.notice = (
        "直接在当前字段修改 · Enter 暂存"
        + (" · 清空后 Enter 可置空" if not field_.required else "")
        + " · Esc 取消"
    )
    frame = render(state, catalog)
    screen._paint(frame.lines)
    row, column, width = _inline_field_geometry(
        frame,
        index,
        direct=state.form.mode == "edit" and state.key == "students",
    )
    with input_style(True):
        raw = read_inline_input(
            f"{field_.label} > ",
            row=row,
            column=column,
            width=width,
            initial_value="" if current is None else str(current),
        ).strip()

    value = field_.parse(raw if raw else None)
    state.form.values[field_.key] = value
    state.notice = "字段已暂存。Esc 取消。"
