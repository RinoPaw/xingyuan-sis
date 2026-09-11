from __future__ import annotations

import sqlite3
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, ContentSwitcher, DataTable, Input, Select, Static

from .reports import summary
from .repository import Repository
from .student_queries import get_student_profile, list_student_enrollments


def _show(value: Any) -> str:
    return "" if value is None else str(value)


def _none_if_blank(value: str) -> str | None:
    value = value.strip()
    return value or None


def _required_int(value: str, field: str) -> int:
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field}需要填写整数") from exc


class SignalMark(Static):
    """Small reactive mark used on the overview page."""

    frame = reactive(0)
    FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def on_mount(self) -> None:
        self.set_interval(0.09, self._tick)

    def _tick(self) -> None:
        self.frame = (self.frame + 1) % len(self.FRAMES)

    def render(self) -> str:
        glyph = self.FRAMES[self.frame]
        return f"{glyph}   ◇   {glyph}"


class OverviewPage(VerticalScroll):
    def __init__(self, repository: Repository, *, id: str) -> None:
        super().__init__(id=id)
        self.repository = repository

    def compose(self) -> ComposeResult:
        yield Static("Xingyuan", id="overview-heading")
        yield Static("student workspace", id="overview-subheading")
        yield SignalMark(id="overview-signal")
        with Horizontal(id="overview-stats"):
            yield Static("-\n学生", id="overview-students", classes="stat")
            yield Static("-\n班级", id="overview-classes", classes="stat")
            yield Static("-\n课程", id="overview-courses", classes="stat")
            yield Static("-\n平均成绩", id="overview-average", classes="stat")

    def on_mount(self) -> None:
        stats = summary(self.repository.db_path)
        self.query_one("#overview-students", Static).update(f"{stats['students']}\n学生")
        self.query_one("#overview-classes", Static).update(f"{stats['classes']}\n班级")
        self.query_one("#overview-courses", Static).update(f"{stats['courses']}\n课程")
        self.query_one("#overview-average", Static).update(
            f"{_show(stats['average_score']) or '-'}\n平均成绩"
        )


