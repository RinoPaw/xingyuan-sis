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


def _score(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        score = float(value)
    except ValueError as exc:
        raise ValueError("成绩需要填写数字") from exc
    if not 0 <= score <= 100:
        raise ValueError("成绩需要在 0 到 100 之间")
    return score


def _enrollment_by_id(repository: Repository, enrollment_id: int) -> Any | None:
    return next(
        (
            row
            for row in repository.list_enrollments()
            if int(row["id"]) == enrollment_id
        ),
        None,
    )


class GradesPage(VerticalScroll):
    DEFAULT_CSS = """
    GradesPage {
        padding: 2 3;
    }

    #grades-header {
        height: auto;
        margin-bottom: 2;
    }

    #grades-header > Vertical {
        width: 1fr;
        height: auto;
    }

    #grade-new {
        width: 14;
        height: 3;
        margin-top: 1;
        background: #162435;
        color: #9fd3ff;
        border: none;
    }

    #grade-search {
        width: 1fr;
        height: 3;
        margin-bottom: 1;
        background: #10141a;
        border: none;
    }

    #grades-table {
        height: 1fr;
        border-top: solid #1b222c;
    }

    #grades-hint {
        height: 2;
        padding-top: 1;
        color: #59636f;
    }

    GradeEditScreen {
        background: #0b0d10;
        padding: 2 4;
    }

    #grade-edit-heading {
        height: auto;
        color: #f0f4f8;
        text-style: bold;
    }

    #grade-edit-subtitle {
        height: auto;
        color: #6f7885;
        margin-bottom: 2;
    }

    #grade-edit-form {
        height: 1fr;
        max-width: 72;
    }

    .grade-field-row {
        height: 3;
        margin-bottom: 1;
    }

    .grade-field-label {
        width: 12;
        height: 3;
        content-align: left middle;
        color: #7c8794;
    }

    .grade-field-row Input,
    .grade-field-row Select {
        width: 1fr;
        height: 3;
        background: #10141a;
        border: none;
    }

    .grade-readonly {
        width: 1fr;
        height: 3;
        content-align: left middle;
        color: #c2cad4;
    }

    #grade-edit-actions {
        height: 4;
        max-width: 72;
        border-top: solid #1c2129;
        padding-top: 1;
    }

    #grade-edit-actions-spacer {
        width: 1fr;
    }

    #grade-edit-actions Button {
        width: 10;
        height: 3;
        margin-left: 1;
        background: transparent;
        border: none;
        color: #8d98a6;
    }

    #grade-edit-delete {
        color: #d98989;
        margin-left: 0;
    }

    #grade-edit-save {
        background: #162435;
        color: #9fd3ff;
    }

    GradeDeleteScreen {
        align: center middle;
        background: #000000 60%;
    }

    #grade-delete-dialog {
        width: 52;
        height: auto;
        padding: 1 2;
        background: #11161d;
        border: solid #2a313b;
    }

    #grade-delete-title {
        height: auto;
        color: #f0f4f8;
        text-style: bold;
        margin-bottom: 1;
    }

    #grade-delete-message {
        height: auto;
        color: #87919d;
        margin-bottom: 2;
    }

    #grade-delete-actions {
        height: 3;
        align-horizontal: right;
    }

    #grade-delete-actions Button {
        width: 10;
        height: 3;
        margin-left: 1;
        border: none;
    }

    #grade-delete-confirm {
        background: transparent;
        color: #e29292;
    }
    """

    def __init__(self, repository: Repository, *, id: str) -> None:
        super().__init__(id=id)
        self.repository = repository
        self._enrollment_ids: list[int] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="grades-header"):
            with Vertical():
                yield Static("成绩", classes="page-title")
                yield Static("按学生或课程查找，集中录入成绩", classes="page-subtitle")
            yield Button("+ 添加选课", id="grade-new")

        yield Input(
            placeholder="搜索学号、姓名、课程或学期…",
            id="grade-search",
        )
        yield DataTable(id="grades-table", cursor_type="row")
        yield Static("↑↓ 选择   Enter 编辑   / 搜索", id="grades-hint")

    def on_mount(self) -> None:
        table = self.query_one("#grades-table", DataTable)
        table.add_columns("学号", "姓名", "课程", "学期", "成绩")
        self.refresh_table()

    def refresh_table(self, keyword: str = "") -> None:
        keyword = keyword.strip().lower()
        rows = self.repository.list_enrollments()
        if keyword:
            rows = [
                row
                for row in rows
                if keyword
                in " ".join(
                    (
                        _show(row["student_no"]),
                        _show(row["student_name"]),
                        _show(row["course_code"]),
                        _show(row["course_name"]),
                        _show(row["semester"]),
                    )
                ).lower()
            ]

        self._enrollment_ids = [int(row["id"]) for row in rows]
        table = self.query_one("#grades-table", DataTable)
        table.clear()
        for row in rows:
            table.add_row(
                _show(row["student_no"]),
                _show(row["student_name"]),
                _show(row["course_name"]),
                _show(row["semester"]),
                _show(row["score"]) or "—",
            )

    def _refresh_after_change(self, changed: bool | None) -> None:
        if changed:
            self.refresh_table(self.query_one("#grade-search", Input).value)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "grade-search":
            self.refresh_table(event.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "grades-table":
            return
        if not (0 <= event.cursor_row < len(self._enrollment_ids)):
            return
        self.app.push_screen(
            GradeEditScreen(
                self.repository,
                self._enrollment_ids[event.cursor_row],
            ),
            self._refresh_after_change,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "grade-new":
            self.app.push_screen(
                GradeEditScreen(self.repository),
                self._refresh_after_change,
            )


class GradeEditScreen(Screen[bool]):
    BINDINGS = [("escape", "cancel", "取消")]

    def __init__(
        self,
        repository: Repository,
        enrollment_id: int | None = None,
    ) -> None:
        super().__init__()
        self.repository = repository
        self.enrollment_id = enrollment_id
        self.record = (
            _enrollment_by_id(repository, enrollment_id)
            if enrollment_id is not None
            else None
        )

    def compose(self) -> ComposeResult:
        yield Static(
            "编辑成绩" if self.record is not None else "添加选课",
            id="grade-edit-heading",
        )
        yield Static(
            "成绩可以暂时留空，之后再补录。",
            id="grade-edit-subtitle",
        )

        with VerticalScroll(id="grade-edit-form"):
            if self.record is None:
                with Horizontal(classes="grade-field-row"):
                    yield Static("学生", classes="grade-field-label")
                    student_options = [
                        (
                            f"{row['student_no']} · {row['name']}",
                            int(row["id"]),
                        )
                        for row in self.repository.list_students()
                    ]
                    yield Select(
                        student_options,
                        prompt="选择学生",
                        allow_blank=False,
                        id="grade-edit-student",
                    )

                with Horizontal(classes="grade-field-row"):
                    yield Static("课程", classes="grade-field-label")
                    course_options = [
                        (
                            f"{row['course_code']} · {row['name']}",
                            int(row["id"]),
                        )
                        for row in self.repository.list_courses()
                    ]
                    yield Select(
                        course_options,
                        prompt="选择课程",
                        allow_blank=False,
                        id="grade-edit-course",
                    )
            else:
                with Horizontal(classes="grade-field-row"):
                    yield Static("学生", classes="grade-field-label")
                    yield Static(
                        f"{self.record['student_no']} · {self.record['student_name']}",
                        classes="grade-readonly",
                    )
                with Horizontal(classes="grade-field-row"):
                    yield Static("课程", classes="grade-field-label")
                    yield Static(
                        f"{self.record['course_code']} · {self.record['course_name']}",
                        classes="grade-readonly",
                    )

            semester = _show(self.record["semester"]) if self.record is not None else ""
            score = _show(self.record["score"]) if self.record is not None else ""
            with Horizontal(classes="grade-field-row"):
                yield Static("学期", classes="grade-field-label")
                yield Input(
                    value=semester,
                    placeholder="例如 2026-2027-1",
                    id="grade-edit-semester",
                )
            with Horizontal(classes="grade-field-row"):
                yield Static("成绩", classes="grade-field-label")
                yield Input(
                    value=score,
                    placeholder="0–100，可留空",
                    id="grade-edit-score",
                )

        with Horizontal(id="grade-edit-actions"):
            if self.record is not None:
                yield Button("删除…", id="grade-edit-delete")
            yield Static("", id="grade-edit-actions-spacer")
            yield Button("取消", id="grade-edit-cancel")
            yield Button("保存", id="grade-edit-save")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _after_delete(self, confirmed: bool | None) -> None:
        if not confirmed or self.enrollment_id is None:
            return
        try:
            self.repository.delete_enrollment(self.enrollment_id)
        except sqlite3.Error as error:
            self.app.notify(str(error), title="删除失败", severity="error")
            return
        self.app.notify("选课记录已删除")
        self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "grade-edit-cancel":
            self.dismiss(False)
            return
        if event.button.id == "grade-edit-delete":
            self.app.push_screen(GradeDeleteScreen(), self._after_delete)
            return
        if event.button.id != "grade-edit-save":
            return

        semester = self.query_one("#grade-edit-semester", Input).value.strip()
        if not semester:
            self.app.notify("学期需要填写", title="无法保存", severity="error")
            return

        try:
            score = _score(self.query_one("#grade-edit-score", Input).value)
            if self.record is None:
                student = self.query_one("#grade-edit-student", Select)
                course = self.query_one("#grade-edit-course", Select)
                if student.is_blank() or course.is_blank():
                    raise ValueError("请选择学生和课程")
                self.repository.add_enrollment(
                    int(student.value),
                    int(course.value),
                    semester,
                    score,
                )
            else:
                assert self.enrollment_id is not None
                self.repository.update_enrollment(
                    self.enrollment_id,
                    semester,
                    score,
                )
        except sqlite3.IntegrityError:
            self.app.notify(
                "这名学生在该学期已经有这门课程。",
                title="无法保存",
                severity="error",
            )
            return
        except (sqlite3.Error, ValueError) as error:
            self.app.notify(str(error), title="无法保存", severity="error")
            return

        self.app.notify("成绩记录已保存")
        self.dismiss(True)


class GradeDeleteScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "取消")]

    def compose(self) -> ComposeResult:
        with Vertical(id="grade-delete-dialog"):
            yield Static("删除选课记录？", id="grade-delete-title")
            yield Static(
                "这条选课和成绩记录将被删除。",
                id="grade-delete-message",
            )
            with Horizontal(id="grade-delete-actions"):
                yield Button("取消", id="grade-delete-cancel")
                yield Button("删除", id="grade-delete-confirm")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "grade-delete-confirm":
            self.dismiss(True)
        elif event.button.id == "grade-delete-cancel":
            self.dismiss(False)
