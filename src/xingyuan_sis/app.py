from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, Footer, Static

from .repository import Repository
from .reports_view import ReportsPage
from .views import AcademicsPage, CoursePage, GradePage, StudentPage


class XingyuanSIS(App[None]):
    TITLE = "星原大学学生信息管理系统"
    BINDINGS = [("q", "quit", "退出")]

    ORBIT_FRAMES = (
        "      ●      \n  ·       ·  \n ·    ◇    · \n  ·       ·  \n      ·      ",
        "      ·      \n  ·       ●  \n ·    ◆    · \n  ·       ·  \n      ·      ",
        "      ·      \n  ·       ·  \n ·    ◇    ● \n  ·       ·  \n      ·      ",
        "      ·      \n  ·       ·  \n ·    ◆    · \n  ·       ●  \n      ·      ",
        "      ·      \n  ·       ·  \n ·    ◇    · \n  ·       ·  \n      ●      ",
        "      ·      \n  ·       ·  \n ·    ◆    · \n  ●       ·  \n      ·      ",
        "      ·      \n  ·       ·  \n ●    ◇    · \n  ·       ·  \n      ·      ",
        "      ·      \n  ●       ·  \n ·    ◆    · \n  ·       ·  \n      ·      ",
    )

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
        width: 26;
        padding: 1 2;
        background: #0b0d10;
        border-right: solid #1c2129;
    }

    #brand-mark {
        width: 100%;
        height: 7;
        content-align: center middle;
        text-align: center;
        color: #77bdfb;
        margin-top: 1;
    }

    #brand-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: #eef2f7;
    }

    #brand-subtitle {
        width: 100%;
        text-align: center;
        color: #606975;
        margin-bottom: 2;
    }

    #nav Button {
        width: 100%;
        height: 3;
        margin: 0;
        padding: 0 1;
        background: transparent;
        color: #7c8591;
        border: none;
        text-align: left;
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

    .page-title {
        text-style: bold;
        color: #eef2f7;
        margin: 1 0;
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
        height: 16;
        margin-bottom: 1;
        background: #0d1014;
    }

    #content-switcher > * {
        padding: 1 2;
    }

    Footer {
        background: #0b0d10;
        color: #69727f;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.repository = Repository()
        self._orbit_frame = 0

    def compose(self) -> ComposeResult:
        yield Static("xingyuan / sis   ·   local workspace", id="topbar")
        with Horizontal(id="body"):
            with Vertical(id="nav"):
                yield Static(self.ORBIT_FRAMES[0], id="brand-mark")
                yield Static("星原大学", id="brand-title")
                yield Static("student information", id="brand-subtitle")
                yield Button("01  学生", id="nav-students", classes="nav-item active")
                yield Button("02  学院 / 专业 / 班级", id="nav-academics", classes="nav-item")
                yield Button("03  课程", id="nav-courses", classes="nav-item")
                yield Button("04  成绩", id="nav-grades", classes="nav-item")
                yield Button("05  查询 / 统计", id="nav-reports", classes="nav-item")
            with ContentSwitcher(initial="students-page", id="content-switcher"):
                yield StudentPage(self.repository, id="students-page")
                yield AcademicsPage(self.repository, id="academics-page")
                yield CoursePage(self.repository, id="courses-page")
                yield GradePage(self.repository, id="grades-page")
                yield ReportsPage(id="reports-page")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.14, self._advance_brand_animation)

    def _advance_brand_animation(self) -> None:
        self._orbit_frame = (self._orbit_frame + 1) % len(self.ORBIT_FRAMES)
        self.query_one("#brand-mark", Static).update(
            self.ORBIT_FRAMES[self._orbit_frame]
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        pages = {
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
