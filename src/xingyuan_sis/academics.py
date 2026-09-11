from __future__ import annotations

import sqlite3
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, ContentSwitcher, DataTable, Input, Select, Static

from .repository import Repository


def _show(value: Any) -> str:
    return "" if value is None else str(value)


def _required_int(value: str, field: str) -> int:
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field}需要填写整数") from exc


def _row_by_id(rows: list[Any], record_id: int | None) -> Any | None:
    if record_id is None:
        return None
    return next((row for row in rows if int(row["id"]) == record_id), None)


class AcademicsPage(VerticalScroll):
    DEFAULT_CSS = """
    AcademicsPage {
        padding: 2 3;
    }

    #academics-header {
        height: auto;
        margin-bottom: 1;
    }

    #academics-header > Vertical {
        width: 1fr;
        height: auto;
    }

    #academics-tabs {
        height: 3;
        margin-bottom: 1;
        border-bottom: solid #1c2129;
    }

    #academics-tabs Button {
        width: auto;
        min-width: 8;
        height: 3;
        margin-right: 1;
        background: transparent;
        color: #6f7885;
        border: none;
    }

    #academics-tabs Button.active {
        color: #f0f4f8;
        border-bottom: solid #5aa9ff;
    }

    #academics-switcher {
        height: 1fr;
    }

    .academic-panel {
        height: 1fr;
    }

    .academic-panel-header {
        height: auto;
        margin: 1 0;
    }

    .academic-panel-header > Vertical {
        width: 1fr;
        height: auto;
    }

    .academic-panel-title {
        height: auto;
        text-style: bold;
        color: #d9e0e8;
    }

    .academic-panel-subtitle {
        height: auto;
        color: #697481;
    }

    .academic-new {
        width: 14;
        height: 3;
        background: #162435;
        color: #9fd3ff;
        border: none;
    }

    .academic-table {
        height: 1fr;
        border-top: solid #1b222c;
    }

    #academics-hint {
        height: 2;
        padding-top: 1;
        color: #59636f;
    }
    """

    def __init__(self, repository: Repository, *, id: str) -> None:
        super().__init__(id=id)
        self.repository = repository
        self._department_ids: list[int] = []
        self._major_ids: list[int] = []
        self._class_ids: list[int] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="academics-header"):
            with Vertical():
                yield Static("教务", classes="page-title")
                yield Static("学院、专业与班级", classes="page-subtitle")

        with Horizontal(id="academics-tabs"):
            yield Button("学院", id="academics-tab-departments", classes="active")
            yield Button("专业", id="academics-tab-majors")
            yield Button("班级", id="academics-tab-classes")

        with ContentSwitcher(initial="academics-departments", id="academics-switcher"):
            with Vertical(id="academics-departments", classes="academic-panel"):
                with Horizontal(classes="academic-panel-header"):
                    with Vertical():
                        yield Static("学院", classes="academic-panel-title")
                        yield Static("专业所属的上级组织", classes="academic-panel-subtitle")
                    yield Button("+ 新建学院", id="department-new", classes="academic-new")
                yield DataTable(id="department-table", classes="academic-table", cursor_type="row")

            with Vertical(id="academics-majors", classes="academic-panel"):
                with Horizontal(classes="academic-panel-header"):
                    with Vertical():
                        yield Static("专业", classes="academic-panel-title")
                        yield Static("专业归属于学院", classes="academic-panel-subtitle")
                    yield Button("+ 新建专业", id="major-new", classes="academic-new")
                yield DataTable(id="major-table", classes="academic-table", cursor_type="row")

            with Vertical(id="academics-classes", classes="academic-panel"):
                with Horizontal(classes="academic-panel-header"):
                    with Vertical():
                        yield Static("班级", classes="academic-panel-title")
                        yield Static("班级归属于专业，并记录入学年份", classes="academic-panel-subtitle")
                    yield Button("+ 新建班级", id="class-new", classes="academic-new")
                yield DataTable(id="class-table", classes="academic-table", cursor_type="row")

        yield Static("↑↓ 选择   Enter 编辑", id="academics-hint")

    def on_mount(self) -> None:
        self.query_one("#department-table", DataTable).add_columns("编号", "学院")
        self.query_one("#major-table", DataTable).add_columns("编号", "专业", "学院")
        self.query_one("#class-table", DataTable).add_columns("编号", "班级", "专业", "入学年份")
        self.refresh_tables()

    def refresh_tables(self) -> None:
        departments = self.repository.list_departments()
        self._department_ids = [int(row["id"]) for row in departments]
        department_table = self.query_one("#department-table", DataTable)
        department_table.clear()
        for row in departments:
            department_table.add_row(_show(row["code"]), _show(row["name"]))

        majors = self.repository.list_majors()
        self._major_ids = [int(row["id"]) for row in majors]
        major_table = self.query_one("#major-table", DataTable)
        major_table.clear()
        for row in majors:
            major_table.add_row(
                _show(row["code"]),
                _show(row["name"]),
                _show(row["department_name"]),
            )

        classes = self.repository.list_classes()
        self._class_ids = [int(row["id"]) for row in classes]
        class_table = self.query_one("#class-table", DataTable)
        class_table.clear()
        for row in classes:
            class_table.add_row(
                _show(row["code"]),
                _show(row["name"]),
                _show(row["major_name"]),
                _show(row["enrollment_year"]),
            )

    def _after_edit(self, changed: bool | None) -> None:
        if changed:
            self.refresh_tables()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = event.cursor_row
        if event.data_table.id == "department-table" and 0 <= row < len(self._department_ids):
            self.app.push_screen(
                DepartmentEditScreen(self.repository, self._department_ids[row]),
                self._after_edit,
            )
        elif event.data_table.id == "major-table" and 0 <= row < len(self._major_ids):
            self.app.push_screen(
                MajorEditScreen(self.repository, self._major_ids[row]),
                self._after_edit,
            )
        elif event.data_table.id == "class-table" and 0 <= row < len(self._class_ids):
            self.app.push_screen(
                ClassEditScreen(self.repository, self._class_ids[row]),
                self._after_edit,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        tabs = {
            "academics-tab-departments": "academics-departments",
            "academics-tab-majors": "academics-majors",
            "academics-tab-classes": "academics-classes",
        }
        target = tabs.get(event.button.id)
        if target is not None:
            for button in self.query("#academics-tabs Button"):
                button.remove_class("active")
            event.button.add_class("active")
            self.query_one("#academics-switcher", ContentSwitcher).current = target
            return

        if event.button.id == "department-new":
            self.app.push_screen(DepartmentEditScreen(self.repository), self._after_edit)
        elif event.button.id == "major-new":
            self.app.push_screen(MajorEditScreen(self.repository), self._after_edit)
        elif event.button.id == "class-new":
            self.app.push_screen(ClassEditScreen(self.repository), self._after_edit)


class AcademicEditScreen(Screen[bool]):
    DEFAULT_CSS = """
    AcademicEditScreen {
        background: #0b0d10;
        padding: 2 4;
    }

    .academic-edit-heading {
        height: auto;
        color: #f0f4f8;
        text-style: bold;
    }

    .academic-edit-subtitle {
        height: auto;
        color: #6f7885;
        margin-bottom: 2;
    }

    .academic-edit-form {
        height: 1fr;
        max-width: 72;
    }

    .academic-field-row {
        height: 3;
        margin-bottom: 1;
    }

    .academic-field-label {
        width: 12;
        height: 3;
        content-align: left middle;
        color: #7c8794;
    }

    .academic-field-row Input,
    .academic-field-row Select {
        width: 1fr;
        height: 3;
        background: #10141a;
        border: none;
    }

    .academic-edit-actions {
        height: 4;
        max-width: 72;
        border-top: solid #1c2129;
        padding-top: 1;
    }

    .academic-edit-actions Button {
        width: 10;
        height: 3;
        margin-left: 1;
        border: none;
        background: transparent;
        color: #8d98a6;
    }

    .academic-action-spacer {
        width: 1fr;
    }

    .academic-edit-actions .primary-action {
        background: #162435;
        color: #9fd3ff;
    }

    .academic-edit-actions .danger-action {
        color: #d98989;
    }
    """

    BINDINGS = [("escape", "cancel", "取消")]

    def __init__(self, repository: Repository, record_id: int | None = None) -> None:
        super().__init__()
        self.repository = repository
        self.record_id = record_id

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _actions(self) -> ComposeResult:
        with Horizontal(classes="academic-edit-actions"):
            if self.record_id is not None:
                yield Button("删除…", id="academic-delete", classes="danger-action")
            yield Static("", classes="academic-action-spacer")
            yield Button("取消", id="academic-cancel")
            yield Button("保存", id="academic-save", classes="primary-action")

    def _notify_error(self, error: Exception) -> None:
        if isinstance(error, sqlite3.IntegrityError):
            message = "编号或名称与现有数据冲突，或这条记录仍被其他数据使用。"
        else:
            message = str(error)
        self.app.notify(message, title="无法保存", severity="error")


class DepartmentEditScreen(AcademicEditScreen):
    def __init__(self, repository: Repository, record_id: int | None = None) -> None:
        super().__init__(repository, record_id)
        self.record = _row_by_id(repository.list_departments(), record_id)

    def compose(self) -> ComposeResult:
        yield Static("编辑学院" if self.record else "新建学院", classes="academic-edit-heading")
        yield Static("学院是专业的上级组织。", classes="academic-edit-subtitle")
        with VerticalScroll(classes="academic-edit-form"):
            with Horizontal(classes="academic-field-row"):
                yield Static("编号", classes="academic-field-label")
                yield Input(value=_show(self.record["code"]) if self.record else "", id="academic-code")
            with Horizontal(classes="academic-field-row"):
                yield Static("名称", classes="academic-field-label")
                yield Input(value=_show(self.record["name"]) if self.record else "", id="academic-name")
        yield from self._actions()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "academic-cancel":
            self.dismiss(False)
        elif event.button.id == "academic-delete":
            name = _show(self.record["name"]) if self.record else "这个学院"
            self.app.push_screen(
                ReferenceDeleteScreen("学院", name, "仍有专业属于这个学院时，将无法删除。"),
                self._after_delete,
            )
        elif event.button.id == "academic-save":
            code = self.query_one("#academic-code", Input).value.strip()
            name = self.query_one("#academic-name", Input).value.strip()
            if not code or not name:
                self.app.notify("编号和名称都需要填写。", title="无法保存", severity="error")
                return
            try:
                if self.record_id is None:
                    self.repository.add_department(code, name)
                else:
                    self.repository.update_department(self.record_id, code, name)
            except sqlite3.Error as error:
                self._notify_error(error)
                return
            self.dismiss(True)

    def _after_delete(self, confirmed: bool | None) -> None:
        if not confirmed or self.record_id is None:
            return
        try:
            self.repository.delete_department(self.record_id)
        except sqlite3.Error as error:
            self._notify_error(error)
            return
        self.dismiss(True)


class MajorEditScreen(AcademicEditScreen):
    def __init__(self, repository: Repository, record_id: int | None = None) -> None:
        super().__init__(repository, record_id)
        self.record = _row_by_id(repository.list_majors(), record_id)

    def compose(self) -> ComposeResult:
        yield Static("编辑专业" if self.record else "新建专业", classes="academic-edit-heading")
        yield Static("选择所属学院，再填写专业信息。", classes="academic-edit-subtitle")
        departments = self.repository.list_departments()
        options = [(row["name"], int(row["id"])) for row in departments]
        value: Any = Select.NULL
        if self.record is not None:
            value = int(self.record["department_id"])
        with VerticalScroll(classes="academic-edit-form"):
            with Horizontal(classes="academic-field-row"):
                yield Static("编号", classes="academic-field-label")
                yield Input(value=_show(self.record["code"]) if self.record else "", id="academic-code")
            with Horizontal(classes="academic-field-row"):
                yield Static("名称", classes="academic-field-label")
                yield Input(value=_show(self.record["name"]) if self.record else "", id="academic-name")
            with Horizontal(classes="academic-field-row"):
                yield Static("学院", classes="academic-field-label")
                yield Select(options, prompt="选择学院", allow_blank=False, value=value, id="academic-parent")
        yield from self._actions()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "academic-cancel":
            self.dismiss(False)
            return
        if event.button.id == "academic-delete":
            name = _show(self.record["name"]) if self.record else "这个专业"
            self.app.push_screen(
                ReferenceDeleteScreen("专业", name, "仍有班级属于这个专业时，将无法删除。"),
                self._after_delete,
            )
            return
        if event.button.id != "academic-save":
            return
        code = self.query_one("#academic-code", Input).value.strip()
        name = self.query_one("#academic-name", Input).value.strip()
        select = self.query_one("#academic-parent", Select)
        if not code or not name or select.is_blank():
            self.app.notify("编号、名称和所属学院都需要填写。", title="无法保存", severity="error")
            return
        try:
            department_id = int(select.value)
            if self.record_id is None:
                self.repository.add_major(code, name, department_id)
            else:
                self.repository.update_major(self.record_id, code, name, department_id)
        except (ValueError, sqlite3.Error) as error:
            self._notify_error(error)
            return
        self.dismiss(True)

    def _after_delete(self, confirmed: bool | None) -> None:
        if not confirmed or self.record_id is None:
            return
        try:
            self.repository.delete_major(self.record_id)
        except sqlite3.Error as error:
            self._notify_error(error)
            return
        self.dismiss(True)


class ClassEditScreen(AcademicEditScreen):
    def __init__(self, repository: Repository, record_id: int | None = None) -> None:
        super().__init__(repository, record_id)
        self.record = _row_by_id(repository.list_classes(), record_id)

    def compose(self) -> ComposeResult:
        yield Static("编辑班级" if self.record else "新建班级", classes="academic-edit-heading")
        yield Static("选择所属专业，并记录班级的入学年份。", classes="academic-edit-subtitle")
        majors = self.repository.list_majors()
        options = [
            (f"{row['department_name']} / {row['name']}", int(row["id"]))
            for row in majors
        ]
        value: Any = Select.NULL
        if self.record is not None:
            value = int(self.record["major_id"])
        with VerticalScroll(classes="academic-edit-form"):
            with Horizontal(classes="academic-field-row"):
                yield Static("编号", classes="academic-field-label")
                yield Input(value=_show(self.record["code"]) if self.record else "", id="academic-code")
            with Horizontal(classes="academic-field-row"):
                yield Static("名称", classes="academic-field-label")
                yield Input(value=_show(self.record["name"]) if self.record else "", id="academic-name")
            with Horizontal(classes="academic-field-row"):
                yield Static("专业", classes="academic-field-label")
                yield Select(options, prompt="选择专业", allow_blank=False, value=value, id="academic-parent")
            with Horizontal(classes="academic-field-row"):
                yield Static("入学年份", classes="academic-field-label")
                yield Input(
                    value=_show(self.record["enrollment_year"]) if self.record else "",
                    id="academic-year",
                )
        yield from self._actions()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "academic-cancel":
            self.dismiss(False)
            return
        if event.button.id == "academic-delete":
            name = _show(self.record["name"]) if self.record else "这个班级"
            self.app.push_screen(
                ReferenceDeleteScreen("班级", name, "删除后，原属于这个班级的学生会变为未分班。"),
                self._after_delete,
            )
            return
        if event.button.id != "academic-save":
            return
        code = self.query_one("#academic-code", Input).value.strip()
        name = self.query_one("#academic-name", Input).value.strip()
        select = self.query_one("#academic-parent", Select)
        if not code or not name or select.is_blank():
            self.app.notify("编号、名称和所属专业都需要填写。", title="无法保存", severity="error")
            return
        try:
            year = _required_int(self.query_one("#academic-year", Input).value, "入学年份")
            major_id = int(select.value)
            if self.record_id is None:
                self.repository.add_class(code, name, major_id, year)
            else:
                self.repository.update_class(self.record_id, code, name, major_id, year)
        except (ValueError, sqlite3.Error) as error:
            self._notify_error(error)
            return
        self.dismiss(True)

    def _after_delete(self, confirmed: bool | None) -> None:
        if not confirmed or self.record_id is None:
            return
        try:
            self.repository.delete_class(self.record_id)
        except sqlite3.Error as error:
            self._notify_error(error)
            return
        self.dismiss(True)


class ReferenceDeleteScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    ReferenceDeleteScreen {
        align: center middle;
        background: #000000 60%;
    }

    #reference-delete-dialog {
        width: 54;
        height: auto;
        padding: 1 2;
        background: #11161d;
        border: solid #2a313b;
    }

    #reference-delete-title {
        height: auto;
        color: #f0f4f8;
        text-style: bold;
        margin-bottom: 1;
    }

    #reference-delete-message {
        height: auto;
        color: #87919d;
        margin-bottom: 2;
    }

    #reference-delete-actions {
        height: 3;
        align-horizontal: right;
    }

    #reference-delete-actions Button {
        width: 10;
        height: 3;
        margin-left: 1;
        border: none;
    }
    """

    BINDINGS = [("escape", "cancel", "取消")]

    def __init__(self, kind: str, name: str, note: str) -> None:
        super().__init__()
        self.kind = kind
        self.name = name
        self.note = note

    def compose(self) -> ComposeResult:
        with Vertical(id="reference-delete-dialog"):
            yield Static(f"删除{self.kind}？", id="reference-delete-title")
            yield Static(
                f"{self.name} 将被删除。\n{self.note}",
                id="reference-delete-message",
            )
            with Horizontal(id="reference-delete-actions"):
                yield Button("取消", id="reference-delete-cancel")
                yield Button("删除", id="reference-delete-confirm", classes="danger-action")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "reference-delete-confirm":
            self.dismiss(True)
        elif event.button.id == "reference-delete-cancel":
            self.dismiss(False)
