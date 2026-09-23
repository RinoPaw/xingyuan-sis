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


def apply_form(state: Workspace, catalog: Catalog) -> int | None:
    """Apply one transaction; visual effects are consequences of committed mutations."""
    catalog.require_write()
    form = state.form
    if form is None:
        return None

    from .roster_effects import capture_student_roster_effect, play_student_roster_effect

    record_id: int | None = None
    deleting_position: int | None = None
    delete_effect = None

    if form.mode == "create":
        values = {field.key: form.values.get(field.key) for field in form.fields}
        record_id = catalog.save(state.key, values)
        state.roster_gap = None
        rows = state.rows(catalog)
        created_index = next((i for i, row in enumerate(rows) if row["id"] == record_id), None)
        if created_index is not None:
            state.select_row(created_index)
        state.notice = (
            "已保存。学生初始密码为学号，首次登录必须修改。"
            if state.key == "students" and created_index is not None
            else "已保存。"
            if created_index is not None
            else "已保存；这条记录不符合当前筛选条件。"
        )
    elif form.mode == "reset-password":
        no = str(form.original["student_no"]).strip()
        catalog.service.reset_student_password(no, no)
        catalog.initial_password = None
        state.notice = "已重置密码为学号；学生下次登录必须修改密码。"
    elif form.mode == "delete":
        if state.key == "students":
            deleting_position = state.selected
            # Capture presentation while the record still exists, but do not
            # play anything until persistence succeeds. A failed delete must
            # never visually burn a record that remains in the database.
            delete_effect = capture_student_roster_effect(
                state,
                catalog,
                int(form.original["id"]),
                "burn",
            )
        catalog.delete(state.key, form.original)
        state.notice = "记录已删除。"
    elif form.mode == "seed":
        from ...auth import DEMO_STUDENT_PASSWORD

        if any(catalog.records.values()):
            raise ValueError("已有校园记录，请使用空数据库体验演示校园。")
        catalog.service.seed_demo()
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
    state.field_session = None

    created_visible = bool(
        form.mode == "create"
        and record_id is not None
        and any(row["id"] == record_id for row in state.rows(catalog))
    )
    if form.mode == "delete":
        if state.key == "students" and deleting_position is not None:
            rows = state.rows(catalog)
            state.leave_roster_gap(min(deleting_position, len(rows)))
        else:
            if state.key != "data":
                state.rows(catalog)
            state.restore_focus_context(form.return_to)
    elif created_visible:
        state.set_focus(FocusArea.INSPECTOR)
        state.detail_scroll, state.detail_selected = 0, 0
    else:
        state.set_focus(FocusArea.DASHBOARD if state.key == "data" else FocusArea.ROSTER)
        state.detail_scroll, state.detail_selected = 0, 0

    # Effects are dispatched from the successful mutation result, not from a
    # button or shortcut path. Any UI route that reaches this transaction gets
    # exactly the same visual consequence.
    if form.mode == "delete" and delete_effect is not None:
        play_student_roster_effect(delete_effect)
    elif state.key == "students" and form.mode == "create" and record_id is not None and created_visible:
        create_effect = capture_student_roster_effect(state, catalog, record_id, "print")
        play_student_roster_effect(create_effect)

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
    state.roster_gap = None
    state.detail_scroll, state.detail_selected = 0, 0
    state.notice = f"搜索：{raw}" if raw else "已显示全部记录。"
