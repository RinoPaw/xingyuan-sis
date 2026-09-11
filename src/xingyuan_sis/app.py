from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, Footer, Header, Static

from .repository import Repository
from .reports_view import ReportsPage
from .views import AcademicsPage, CoursePage, GradePage, StudentPage


class XingyuanSIS(App[None]):
    TITLE = "星原大学学生信息管理系统"
    BINDINGS = [("q", "quit", "退出")]

    CSS = """
    #body {
        height: 1fr;
    }

    #nav {
        width: 22;
        padding: 1;
        border-right: solid $primary;
    }

    #nav Button {
        width: 100%;
        margin-bottom: 1;
    }

    ContentSwitcher {
        width: 1fr;
        height: 1fr;
    }

    .page-title {
        text-style: bold;
        margin: 1 0;
    }

    .section-title {
        text-style: bold;
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
        height: 16;
        margin-bottom: 1;
    }

    #content-switcher > * {
        padding: 1 2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.repository = Repository()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with Vertical(id="nav"):
                yield Static("功能")
                yield Button("学生管理", id="nav-students", variant="primary")
                yield Button("学院 / 专业 / 班级", id="nav-academics")
                yield Button("课程管理", id="nav-courses")
                yield Button("成绩管理", id="nav-grades")
                yield Button("查询与统计", id="nav-reports")
            with ContentSwitcher(initial="students-page", id="content-switcher"):
                yield StudentPage(self.repository, id="students-page")
                yield AcademicsPage(self.repository, id="academics-page")
                yield CoursePage(self.repository, id="courses-page")
                yield GradePage(self.repository, id="grades-page")
                yield ReportsPage(id="reports-page")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        pages = {
            "nav-students": "students-page",
            "nav-academics": "academics-page",
            "nav-courses": "courses-page",
            "nav-grades": "grades-page",
            "nav-reports": "reports-page",
        }
        target = pages.get(event.button.id)
        if target is not None:
            self.query_one("#content-switcher", ContentSwitcher).current = target
