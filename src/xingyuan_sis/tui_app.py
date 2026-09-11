from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, Footer, Static

from .academics import AcademicsPage
from .app import XingyuanSIS as _BaseApp
from .courses import CoursesPage
from .data_workspace import DataPage
from .grades import GradesPage
from .service import XingyuanService
from .workspace import OverviewPage, StudentsPage


class XingyuanSIS(_BaseApp):
    """Modern TUI wired to the same application service as the CLI."""

    def __init__(self, service: XingyuanService | None = None) -> None:
        super().__init__()
        self.service = service or XingyuanService()
        # Existing page classes use repository-like methods. XingyuanService
        # deliberately exposes those methods while centralising newer logic.
        self.repository = self.service

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
                yield OverviewPage(self.service, id="overview-page")
                yield StudentsPage(self.service, id="students-page")
                yield AcademicsPage(self.service, id="academics-page")
                yield CoursesPage(self.service, id="courses-page")
                yield GradesPage(self.service, id="grades-page")
                yield DataPage(self.service, id="reports-page")
        yield Footer()