class StudentsPage(VerticalScroll):
    def __init__(self, repository: Repository, *, id: str) -> None:
        super().__init__(id=id)
        self.repository = repository
        self._student_ids: list[int] = []
        self._selected_ids: set[int] = set()

    def compose(self) -> ComposeResult:
        with Horizontal(id="students-header"):
            with Vertical():
                yield Static("学生", classes="page-title")
                yield Static("浏览档案与课程成绩", classes="page-subtitle")
            yield Button(
                "查看所选",
                id="student-view",
                classes="primary-action",
                disabled=True,
            )
            yield Button("+ 新建学生", id="student-new", classes="primary-action")

        yield Input(
            placeholder="搜索学号、姓名、支系、班级、专业或主元素…",
            id="student-search",
        )
        yield DataTable(id="students-table", cursor_type="row")
        yield Static("点击行勾选   选择 1 名后查看   / 搜索", id="students-hint")

    def on_mount(self) -> None:
        table = self.query_one("#students-table", DataTable)
        table.add_column("选", key="selected", width=3)
        table.add_column("学号", key="student_no")
        table.add_column("姓名", key="name")
        table.add_column("支系", key="branch")
        table.add_column("班级", key="class_name")
        table.add_column("专业", key="major_name")
        table.add_column("主元素", key="primary_element")
        table.add_column("状态", key="status")
        self.refresh_table()

    def refresh_table(self, keyword: str = "") -> None:
        rows = self.repository.list_students(keyword)
        self._student_ids = [int(row["id"]) for row in rows]
        self._selected_ids.intersection_update(self._student_ids)

        table = self.query_one("#students-table", DataTable)
        table.clear()
        for row in rows:
            student_id = int(row["id"])
            table.add_row(
                "☑" if student_id in self._selected_ids else "☐",
                _show(row["student_no"]),
                _show(row["name"]),
                _show(row["branch"]),
                _show(row["class_name"]),
                _show(row["major_name"]),
                _show(row["primary_element"]),
                _show(row["status"]),
                key=str(student_id),
            )
        self._update_selection_ui()

    def _update_selection_ui(self) -> None:
        count = len(self._selected_ids)
        self.query_one("#student-view", Button).disabled = count != 1
        hint = self.query_one("#students-hint", Static)
        if count == 0:
            hint.update("点击行勾选   选择 1 名后查看   / 搜索")
        elif count == 1:
            hint.update("已选 1 名   再点一次取消   查看所选 打开档案")
        else:
            hint.update(f"已选 {count} 名   点击已选行可取消   查看需只选 1 名")

    def _refresh_after_edit(self, changed: bool | None) -> None:
        if changed:
            self.refresh_table(self.query_one("#student-search", Input).value)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "student-search":
            self.refresh_table(event.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "students-table":
            return
        if not (0 <= event.cursor_row < len(self._student_ids)):
            return

        student_id = self._student_ids[event.cursor_row]
        if student_id in self._selected_ids:
            self._selected_ids.remove(student_id)
            mark = "☐"
        else:
            self._selected_ids.add(student_id)
            mark = "☑"

        event.data_table.update_cell(str(student_id), "selected", mark)
        self._update_selection_ui()

    def _open_selected_student(self) -> None:
        if len(self._selected_ids) != 1:
            return
        student_id = next(iter(self._selected_ids))
        self.app.push_screen(
            StudentDetailScreen(self.repository, student_id),
            self._refresh_after_edit,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "student-view":
            self._open_selected_student()
            return
        if event.button.id == "student-new":
            self.app.push_screen(
                StudentEditScreen(self.repository),
                self._refresh_after_edit,
            )


class StudentDetailScreen(Screen[bool]):
    BINDINGS = [("escape", "close", "返回")]

    def __init__(self, repository: Repository, student_id: int) -> None:
        super().__init__()
        self.repository = repository
        self.student_id = student_id
        self.changed = False

    def compose(self) -> ComposeResult:
        profile = get_student_profile(self.student_id, self.repository.db_path)
        if profile is None:
            yield Static("这条学生记录已经不存在。", id="detail-missing")
            return

        yield Static(
            f"学生 / {_show(profile['student_no'])}",
            id="detail-breadcrumb",
        )
        with Horizontal(id="detail-heading-row"):
            with Vertical():
                yield Static(_show(profile["name"]), id="detail-heading")
                yield Static(self._meta_text(profile), id="detail-meta")
            with Horizontal(id="detail-actions"):
                yield Button("编辑", id="detail-edit")
                yield Button("删除学生…", id="detail-delete", classes="danger-action")

        with Horizontal(id="detail-tabs"):
            yield Button("档案", id="detail-tab-profile", classes="active")
            yield Button("课程与成绩", id="detail-tab-grades")

        with ContentSwitcher(initial="detail-profile", id="detail-switcher"):
            with VerticalScroll(id="detail-profile"):
                yield Static("基本信息", classes="detail-section-title")
                yield Static(self._basic_text(profile), id="detail-basic", classes="detail-block")
                yield Static("学籍", classes="detail-section-title")
                yield Static(
                    self._academic_text(profile),
                    id="detail-academic",
                    classes="detail-block",
                )
                yield Static("元素", classes="detail-section-title")
                yield Static(
                    self._element_text(profile),
                    id="detail-element",
                    classes="detail-block",
                )
                yield Static("联系", classes="detail-section-title")
                yield Static(
                    self._contact_text(profile),
                    id="detail-contact",
                    classes="detail-block",
                )
            with VerticalScroll(id="detail-grades"):
                yield DataTable(id="detail-grades-table")

        yield Static("Esc 返回", id="detail-hint")

    def on_mount(self) -> None:
        try:
            table = self.query_one("#detail-grades-table", DataTable)
        except Exception:
            return
        table.add_columns("学期", "课程", "学分", "成绩")
        self._refresh_grades()

    def _refresh_grades(self) -> None:
        table = self.query_one("#detail-grades-table", DataTable)
        table.clear()
        for row in list_student_enrollments(self.student_id, self.repository.db_path):
            table.add_row(
                _show(row["semester"]),
                _show(row["course_name"]),
                _show(row["credits"]),
                _show(row["score"]) or "—",
            )

    def action_close(self) -> None:
        self.dismiss(self.changed)

    def _refresh_after_edit(self, changed: bool | None) -> None:
        if not changed:
            return
        self.changed = True
        profile = get_student_profile(self.student_id, self.repository.db_path)
        if profile is None:
            return
        self.query_one("#detail-breadcrumb", Static).update(
            f"学生 / {_show(profile['student_no'])}"
        )
        self.query_one("#detail-heading", Static).update(_show(profile["name"]))
        self.query_one("#detail-meta", Static).update(self._meta_text(profile))
        self.query_one("#detail-basic", Static).update(self._basic_text(profile))
        self.query_one("#detail-academic", Static).update(self._academic_text(profile))
        self.query_one("#detail-element", Static).update(self._element_text(profile))
        self.query_one("#detail-contact", Static).update(self._contact_text(profile))

    def _after_delete(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            self.repository.delete_student(self.student_id)
        except sqlite3.Error as error:
            self.app.notify(str(error), title="删除失败", severity="error")
            return
        self.app.notify("学生已删除")
        self.dismiss(True)

    def _meta_text(self, profile: Any) -> str:
        return "  ·  ".join(
            value
            for value in (
                _show(profile["major_name"]),
                _show(profile["class_name"]),
                _show(profile["status"]),
            )
            if value
        )

    def _basic_text(self, profile: Any) -> str:
        return (
            f"学号        {_show(profile['student_no'])}\n"
            f"族系        {_show(profile['family'])} · {_show(profile['branch'])}\n"
            f"性别        {_show(profile['gender']) or '—'}\n"
            f"出生日期    {_show(profile['birth_date']) or '—'}"
        )

    def _academic_text(self, profile: Any) -> str:
        return (
            f"学院        {_show(profile['department_name']) or '—'}\n"
            f"专业        {_show(profile['major_name']) or '—'}\n"
            f"班级        {_show(profile['class_name']) or '—'}\n"
            f"入学年份    {_show(profile['enrollment_year'])}\n"
            f"状态        {_show(profile['status'])}"
        )

    def _element_text(self, profile: Any) -> str:
        affinity = _show(profile["primary_affinity"])
        value = _show(profile["primary_element"]) or "—"
        if affinity:
            value = f"{value}  ·  {affinity}"
        return f"主元素      {value}"

    def _contact_text(self, profile: Any) -> str:
        return (
            f"联系方式    {_show(profile['contact']) or '—'}\n"
            f"宿舍        {_show(profile['dormitory']) or '—'}\n"
            f"备注        {_show(profile['notes']) or '—'}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "detail-edit":
            self.app.push_screen(
                StudentEditScreen(self.repository, self.student_id),
                self._refresh_after_edit,
            )
            return
        if event.button.id == "detail-delete":
            profile = get_student_profile(self.student_id, self.repository.db_path)
            name = _show(profile["name"]) if profile else "这名学生"
            self.app.push_screen(
                ConfirmDeleteScreen(name),
                self._after_delete,
            )
            return

        pages = {
            "detail-tab-profile": "detail-profile",
            "detail-tab-grades": "detail-grades",
        }
        target = pages.get(event.button.id)
        if target is None:
            return

        for button in self.query("#detail-tabs Button"):
            button.remove_class("active")
        event.button.add_class("active")
        self.query_one("#detail-switcher", ContentSwitcher).current = target


class StudentEditScreen(Screen[bool]):
    BINDINGS = [("escape", "cancel", "取消")]

    def __init__(self, repository: Repository, student_id: int | None = None) -> None:
        super().__init__()
        self.repository = repository
        self.student_id = student_id
        self.record = (
            self.repository.get_student(student_id)
            if student_id is not None
            else None
        )

    def compose(self) -> ComposeResult:
        title = "编辑学生" if self.record is not None else "新建学生"
        yield Static(title, id="edit-heading")
        yield Static("填写学生档案，完成后保存。", id="edit-subtitle")

        with VerticalScroll(id="edit-form"):
            yield Static("基本信息", classes="edit-section-title")
            yield from self._input_row("学号", "edit-student-no", "student_no")
            yield from self._input_row("姓名", "edit-name", "name")
            yield from self._input_row("族系", "edit-family", "family")
            yield from self._input_row("支系", "edit-branch", "branch")
            yield from self._input_row("性别", "edit-gender", "gender")
            yield from self._input_row(
                "出生日期",
                "edit-birth-date",
                "birth_date",
                placeholder="YYYY-MM-DD",
            )

            yield Static("学籍", classes="edit-section-title")
            yield from self._input_row(
                "入学年份",
                "edit-enrollment-year",
                "enrollment_year",
            )
            with Horizontal(classes="field-row"):
                yield Static("班级", classes="field-label")
                class_options = [
                    (
                        f"{row['major_name']} / {row['name']}",
                        int(row["id"]),
                    )
                    for row in self.repository.list_classes()
                ]
                class_value: Any = Select.NULL
                if self.record is not None and self.record["class_id"] is not None:
                    class_value = int(self.record["class_id"])
                yield Select(
                    class_options,
                    prompt="未分班",
                    allow_blank=True,
                    value=class_value,
                    id="edit-class",
                )
            yield from self._input_row(
                "状态",
                "edit-status",
                "status",
                default="在读",
            )

            yield Static("元素", classes="edit-section-title")
            yield from self._input_row(
                "主元素",
                "edit-primary-element",
                "primary_element",
            )
            yield from self._input_row(
                "亲和等级",
                "edit-primary-affinity",
                "primary_affinity",
            )

            yield Static("联系", classes="edit-section-title")
            yield from self._input_row("联系方式", "edit-contact", "contact")
            yield from self._input_row("宿舍", "edit-dormitory", "dormitory")
            yield from self._input_row("备注", "edit-notes", "notes")

        with Horizontal(id="edit-actions"):
            yield Button("取消", id="edit-cancel")
            yield Button("保存", id="edit-save", classes="primary-action")

    def _input_row(
        self,
        label: str,
        widget_id: str,
        column: str,
        *,
        placeholder: str = "",
        default: str = "",
    ):
        value = default
        if self.record is not None:
            value = _show(self.record[column])
        with Horizontal(classes="field-row"):
            yield Static(label, classes="field-label")
            yield Input(value=value, placeholder=placeholder, id=widget_id)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _values(self) -> dict[str, Any]:
        student_no = self.query_one("#edit-student-no", Input).value.strip()
        name = self.query_one("#edit-name", Input).value.strip()
        family = self.query_one("#edit-family", Input).value.strip()
        branch = self.query_one("#edit-branch", Input).value.strip()
        if not all((student_no, name, family, branch)):
            raise ValueError("学号、姓名、族系和支系需要填写")

        class_select = self.query_one("#edit-class", Select)
        class_id = None if class_select.is_blank() else int(class_select.value)

        return {
            "student_no": student_no,
            "name": name,
            "family": family,
            "branch": branch,
            "gender": _none_if_blank(self.query_one("#edit-gender", Input).value),
            "birth_date": _none_if_blank(
                self.query_one("#edit-birth-date", Input).value
            ),
            "enrollment_year": _required_int(
                self.query_one("#edit-enrollment-year", Input).value,
                "入学年份",
            ),
            "class_id": class_id,
            "status": self.query_one("#edit-status", Input).value.strip() or "在读",
            "primary_element": _none_if_blank(
                self.query_one("#edit-primary-element", Input).value
            ),
            "primary_affinity": _none_if_blank(
                self.query_one("#edit-primary-affinity", Input).value
            ),
            "contact": _none_if_blank(self.query_one("#edit-contact", Input).value),
            "dormitory": _none_if_blank(
                self.query_one("#edit-dormitory", Input).value
            ),
            "notes": _none_if_blank(self.query_one("#edit-notes", Input).value),
        }

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit-cancel":
            self.dismiss(False)
            return
        if event.button.id != "edit-save":
            return

        try:
            values = self._values()
            if self.student_id is None:
                self.repository.add_student(**values)
            else:
                self.repository.update_student(self.student_id, **values)
        except sqlite3.IntegrityError:
            self.app.notify(
                "学号已存在，或档案与现有数据冲突。",
                title="无法保存",
                severity="error",
            )
            return
        except (sqlite3.Error, ValueError) as error:
            self.app.notify(str(error), title="无法保存", severity="error")
            return

        self.app.notify("学生档案已保存")
        self.dismiss(True)


class ConfirmDeleteScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "取消")]

    def __init__(self, student_name: str) -> None:
        super().__init__()
        self.student_name = student_name

    def compose(self) -> ComposeResult:
        with Vertical(id="delete-dialog"):
            yield Static("删除学生？", id="delete-title")
            yield Static(
                f"{self.student_name} 的档案和选课记录将被删除。",
                id="delete-message",
            )
            with Horizontal(id="delete-actions"):
                yield Button("取消", id="delete-cancel")
                yield Button("删除", id="delete-confirm", classes="danger-action")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "delete-confirm":
            self.dismiss(True)
        elif event.button.id == "delete-cancel":
            self.dismiss(False)