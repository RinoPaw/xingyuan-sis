from __future__ import annotations

import sqlite3
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Input, Select, Static

from .repository import Repository


def _show(value: Any) -> str:
    return "" if value is None else str(value)


def _required_int(value: str, field: str) -> int:
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field}需要填写整数") from exc


def _required_float(value: str, field: str) -> float:
    try:
        return float(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field}需要填写数字") from exc


def _course_by_id(repository: Repository, course_id: int) -> Any | None:
    return next(
        (row for row in repository.list_courses() if int(row["id"]) == course_id),
        None,
    )


class CoursesPage(VerticalScroll):
    DEFAULT_CSS = """
    CoursesPage {
        padding: 2 3;
    }

    #courses-header {
        height: auto;
        margin-bottom: 2;
    }

    #courses-header > Vertical {
        width: 1fr;
        height: auto;
    }

    #course-new {
        width: 14;
        height: 3;
        margin-top: 1;
        background: #162435;
        color: #9fd3ff;
        border: none;
    }

    #course-search {
        width: 1fr;
        height: 3;
        margin-bottom: 1;
        background: #10141a;
        border: none;
    }

    #courses-table {
        height: 1fr;
        border-top: solid #1b222c;
    }

    #courses-hint {
        height: 2;
        padding-top: 1;
        color: #59636f;
    }

    CourseDetailScreen {
        background: #0b0d10;
        padding: 2 4;
    }

    #course-detail-breadcrumb {
        height: 2;
        color: #626c78;
    }

    #course-detail-heading-row {
        height: auto;
        margin-bottom: 2;
    }

    #course-detail-heading-row > Vertical {
        width: 1fr;
        height: auto;
    }

    #course-detail-heading {
        height: auto;
        color: #f0f4f8;
        text-style: bold;
    }

    #course-detail-meta {
        height: auto;
        color: #707a87;
    }

    #course-detail-actions {
        width: auto;
        height: 3;
    }

    #course-detail-actions Button {
        width: auto;
        min-width: 8;
        height: 3;
        margin-left: 1;
        background: transparent;
        border: none;
        color: #9aa4b1;
    }

    #course-detail-delete {
        color: #d98989;
    }

    #course-roster-title {
        height: auto;
        margin: 1 0;
        color: #8d98a6;
        text-style: bold;
    }

    #course-roster {
        height: 1fr;
        border-top: solid #1b222c;
    }

    #course-detail-hint {
        height: 2;
        padding-top: 1;
        color: #59636f;
    }

    CourseEditScreen {
        background: #0b0d10;
        padding: 2 4;
    }

    #course-edit-heading {
        height: auto;
        color: #f0f4f8;
        text-style: bold;
    }

    #course-edit-subtitle {
        height: auto;
        color: #6f7885;
        margin-bottom: 2;
    }

    #course-edit-form {
        height: 1fr;
        max-width: 72;
    }

    .course-field-row {
        height: 3;
        margin-bottom: 1;
    }

    .course-field-label {
        width: 12;
        height: 3;
        content-align: left middle;
        color: #7c8794;
    }

    .course-field-row Input,
    .course-field-row Select {
        width: 1fr;
        height: 3;
        background: #10141a;
        border: none;
    }

    #course-edit-actions {
        height: 4;
        max-width: 72;
        align-horizontal: right;
        border-top: solid #1c2129;
        padding-top: 1;
    }

    #course-edit-actions Button {
        width: 10;
        height: 3;
        margin-left: 1;
        background: transparent;
        border: none;
        color: #8d98a6;
    }

    #course-edit-save {
        background: #162435;
        color: #9fd3ff;
    }

    CourseDeleteScreen {
        align: center middle;
        background: #000000 60%;
    }

    #course-delete-dialog {
        width: 52;
        height: auto;
        padding: 1 2;
        background: #11161d;
        border: solid #2a313b;
    }

    #course-delete-title {
        height: auto;
        color: #f0f4f8;
        text-style: bold;
        margin-bottom: 1;
    }

    #course-delete-message {
        height: auto;
        color: #87919d;
        margin-bottom: 2;
    }

    #course-delete-actions {
        height: 3;
        align-horizontal: right;
    }

    #course-delete-actions Button {
        width: 10;
        height: 3;
        margin-left: 1;
        border: none;
    }

    #course-delete-confirm {
        background: transparent;
        color: #e29292;
    }
    """

    def __init__(self, repository: Repository, *, id: str) -> None:
        super().__init__(id=id)
        self.repository = repository
        self._course_ids: list[int] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="courses-header"):
            with Vertical():
                yield Static("课程", classes="page-title")
                yield Static("浏览课程、选课学生与成绩", classes="page-subtitle")
            yield Button("+ 新建课程", id="course-new")

        yield Input(
            placeholder="搜索课程编号、名称或学院…",
            id="course-search",
        )
        yield DataTable(id="courses-table", cursor_type="row")
        yield Static("↑↓ 选择   Enter 查看   / 搜索", id="courses-hint")

    def on_mount(self) -> None:
        table = self.query_one("#courses-table", DataTable)
        table.add_columns("编号", "课程", "学院", "学分", "课时")
        self.refresh_table()

    def refresh_table(self, keyword: str = "") -> None:
        keyword = keyword.strip().lower()
        rows = self.repository.list_courses()
        if keyword:
            rows = [
                row
                for row in rows
                if keyword
                in " ".join(
                    (
                        _show(row["course_code"]),
                        _show(row["name"]),
                        _show(row["department_name"]),
                    )
                ).lower()
            ]

        self._course_ids = [int(row["id"]) for row in rows]
        table = self.query_one("#courses-table", DataTable)
        table.clear()
        for row in rows:
            table.add_row(
                _show(row["course_code"]),
                _show(row["name"]),
                _show(row["department_name"]) or "—",
                _show(row["credits"]),
                _show(row["hours"]),
            )

    def _refresh_after_change(self, changed: bool | None) -> None:
        if changed:
            self.refresh_table(self.query_one("#course-search", Input).value)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "course-search":
            self.refresh_table(event.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "courses-table":
            return
        if not (0 <= event.cursor_row < len(self._course_ids)):
            return
        self.app.push_screen(
            CourseDetailScreen(
                self.repository,
                self._course_ids[event.cursor_row],
            ),
            self._refresh_after_change,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "course-new":
            self.app.push_screen(
                CourseEditScreen(self.repository),
                self._refresh_after_change,
            )


class CourseDetailScreen(Screen[bool]):
    BINDINGS = [("escape", "close", "返回")]

    def __init__(self, repository: Repository, course_id: int) -> None:
        super().__init__()
        self.repository = repository
        self.course_id = course_id
        self.changed = False

    def compose(self) -> ComposeResult:
        course = _course_by_id(self.repository, self.course_id)
        if course is None:
            yield Static("这门课程已经不存在。")
            return

        yield Static(
            f"课程 / {_show(course['course_code'])}",
            id="course-detail-breadcrumb",
        )
        with Horizontal(id="course-detail-heading-row"):
            with Vertical():
                yield Static(_show(course["name"]), id="course-detail-heading")
                yield Static(self._meta_text(course), id="course-detail-meta")
            with Horizontal(id="course-detail-actions"):
                yield Button("编辑", id="course-detail-edit")
                yield Button("删除课程…", id="course-detail-delete")

        yield Static("学生与成绩", id="course-roster-title")
        yield DataTable(id="course-roster")
        yield Static("Esc 返回", id="course-detail-hint")

    def on_mount(self) -> None:
        try:
            table = self.query_one("#course-roster", DataTable)
        except Exception:
            return
        table.add_columns("学号", "姓名", "学期", "成绩")
        self._refresh_roster()

    def _refresh_roster(self) -> None:
        table = self.query_one("#course-roster", DataTable)
        table.clear()
        for row in self.repository.list_enrollments():
            if int(row["course_id"]) != self.course_id:
                continue
            table.add_row(
                _show(row["student_no"]),
                _show(row["student_name"]),
                _show(row["semester"]),
                _show(row["score"]) or "—",
            )

    def _meta_text(self, course: Any) -> str:
        return "  ·  ".join(
            value
            for value in (
                _show(course["department_name"]),
                f"{_show(course['credits'])} 学分",
                f"{_show(course['hours'])} 课时",
            )
            if value
        )

    def action_close(self) -> None:
        self.dismiss(self.changed)

    def _refresh_after_edit(self, changed: bool | None) -> None:
        if not changed:
            return
        self.changed = True
        course = _course_by_id(self.repository, self.course_id)
        if course is None:
            return
        self.query_one("#course-detail-breadcrumb", Static).update(
            f"课程 / {_show(course['course_code'])}"
        )
        self.query_one("#course-detail-heading", Static).update(_show(course["name"]))
        self.query_one("#course-detail-meta", Static).update(self._meta_text(course))
        self._refresh_roster()

    def _after_delete(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            self.repository.delete_course(self.course_id)
        except sqlite3.Error as error:
            self.app.notify(str(error), title="删除失败", severity="error")
            return
        self.app.notify("课程已删除")
        self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "course-detail-edit":
            self.app.push_screen(
                CourseEditScreen(self.repository, self.course_id),
                self._refresh_after_edit,
            )
        elif event.button.id == "course-detail-delete":
            course = _course_by_id(self.repository, self.course_id)
            name = _show(course["name"]) if course else "这门课程"
            self.app.push_screen(CourseDeleteScreen(name), self._after_delete)


class CourseEditScreen(Screen[bool]):
    BINDINGS = [("escape", "cancel", "取消")]

    def __init__(self, repository: Repository, course_id: int | None = None) -> None:
        super().__init__()
        self.repository = repository
        self.course_id = course_id
        self.record = (
            _course_by_id(repository, course_id)
            if course_id is not None
            else None
        )

    def compose(self) -> ComposeResult:
        yield Static(
            "编辑课程" if self.record is not None else "新建课程",
            id="course-edit-heading",
        )
        yield Static(
            "填写课程信息，完成后保存。",
            id="course-edit-subtitle",
        )

        with VerticalScroll(id="course-edit-form"):
            yield from self._input_row("编号", "course-edit-code", "course_code")
            yield from self._input_row("课程名称", "course-edit-name", "name")

            with Horizontal(classes="course-field-row"):
                yield Static("开课学院", classes="course-field-label")
                options = [
                    (row["name"], int(row["id"]))
                    for row in self.repository.list_departments()
                ]
                value: Any = Select.NULL
                if self.record is not None and self.record["department_id"] is not None:
                    value = int(self.record["department_id"])
                yield Select(
                    options,
                    prompt="未指定",
                    allow_blank=True,
                    value=value,
                    id="course-edit-department",
                )

            yield from self._input_row("学分", "course-edit-credits", "credits")
            yield from self._input_row("课时", "course-edit-hours", "hours")

        with Horizontal(id="course-edit-actions"):
            yield Button("取消", id="course-edit-cancel")
            yield Button("保存", id="course-edit-save")

    def _input_row(self, label: str, widget_id: str, column: str):
        value = ""
        if self.record is not None:
            value = _show(self.record[column])
        with Horizontal(classes="course-field-row"):
            yield Static(label, classes="course-field-label")
            yield Input(value=value, id=widget_id)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "course-edit-cancel":
            self.dismiss(False)
            return
        if event.button.id != "course-edit-save":
            return

        code = self.query_one("#course-edit-code", Input).value.strip()
        name = self.query_one("#course-edit-name", Input).value.strip()
        if not code or not name:
            self.app.notify("编号和课程名称需要填写", title="无法保存", severity="error")
            return

        department = self.query_one("#course-edit-department", Select)
        department_id = None if department.is_blank() else int(department.value)

        try:
            values = (
                code,
                name,
                department_id,
                _required_float(
                    self.query_one("#course-edit-credits", Input).value,
                    "学分",
                ),
                _required_int(
                    self.query_one("#course-edit-hours", Input).value,
                    "课时",
                ),
            )
            if self.course_id is None:
                self.repository.add_course(*values)
            else:
                self.repository.update_course(self.course_id, *values)
        except sqlite3.IntegrityError:
            self.app.notify("课程编号已存在。", title="无法保存", severity="error")
            return
        except (sqlite3.Error, ValueError) as error:
            self.app.notify(str(error), title="无法保存", severity="error")
            return

        self.app.notify("课程已保存")
        self.dismiss(True)


class CourseDeleteScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "取消")]

    def __init__(self, course_name: str) -> None:
        super().__init__()
        self.course_name = course_name

    def compose(self) -> ComposeResult:
        with Vertical(id="course-delete-dialog"):
            yield Static("删除课程？", id="course-delete-title")
            yield Static(
                f"{self.course_name} 及相关选课记录将被删除。",
                id="course-delete-message",
            )
            with Horizontal(id="course-delete-actions"):
                yield Button("取消", id="course-delete-cancel")
                yield Button("删除", id="course-delete-confirm")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "course-delete-confirm":
            self.dismiss(True)
        elif event.button.id == "course-delete-cancel":
            self.dismiss(False)
