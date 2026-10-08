from __future__ import annotations

from pathlib import Path

from ...auth import INITIAL_STUDENT_PASSWORD
from ...student_query import parse_student_query
from ...terminal_input import input_style, read_inline_input
from .. import screen
from .data import Catalog, Field
from .presentation import CONFIRMATION_MODES
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

    return_to = state.capture_focus_context() if mode in CONFIRMATION_MODES else None
    if mode == "create":
        state.form = Form(mode, _create_fields(state, catalog), catalog.defaults(state.key))
    elif mode in {"import", "export"}:
        state.form = Form(mode, (Field("path", "CSV 文件路径", True),), {"path": "data/students.csv"})
    elif mode in CONFIRMATION_MODES:
        # All action-only confirmations begin on Cancel to absorb repeat Enter.
        state.form = Form(mode, original=row, return_to=return_to, position=1)
    else:
        state.form = Form(mode, original=row)

    state.field_session = None
    state.notice = ""
    if mode in CONFIRMATION_MODES:
        if state.key != "data":
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
    last = len(form.fields)  # Save follows the fields as an actual choice.
    if direction == "focus":
        form.position = (form.position + 1) % (last + 1)
    elif direction == "home":
        form.position = 0
    elif direction == "end":
        form.position = last
    elif direction == "up":
        form.position = max(0, form.position - 1)
    elif direction == "down":
        form.position = min(last, form.position + 1)


def apply_form(state: Workspace, catalog: Catalog) -> int | None:
    """Persist one transaction, then reconcile its selection and focus."""
    catalog.require_write()
    form = state.form
    if form is None:
        return None

    record_id: int | None = None
    deleting_position = state.selected

    if form.mode == "create":
        values = {field.key: form.values.get(field.key) for field in form.fields}
        record_id = catalog.save(state.key, values)
        rows = state.rows(catalog)
        created_index = next((i for i, row in enumerate(rows) if row["id"] == record_id), None)
        if created_index is not None:
            state.select_row(created_index)
        state.notice = (
            f"已保存。学生初始密码为 {INITIAL_STUDENT_PASSWORD}，首次登录必须修改。"
            if state.key == "students" and created_index is not None
            else "已保存。"
            if created_index is not None
            else "已保存；这条记录不符合当前筛选条件。"
        )
    elif form.mode == "reset-password":
        no = str(form.original["student_no"]).strip()
        catalog.service.reset_student_password(no)
        catalog.initial_password = None
        state.notice = f"已重置密码为 {INITIAL_STUDENT_PASSWORD}；学生下次登录必须修改密码。"
    elif form.mode == "delete":
        catalog.delete(state.key, form.original)
        state.notice = "记录已删除。"
    elif form.mode == "seed":
        catalog.service.seed_demo()
        catalog.refresh()
        state.notice = f"演示校园已就绪；学生初始密码为 {INITIAL_STUDENT_PASSWORD}。"
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
    state.field_session = None

    if form.mode in {"create", "delete", "seed", "import"}:
        state.reconcile_roster(len(state.rows(catalog)))

    created_visible = bool(
        form.mode == "create"
        and record_id is not None
        and any(row["id"] == record_id for row in state.rows(catalog))
    )
    if form.mode == "delete":
        # The next item now occupies the deleted row's position. At the end
        # of the roster, select the previous one; an empty roster has none.
        rows = state.rows(catalog)
        state.select_row(min(deleting_position, max(0, len(rows) - 1)))
        state.detail_scroll, state.detail_selected = 0, 0
        state.set_focus(FocusArea.ROSTER)
    elif created_visible:
        state.set_focus(FocusArea.INSPECTOR)
        state.detail_scroll, state.detail_selected = 0, 0
    else:
        state.set_focus(FocusArea.DASHBOARD if state.key == "data" else FocusArea.ROSTER)
        state.detail_scroll, state.detail_selected = 0, 0

    return record_id


def read_search(state: Workspace, catalog: Catalog) -> None:
    """Edit the real footer cell; commit only after Enter and query validation."""
    from .view import render, search_input_geometry

    state.searching = True
    try:
        frame = render(state, catalog)
        screen._paint(frame.lines)
        column, field_width = search_input_geometry(screen._display_width(frame.lines[-1]))
        with input_style(True):
            raw = read_inline_input(
                "搜索：", row=len(frame.lines), column=column, width=field_width,
                initial_value=state.query,
            ).strip()

        if state.key == "students":
            try:
                parse_student_query(raw)
            except ValueError as exc:
                state.notice = f"未完成：{exc}"
                return
        state.commit_search(raw)
        state.notice = f"搜索：{raw}" if raw else "已显示全部记录。"
    finally:
        state.searching = False
