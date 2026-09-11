from __future__ import annotations

import sqlite3
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Input, Static

from .repository import Repository


def _show(value: Any) -> str:
    return "" if value is None else str(value)


def _required_int(value: str, field: str) -> int:
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field}必须是整数") from exc


def _optional_int(value: str, field: str) -> int | None:
    value = value.strip()
    return None if not value else _required_int(value, field)


def _required_float(value: str, field: str) -> float:
    try:
        return float(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field}必须是数字") from exc


def _optional_float(value: str, field: str) -> float | None:
    value = value.strip()
    return None if not value else _required_float(value, field)


def _none_if_blank(value: str) -> str | None:
    value = value.strip()
    return value or None


class CrudPage(VerticalScroll):
    def __init__(self, repository: Repository, *, id: str) -> None:
        super().__init__(id=id)
        self.repository = repository

    def report_error(self, error: Exception) -> None:
        if isinstance(error, sqlite3.IntegrityError):
            message = f"数据库约束失败：{error}"
        else:
            message = str(error)
        self.app.notify(message, title="操作失败", severity="error")

    def report_success(self, message: str) -> None:
        self.app.notify(message, severity="information")


class StudentPage(CrudPage):
    def compose(self) -> ComposeResult:
        yield Static("学生管理", classes="page-title")
        with Horizontal(classes="form-row"):
            yield Input(placeholder="记录 ID（加载/修改/删除）", id="student-id")
            yield Input(placeholder="学号 *", id="student-no")
            yield Input(placeholder="姓名 *", id="student-name")
            yield Input(placeholder="族系 *", id="student-family")
            yield Input(placeholder="支系 *", id="student-branch")
        with Horizontal(classes="form-row"):
            yield Input(placeholder="性别", id="student-gender")
            yield Input(placeholder="出生日期 YYYY-MM-DD", id="student-birth-date")
            yield Input(placeholder="入学年份 *", id="student-enrollment-year")
            yield Input(placeholder="班级 ID", id="student-class-id")
            yield Input(value="在读", placeholder="学籍状态", id="student-status")
        with Horizontal(classes="form-row"):
            yield Input(placeholder="主元素", id="student-primary-element")
            yield Input(placeholder="主亲和等级", id="student-primary-affinity")
            yield Input(placeholder="次元素", id="student-secondary-element")
            yield Input(placeholder="次亲和等级", id="student-secondary-affinity")
        with Horizontal(classes="form-row"):
            yield Input(placeholder="联系方式", id="student-contact")
            yield Input(placeholder="宿舍", id="student-dormitory")
            yield Input(placeholder="备注", id="student-notes")
        with Horizontal(classes="actions"):
            yield Button("新增", id="student-add", variant="success")
            yield Button("加载 ID", id="student-load")
            yield Button("修改", id="student-update", variant="primary")
            yield Button("删除", id="student-delete", variant="error")
            yield Input(placeholder="搜索学号/姓名/班级/专业/元素", id="student-search")
            yield Button("搜索", id="student-search-button")
            yield Button("全部", id="student-refresh")
        yield DataTable(id="student-table", zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one("#student-table", DataTable)
        table.add_columns("ID", "学号", "姓名", "族系", "支系", "班级", "专业", "主元素", "等级", "状态")
        self.refresh_table()

    def refresh_table(self, keyword: str = "") -> None:
        table = self.query_one("#student-table", DataTable)
        table.clear()
        for row in self.repository.list_students(keyword):
            table.add_row(
                _show(row["id"]), _show(row["student_no"]), _show(row["name"]),
                _show(row["family"]), _show(row["branch"]), _show(row["class_name"]),
                _show(row["major_name"]), _show(row["primary_element"]),
                _show(row["primary_affinity"]), _show(row["status"]),
            )

    def _values(self) -> dict[str, Any]:
        student_no = self.query_one("#student-no", Input).value.strip()
        name = self.query_one("#student-name", Input).value.strip()
        family = self.query_one("#student-family", Input).value.strip()
        branch = self.query_one("#student-branch", Input).value.strip()
        if not all((student_no, name, family, branch)):
            raise ValueError("学号、姓名、族系、支系为必填项")
        return {
            "student_no": student_no,
            "name": name,
            "family": family,
            "branch": branch,
            "gender": _none_if_blank(self.query_one("#student-gender", Input).value),
            "birth_date": _none_if_blank(self.query_one("#student-birth-date", Input).value),
            "enrollment_year": _required_int(self.query_one("#student-enrollment-year", Input).value, "入学年份"),
            "class_id": _optional_int(self.query_one("#student-class-id", Input).value, "班级 ID"),
            "status": self.query_one("#student-status", Input).value.strip() or "在读",
            "primary_element": _none_if_blank(self.query_one("#student-primary-element", Input).value),
            "primary_affinity": _none_if_blank(self.query_one("#student-primary-affinity", Input).value),
            "secondary_element": _none_if_blank(self.query_one("#student-secondary-element", Input).value),
            "secondary_affinity": _none_if_blank(self.query_one("#student-secondary-affinity", Input).value),
            "contact": _none_if_blank(self.query_one("#student-contact", Input).value),
            "dormitory": _none_if_blank(self.query_one("#student-dormitory", Input).value),
            "notes": _none_if_blank(self.query_one("#student-notes", Input).value),
        }

    def _record_id(self) -> int:
        return _required_int(self.query_one("#student-id", Input).value, "记录 ID")

    def _load(self) -> None:
        row = self.repository.get_student(self._record_id())
        if row is None:
            raise ValueError("找不到该学生")
        mapping = {
            "#student-no": "student_no", "#student-name": "name",
            "#student-family": "family", "#student-branch": "branch",
            "#student-gender": "gender", "#student-birth-date": "birth_date",
            "#student-enrollment-year": "enrollment_year", "#student-class-id": "class_id",
            "#student-status": "status", "#student-primary-element": "primary_element",
            "#student-primary-affinity": "primary_affinity",
            "#student-secondary-element": "secondary_element",
            "#student-secondary-affinity": "secondary_affinity",
            "#student-contact": "contact", "#student-dormitory": "dormitory",
            "#student-notes": "notes",
        }
        for selector, column in mapping.items():
            self.query_one(selector, Input).value = _show(row[column])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        try:
            if button_id == "student-add":
                self.repository.add_student(**self._values())
                self.refresh_table()
                self.report_success("学生已新增")
            elif button_id == "student-load":
                self._load()
            elif button_id == "student-update":
                self.repository.update_student(self._record_id(), **self._values())
                self.refresh_table()
                self.report_success("学生已修改")
            elif button_id == "student-delete":
                self.repository.delete_student(self._record_id())
                self.refresh_table()
                self.report_success("学生已删除")
            elif button_id == "student-search-button":
                self.refresh_table(self.query_one("#student-search", Input).value)
            elif button_id == "student-refresh":
                self.query_one("#student-search", Input).value = ""
                self.refresh_table()
        except (ValueError, sqlite3.Error) as error:
            self.report_error(error)


class AcademicsPage(CrudPage):
    def compose(self) -> ComposeResult:
        yield Static("学院、专业与班级", classes="page-title")
        yield Static("学院", classes="section-title")
        with Horizontal(classes="form-row"):
            yield Input(placeholder="ID", id="department-id")
            yield Input(placeholder="学院编号 *", id="department-code")
            yield Input(placeholder="学院名称 *", id="department-name")
            yield Button("新增", id="department-add", variant="success")
            yield Button("修改", id="department-update", variant="primary")
            yield Button("删除", id="department-delete", variant="error")
        yield DataTable(id="department-table", zebra_stripes=True)

        yield Static("专业", classes="section-title")
        with Horizontal(classes="form-row"):
            yield Input(placeholder="ID", id="major-id")
            yield Input(placeholder="专业编号 *", id="major-code")
            yield Input(placeholder="专业名称 *", id="major-name")
            yield Input(placeholder="学院 ID *", id="major-department-id")
            yield Button("新增", id="major-add", variant="success")
            yield Button("修改", id="major-update", variant="primary")
            yield Button("删除", id="major-delete", variant="error")
        yield DataTable(id="major-table", zebra_stripes=True)

        yield Static("班级", classes="section-title")
        with Horizontal(classes="form-row"):
            yield Input(placeholder="ID", id="class-id")
            yield Input(placeholder="班级编号 *", id="class-code")
            yield Input(placeholder="班级名称 *", id="class-name")
            yield Input(placeholder="专业 ID *", id="class-major-id")
            yield Input(placeholder="入学年份 *", id="class-year")
            yield Button("新增", id="class-add", variant="success")
            yield Button("修改", id="class-update", variant="primary")
            yield Button("删除", id="class-delete", variant="error")
        yield DataTable(id="class-table", zebra_stripes=True)

    def on_mount(self) -> None:
        self.query_one("#department-table", DataTable).add_columns("ID", "编号", "学院名称")
        self.query_one("#major-table", DataTable).add_columns("ID", "编号", "专业名称", "学院")
        self.query_one("#class-table", DataTable).add_columns("ID", "编号", "班级名称", "专业", "入学年份")
        self.refresh_tables()

    def refresh_tables(self) -> None:
        departments = self.query_one("#department-table", DataTable)
        departments.clear()
        for row in self.repository.list_departments():
            departments.add_row(_show(row["id"]), row["code"], row["name"])
        majors = self.query_one("#major-table", DataTable)
        majors.clear()
        for row in self.repository.list_majors():
            majors.add_row(_show(row["id"]), row["code"], row["name"], row["department_name"])
        classes = self.query_one("#class-table", DataTable)
        classes.clear()
        for row in self.repository.list_classes():
            classes.add_row(
                _show(row["id"]), row["code"], row["name"],
                row["major_name"], _show(row["enrollment_year"]),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        try:
            if button_id == "department-add":
                self.repository.add_department(
                    self.query_one("#department-code", Input).value,
                    self.query_one("#department-name", Input).value,
                )
            elif button_id == "department-update":
                self.repository.update_department(
                    _required_int(self.query_one("#department-id", Input).value, "学院 ID"),
                    self.query_one("#department-code", Input).value,
                    self.query_one("#department-name", Input).value,
                )
            elif button_id == "department-delete":
                self.repository.delete_department(
                    _required_int(self.query_one("#department-id", Input).value, "学院 ID")
                )
            elif button_id == "major-add":
                self.repository.add_major(
                    self.query_one("#major-code", Input).value,
                    self.query_one("#major-name", Input).value,
                    _required_int(self.query_one("#major-department-id", Input).value, "学院 ID"),
                )
            elif button_id == "major-update":
                self.repository.update_major(
                    _required_int(self.query_one("#major-id", Input).value, "专业 ID"),
                    self.query_one("#major-code", Input).value,
                    self.query_one("#major-name", Input).value,
                    _required_int(self.query_one("#major-department-id", Input).value, "学院 ID"),
                )
            elif button_id == "major-delete":
                self.repository.delete_major(
                    _required_int(self.query_one("#major-id", Input).value, "专业 ID")
                )
            elif button_id == "class-add":
                self.repository.add_class(
                    self.query_one("#class-code", Input).value,
                    self.query_one("#class-name", Input).value,
                    _required_int(self.query_one("#class-major-id", Input).value, "专业 ID"),
                    _required_int(self.query_one("#class-year", Input).value, "入学年份"),
                )
            elif button_id == "class-update":
                self.repository.update_class(
                    _required_int(self.query_one("#class-id", Input).value, "班级 ID"),
                    self.query_one("#class-code", Input).value,
                    self.query_one("#class-name", Input).value,
                    _required_int(self.query_one("#class-major-id", Input).value, "专业 ID"),
                    _required_int(self.query_one("#class-year", Input).value, "入学年份"),
                )
            elif button_id == "class-delete":
                self.repository.delete_class(
                    _required_int(self.query_one("#class-id", Input).value, "班级 ID")
                )
            else:
                return
            self.refresh_tables()
            self.report_success("操作完成")
        except (ValueError, sqlite3.Error) as error:
            self.report_error(error)


class CoursePage(CrudPage):
    def compose(self) -> ComposeResult:
        yield Static("课程管理", classes="page-title")
        with Horizontal(classes="form-row"):
            yield Input(placeholder="ID", id="course-id")
            yield Input(placeholder="课程编号 *", id="course-code")
            yield Input(placeholder="课程名称 *", id="course-name")
            yield Input(placeholder="开课学院 ID", id="course-department-id")
            yield Input(placeholder="学分 *", id="course-credits")
            yield Input(placeholder="课时 *", id="course-hours")
        with Horizontal(classes="actions"):
            yield Button("新增", id="course-add", variant="success")
            yield Button("修改", id="course-update", variant="primary")
            yield Button("删除", id="course-delete", variant="error")
            yield Button("刷新", id="course-refresh")
        yield DataTable(id="course-table", zebra_stripes=True)

    def on_mount(self) -> None:
        self.query_one("#course-table", DataTable).add_columns("ID", "编号", "课程", "学院", "学分", "课时")
        self.refresh_table()

    def refresh_table(self) -> None:
        table = self.query_one("#course-table", DataTable)
        table.clear()
        for row in self.repository.list_courses():
            table.add_row(
                _show(row["id"]), row["course_code"], row["name"],
                _show(row["department_name"]), _show(row["credits"]), _show(row["hours"]),
            )

    def _values(self) -> tuple[str, str, int | None, float, int]:
        code = self.query_one("#course-code", Input).value.strip()
        name = self.query_one("#course-name", Input).value.strip()
        if not code or not name:
            raise ValueError("课程编号和课程名称为必填项")
        return (
            code,
            name,
            _optional_int(self.query_one("#course-department-id", Input).value, "学院 ID"),
            _required_float(self.query_one("#course-credits", Input).value, "学分"),
            _required_int(self.query_one("#course-hours", Input).value, "课时"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        try:
            if event.button.id == "course-add":
                self.repository.add_course(*self._values())
            elif event.button.id == "course-update":
                self.repository.update_course(
                    _required_int(self.query_one("#course-id", Input).value, "课程 ID"),
                    *self._values(),
                )
            elif event.button.id == "course-delete":
                self.repository.delete_course(
                    _required_int(self.query_one("#course-id", Input).value, "课程 ID")
                )
            elif event.button.id == "course-refresh":
                self.refresh_table()
                return
            else:
                return
            self.refresh_table()
            self.report_success("操作完成")
        except (ValueError, sqlite3.Error) as error:
            self.report_error(error)


class GradePage(CrudPage):
    def compose(self) -> ComposeResult:
        yield Static("选课与成绩", classes="page-title")
        with Horizontal(classes="form-row"):
            yield Input(placeholder="记录 ID", id="grade-id")
            yield Input(placeholder="学生 ID *", id="grade-student-id")
            yield Input(placeholder="课程 ID *", id="grade-course-id")
            yield Input(placeholder="学期 *，如 2026-2027-1", id="grade-semester")
            yield Input(placeholder="成绩 0-100，可空", id="grade-score")
        with Horizontal(classes="actions"):
            yield Button("新增选课", id="grade-add", variant="success")
            yield Button("修改学期/成绩", id="grade-update", variant="primary")
            yield Button("删除", id="grade-delete", variant="error")
            yield Button("刷新", id="grade-refresh")
        yield DataTable(id="grade-table", zebra_stripes=True)

    def on_mount(self) -> None:
        self.query_one("#grade-table", DataTable).add_columns(
            "ID", "学生 ID", "学号", "姓名", "课程 ID", "课程", "学期", "成绩"
        )
        self.refresh_table()

    def refresh_table(self) -> None:
        table = self.query_one("#grade-table", DataTable)
        table.clear()
        for row in self.repository.list_enrollments():
            table.add_row(
                _show(row["id"]), _show(row["student_id"]), row["student_no"],
                row["student_name"], _show(row["course_id"]), row["course_name"],
                row["semester"], _show(row["score"]),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        try:
            if event.button.id == "grade-add":
                semester = self.query_one("#grade-semester", Input).value.strip()
                if not semester:
                    raise ValueError("学期为必填项")
                self.repository.add_enrollment(
                    _required_int(self.query_one("#grade-student-id", Input).value, "学生 ID"),
                    _required_int(self.query_one("#grade-course-id", Input).value, "课程 ID"),
                    semester,
                    _optional_float(self.query_one("#grade-score", Input).value, "成绩"),
                )
            elif event.button.id == "grade-update":
                semester = self.query_one("#grade-semester", Input).value.strip()
                if not semester:
                    raise ValueError("学期为必填项")
                self.repository.update_enrollment(
                    _required_int(self.query_one("#grade-id", Input).value, "记录 ID"),
                    semester,
                    _optional_float(self.query_one("#grade-score", Input).value, "成绩"),
                )
            elif event.button.id == "grade-delete":
                self.repository.delete_enrollment(
                    _required_int(self.query_one("#grade-id", Input).value, "记录 ID")
                )
            elif event.button.id == "grade-refresh":
                self.refresh_table()
                return
            else:
                return
            self.refresh_table()
            self.report_success("操作完成")
        except (ValueError, sqlite3.Error) as error:
            self.report_error(error)


class ReportsPage(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static("查询与统计", classes="page-title")
        yield Static("统计与 CSV 导入导出将在下一步加入。")
