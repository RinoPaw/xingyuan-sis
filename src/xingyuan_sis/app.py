from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static


class XingyuanSIS(App[None]):
    TITLE = "星原大学学生信息管理系统"
    BINDINGS = [("q", "quit", "退出")]

    CSS = """
    #body {
        height: 1fr;
    }

    #nav {
        width: 24;
        padding: 1;
        border-right: solid $primary;
    }

    #nav Button {
        width: 100%;
        margin-bottom: 1;
    }

    #content {
        width: 1fr;
        padding: 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with Vertical(id="nav"):
                yield Button("学生管理", id="students")
                yield Button("学院与班级", id="academics")
                yield Button("课程管理", id="courses")
                yield Button("成绩管理", id="grades")
                yield Button("查询与统计", id="reports")
            yield Static(
                "欢迎使用星原大学学生信息管理系统。\n\n"
                "请选择左侧功能。",
                id="content",
            )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        pages = {
            "students": "学生管理\n\n此模块待实现。",
            "academics": "学院、专业与班级管理\n\n此模块待实现。",
            "courses": "课程管理\n\n此模块待实现。",
            "grades": "成绩管理\n\n此模块待实现。",
            "reports": "查询与统计\n\n此模块待实现。",
        }
        content = pages.get(event.button.id, "此模块待实现。")
        self.query_one("#content", Static).update(content)
