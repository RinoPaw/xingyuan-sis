from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, Footer, Static

from .academics import AcademicsPage
from .repository import Repository
from .reports_view import ReportsPage
from .views import CoursePage, GradePage
from .workspace import OverviewPage, StudentsPage


class XingyuanSIS(App[None]):
    TITLE = "星原大学学生信息管理系统"
    BINDINGS = [("q", "quit", "退出")]

    CSS = """
    Screen {
        background: #0b0d10;
        color: #d8dee9;
    }

    #topbar {
        height: 3;
        padding: 1 2;
        color: #737b87;
        background: #0b0d10;
        border-bottom: solid #1c2129;
    }

    #body {
        height: 1fr;
        background: #0b0d10;
    }

    #nav {
        width: 18;
        padding: 1;
        background: #0b0d10;
        border-right: solid #1c2129;
    }

    #nav-brand {
        height: 3;
        padding: 1;
        color: #8bd5ff;
        text-style: bold;
    }

    #nav Button {
        width: 100%;
        height: 3;
        margin: 0;
        padding: 0 1;
        background: transparent;
        color: #7c8591;
        border: none;
        content-align: left middle;
        text-wrap: nowrap;
    }

    #nav Button:hover {
        background: #11161d;
        color: #e6edf3;
    }

    #nav Button.active {
        background: #11161d;
        color: #f0f4f8;
        border-left: solid #5aa9ff;
    }

    ContentSwitcher {
        width: 1fr;
        height: 1fr;
        background: #0d1014;
    }

    #content-switcher > * {
        padding: 1 2;
    }

    .page-title {
        height: auto;
        text-style: bold;
        color: #eef2f7;
        margin: 1 0 0 0;
    }

    .page-subtitle {
        height: auto;
        color: #6f7885;
    }

    .section-title {
        text-style: bold;
        color: #b7c0cc;
        margin-top: 1;
    }

    .form-row {
        height: auto;
        margin-bottom: 1;
    }

    .form-row Input {
        width: 1fr;
        min-width: 14;
        margin-right: 1;
    }

    .form-row Button {
        margin-right: 1;
    }

    .actions {
        height: auto;
        margin-bottom: 1;
    }

    .actions Button {
        margin-right: 1;
    }

    .actions Input {
        width: 1fr;
        min-width: 24;
        margin-right: 1;
    }

    DataTable {
        background: #0d1014;
    }

    Button.primary-action {
        background: #162435;
        color: #9fd3ff;
        border: none;
        text-style: bold;
    }

    Button.primary-action:hover {
        background: #1c3047;
        color: #d7edff;
    }

    Button.danger-action {
        background: transparent;
        color: #d98989;
        border: none;
    }

    Button.danger-action:hover {
        background: #261719;
        color: #ffaaaa;
    }

    #overview {
        padding: 2 4;
    }

    #overview-heading {
        margin-top: 2;
        color: #f0f4f8;
        text-style: bold;
    }

    #overview-subheading {
        color: #687280;
        margin-bottom: 1;
    }

    #overview-signal {
        height: 3;
        color: #72c7ff;
        margin: 1 0 2 0;
    }

    #overview-stats {
        height: 7;
        margin-bottom: 2;
    }

    .stat {
        width: 1fr;
        min-width: 12;
        height: 6;
        margin-right: 1;
        padding: 1;
        background: #10141a;
        border: solid #1b222c;
        color: #8894a2;
    }

    #students-page {
        padding: 2 3;
    }

    #students-header {
        height: auto;
        margin-bottom: 2;
    }

    #students-header > Vertical {
        width: 1fr;
        height: auto;
    }

    #student-new {
        width: 14;
        height: 3;
        margin-top: 1;
    }

    #student-search {
        width: 1fr;
        height: 3;
        margin-bottom: 1;
        border: none;
        background: #10141a;
    }

    #students-table {
        height: 1fr;
        border-top: solid #1b222c;
    }

    #students-hint {
        height: 2;
        color: #626c78;
        padding-top: 1;
    }

    StudentDetailScreen {
        background: #0b0d10;
        padding: 2 4;
    }

    #detail-breadcrumb {
        height: 2;
        color: #626c78;
    }

    #detail-heading-row {
        height: auto;
        margin-bottom: 2;
    }

    #detail-heading-row > Vertical {
        width: 1fr;
        height: auto;
    }

    #detail-heading {
        height: auto;
        color: #f0f4f8;
        text-style: bold;
    }

    #detail-meta {
        height: auto;
        color: #707a87;
    }

    #detail-actions {
        width: auto;
        height: 3;
    }

    #detail-actions Button {
        width: auto;
        min-width: 8;
        height: 3;
        margin-left: 1;
        background: transparent;
        border: none;
        color: #9aa4b1;
    }

    #detail-tabs {
        height: 3;
        margin-bottom: 1;
        border-bottom: solid #1c2129;
    }

    #detail-tabs Button {
        width: auto;
        min-width: 10;
        height: 3;
        background: transparent;
        color: #6f7885;
        border: none;
        margin-right: 1;
    }

    #detail-tabs Button.active {
        color: #f0f4f8;
        border-bottom: solid #5aa9ff;
    }

    #detail-switcher {
        height: 1fr;
    }

    #detail-profile,
    #detail-grades {
        padding: 1 0;
    }

    .detail-section-title {
        height: auto;
        margin: 1 0;
        color: #8d98a6;
        text-style: bold;
    }

    .detail-block {
        height: auto;
        padding: 0 0 1 0;
        color: #c7ced8;
    }

    #detail-grades-table {
        height: 1fr;
    }

    #detail-hint {
        height: 2;
        padding-top: 1;
        color: #59636f;
    }

    #detail-missing {
        margin: 3;
        color: #8d98a6;
    }

    StudentEditScreen {
        background: #0b0d10;
        padding: 2 4;
    }

    #edit-heading {
        height: auto;
        color: #f0f4f8;
        text-style: bold;
    }

    #edit-subtitle {
        height: auto;
        color: #6f7885;
        margin-bottom: 2;
    }

    #edit-form {
        height: 1fr;
        max-width: 76;
    }

    .edit-section-title {
        height: auto;
        color: #8d98a6;
        text-style: bold;
        margin: 2 0 1 0;
    }

    .field-row {
        height: 3;
        margin-bottom: 1;
    }

    .field-label {
        width: 12;
        height: 3;
        content-align: left middle;
        color: #7c8794;
    }

    .field-row Input,
    .field-row Select {
        width: 1fr;
        height: 3;
        background: #10141a;
        border: none;
    }

    #edit-actions {
        height: 4;
        max-width: 76;
        align-horizontal: right;
        border-top: solid #1c2129;
        padding-top: 1;
    }

    #edit-actions Button {
        width: 10;
        height: 3;
        margin-left: 1;
        border: none;
        background: transparent;
        color: #8d98a6;
    }

    #edit-save {
        background: #162435;
        color: #9fd3ff;
    }

    ConfirmDeleteScreen {
        align: center middle;
        background: #000000 60%;
    }

    #delete-dialog {
        width: 52;
        height: auto;
        padding: 1 2;
        background: #11161d;
        border: solid #2a313b;
    }

    #delete-title {
        height: auto;
        text-style: bold;
        color: #f0f4f8;
        margin-bottom: 1;
    }

    #delete-message {
        height: auto;
        color: #87919d;
        margin-bottom: 2;
    }

    #delete-actions {
        height: 3;
        align-horizontal: right;
    }

    #delete-actions Button {
        width: 10;
        height: 3;
        margin-left: 1;
        border: none;
    }

    Footer {
        background: #0b0d10;
        color: #69727f;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.repository = Repository()

    def compose(self) -> ComposeResult:
        yield Static("xingyuan / student workspace", id="topbar")
        with Horizontal(id="body"):
            with Vertical(id="nav"):
                yield Static("xy / sis", id="nav-brand")
                yield Button("总览", id="nav-overview", classes="nav-item active")
                yield Button("学生", id="nav-students", classes="nav-item")
                yield Button("教务", id="nav-academics", classes="nav-item")
                yield Button("课程", id="nav-courses", classes="nav-item")
                yield Button("成绩", id="nav-grades", classes="nav-item")
                yield Button("数据", id="nav-reports", classes="nav-item")
            with ContentSwitcher(initial="overview-page", id="content-switcher"):
                yield OverviewPage(self.repository, id="overview-page")
                yield StudentsPage(self.repository, id="students-page")
                yield AcademicsPage(self.repository, id="academics-page")
                yield CoursePage(self.repository, id="courses-page")
                yield GradePage(self.repository, id="grades-page")
                yield ReportsPage(id="reports-page")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        pages = {
            "nav-overview": "overview-page",
            "nav-students": "students-page",
            "nav-academics": "academics-page",
            "nav-courses": "courses-page",
            "nav-grades": "grades-page",
            "nav-reports": "reports-page",
        }
        target = pages.get(event.button.id)
        if target is None:
            return

        for button in self.query(".nav-item"):
            button.remove_class("active")
        event.button.add_class("active")
        self.query_one("#content-switcher", ContentSwitcher).current = target
