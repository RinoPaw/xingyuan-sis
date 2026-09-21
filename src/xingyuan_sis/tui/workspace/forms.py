from __future__ import annotations

from pathlib import Path

from ...student_query import parse_student_query
from ...terminal_input import input_style, read_input
from .. import screen
from .data import Catalog, Field
from .state import FocusArea, Form, Workspace
from .student_layout import order_fields as order_student_fields


def _create_fields(state: Workspace, catalog: Catalog) -> tuple[Field, ...]:
    fields = catalog.fields(state.key)
    return order_student_fields(fields) if state.key == "students" else fields


def open_form(state: Workspace, catalog: Catalog, mode: str) -> None:
    """Open a transaction and make its focus transition explicit."""
    catalog.require_write()
    if mode == "edit":
        raise ValueError("已有记录请在档案字段上直接修改。")

    row = state.current(catalog)
    if mode in {"delete", "reset-password"} and row is None:
        state.notice = "先选择一条记录。"
        return

    return_to = state.capture_focus_context() if mode == "delete" else None
    if mode == "create":
        state.form = Form(mode, _create_fields(state, catalog), catalog.defaults(state.key))
    elif mode in {"import", "export"}:
        state.form = Form(mode, (Field("path", "CSV 文件路径", True),), {"path": "data/students.csv"})
    elif mode == "delete":
        state.form = Form(mode, original=row, return_to=return_to)
    else:
        state.form = Form(mode, original=row)

    state.field_session = None
    state.notice = ""
    if mode == "delete":
        state.set_focus(FocusArea.INSPECTOR)
    else:
        state.focus_content()
        state.detail_scroll = 0


def cancel_form(state: Workspace) -> None:
    """Close a transaction and restore any context explicitly owned by it."""
    form = state.form
    state.form = None
    state.field_session = None
    if form is not None:
        state.restore_focus_context(form.return_to)
    state.notice = "已取消，记录保持原样。"


def move_form_position(state: Workspace, direction: str) -> None:
    """Move the selected transaction field without entering edit state."""
    form = state.form
    if form is None or not form.fields:
        return
    if direction == "focus":
        form.position = (form.position + 1) % len(form.fields)
    elif direction == "home":
        form.position = 0
    elif direction == "end":
        form.position = len(form.fields) - 1
    elif direction == "up":
        form.position = max(0, form.position - 1)
    elif direction == "down":
        form.position = min(len(form.fields) - 1, form.position + 1)


def _use_student_number_as_password(catalog: Catalog, student_no: object) -> None:
    """Apply the TUI's predictable first-login credential policy."""
    from ...auth import reset_student_password

    no = str(student_no).strip()
    reset_student_password(catalog.service.db_path, no, no)
    catalog.initial_password = None


def apply_form(state: Workspace, catalog: Catalog) -> int | None:
    """Apply the current transaction and return a created record id, if any."""
    catalog.require_write()
    form = state.form
    if form is None:
        return None

    record_id: int | None = None
    if form.mode == "create":
        values = {field.key: form.values.get(field.key) for field in form.fields}
        record_id = catalog.save(state.key, values)
        if state.key == "students":
            _use_student_number_as_password(catalog, form.values["student_no"])
        rows = state.rows(catalog)
        state.selected = next((i for i, row in enumerate(rows) if row["id"] == record_id), state.selected)
        state.notice = (
            "已保存。学生初始密码为学号，首次登录必须修改。"
            if state.key == "students" and any(row["id"] == record_id for row in rows)
            else "已保存。"
            if any(row["id"] == record_id for row in rows)
            else "已保存；这条记录不符合当前筛选条件。"
        )
    elif form.mode == "reset-password":
        no = form.original["student_no"]
        _use_student_number_as_password(catalog, no)
        state.notice = "已重置密码为学号；学生下次登录必须修改密码。"
    elif form.mode == "delete":
        catalog.delete(state.key, form.original)
        state.notice = "记录已删除。"
    elif form.mode == "seed":
        from ...auth import DEMO_STUDENT_PASSWORD, provision_demo_passwords
        from ...seed_data import seed_demo

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
            for student_no, _ in result.credentials:
                _use_student_number_as_password(catalog, student_no)
            catalog.refresh()
            state.notice = f"已导入 {result.imported} 名学生；{len(result.errors)} 行未导入。"
            state.report = result.errors
            if result.errors:
                state.switch("data")

    state.form = None
    state.field_session = None
    if form.mode == "delete":
        if state.key != "data":
            state.rows(catalog)
        if state.key == "students":
            state.set_focus(FocusArea.ROSTER)
            state.detail_scroll, state.detail_selected = 0, 0
        else:
            state.restore_focus_context(form.return_to)
    elif form.mode == "create" and record_id is not None and any(
        row["id"] == record_id for row in state.rows(catalog)
    ):
        state.set_focus(FocusArea.ROSTER if state.key == "students" else FocusArea.INSPECTOR)
        state.detail_scroll, state.detail_selected = 0, 0
    else:
        state.set_focus(FocusArea.DASHBOARD if state.key == "data" else FocusArea.ROSTER)
        state.detail_scroll, state.detail_selected = 0, 0

    return record_id


def read_search(state: Workspace, catalog: Catalog) -> None:
    """Read the workspace search query; transaction fields use FieldSession."""
    from .view import render

    # Search filters the roster; its input must not inherit inspector selection.
    state.set_focus(FocusArea.ROSTER)
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
