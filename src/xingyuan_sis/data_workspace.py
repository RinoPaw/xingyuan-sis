from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, ContentSwitcher, DataTable, Input, Static

from .csv_io import export_students_csv, import_students_csv
from .reports import class_student_counts, course_score_stats, element_distribution, summary
from .repository import Repository


def _show(value: object) -> str:
    return "" if value is None else str(value)


class DataPage(VerticalScroll):
    DEFAULT_CSS = """
    DataPage {
        padding: 2 3;
    }

    #data-header {
        height: auto;
        margin-bottom: 1;
    }

    #data-header > Vertical {
        width: 1fr;
        height: auto;
    }

    #data-refresh {
        width: 10;
        height: 3;
        margin-top: 1;
        background: transparent;
        color: #87919d;
        border: none;
    }

    #data-tabs {
        height: 3;
        margin-bottom: 1;
        border-bottom: solid #1c2129;
    }

    #data-tabs Button {
        width: auto;
        min-width: 10;
        height: 3;
        margin-right: 1;
        background: transparent;
        color: #6f7885;
        border: none;
    }

    #data-tabs Button.active {
        color: #f0f4f8;
        border-bottom: solid #5aa9ff;
    }

    #data-switcher {
        height: 1fr;
    }

    #data-overview,
    #data-transfer {
        padding-top: 1;
    }

    #data-stat-row {
        height: 7;
        margin-bottom: 1;
    }

    .data-stat {
        width: 1fr;
        min-width: 11;
        height: 6;
        margin-right: 1;
        padding: 1;
        background: #10141a;
        border: solid #1b222c;
        color: #8994a1;
    }

    #data-secondary-summary {
        height: auto;
        color: #737e8a;
        margin: 1 0;
    }

    #data-distribution {
        padding-top: 1;
    }

    .data-section-title {
        height: auto;
        margin: 1 0;
        color: #8d98a6;
        text-style: bold;
    }

    #data-class-table,
    #data-element-table,
    #data-course-table {
        height: 11;
        margin-bottom: 1;
        border-top: solid #1b222c;
    }

    #data-transfer-copy {
        height: auto;
        max-width: 72;
        color: #7b8692;
        margin: 1 0 2 0;
    }

    #data-path-label {
        height: auto;
        color: #7c8794;
        margin-bottom: 1;
    }

    #data-path {
        width: 100%;
        max-width: 72;
        height: 3;
        margin-bottom: 1;
        background: #10141a;
        border: none;
    }

    #data-transfer-actions {
        height: 3;
    }

    #data-transfer-actions Button {
        width: 12;
        height: 3;
        margin-right: 1;
        border: none;
        background: transparent;
        color: #8d98a6;
    }

    #data-export {
        background: #162435;
        color: #9fd3ff;
    }
    """

    def __init__(self, repository: Repository | None = None, *, id: str) -> None:
        super().__init__(id=id)
        self.repository = repository or Repository()

    def compose(self) -> ComposeResult:
        with Horizontal(id="data-header"):
            with Vertical():
                yield Static("数据", classes="page-title")
                yield Static("查看分布、汇总和数据交换", classes="page-subtitle")
            yield Button("刷新", id="data-refresh")

        with Horizontal(id="data-tabs"):
            yield Button("概览", id="data-tab-overview", classes="active")
            yield Button("分布", id="data-tab-distribution")
            yield Button("导入导出", id="data-tab-transfer")

        with ContentSwitcher(initial="data-overview", id="data-switcher"):
            with Vertical(id="data-overview"):
                with Horizontal(id="data-stat-row"):
                    yield Static("-\n学生", id="data-stat-students", classes="data-stat")
                    yield Static("-\n课程", id="data-stat-courses", classes="data-stat")
                    yield Static("-\n选课", id="data-stat-enrollments", classes="data-stat")
                    yield Static("-\n平均成绩", id="data-stat-average", classes="data-stat")
                yield Static("", id="data-secondary-summary")

            with VerticalScroll(id="data-distribution"):
                yield Static("班级人数", classes="data-section-title")
                yield DataTable(id="data-class-table")
                yield Static("主元素分布", classes="data-section-title")
                yield DataTable(id="data-element-table")
                yield Static("课程成绩", classes="data-section-title")
                yield DataTable(id="data-course-table")

            with Vertical(id="data-transfer"):
                yield Static(
                    "学生档案可以导出为 CSV，也可以从同一格式重新导入。",
                    id="data-transfer-copy",
                )
                yield Static("文件", id="data-path-label")
                yield Input(
                    value="data/students.csv",
                    placeholder="CSV 文件路径",
                    id="data-path",
                )
                with Horizontal(id="data-transfer-actions"):
                    yield Button("导入 CSV", id="data-import")
                    yield Button("导出 CSV", id="data-export")

    def on_mount(self) -> None:
        self.query_one("#data-class-table", DataTable).add_columns(
            "班级", "专业", "人数"
        )
        self.query_one("#data-element-table", DataTable).add_columns(
            "主元素", "人数"
        )
        self.query_one("#data-course-table", DataTable).add_columns(
            "课程", "已评分", "平均", "最高", "最低"
        )
        self.refresh_data()

    def refresh_data(self) -> None:
        stats = summary(self.repository.db_path)
        self.query_one("#data-stat-students", Static).update(
            f"{_show(stats['students'])}\n学生"
        )
        self.query_one("#data-stat-courses", Static).update(
            f"{_show(stats['courses'])}\n课程"
        )
        self.query_one("#data-stat-enrollments", Static).update(
            f"{_show(stats['enrollments'])}\n选课"
        )
        self.query_one("#data-stat-average", Static).update(
            f"{_show(stats['average_score']) or '—'}\n平均成绩"
        )
        self.query_one("#data-secondary-summary", Static).update(
            "学院 {departments}  ·  专业 {majors}  ·  班级 {classes}  ·  "
            "最高 {max_score}  ·  最低 {min_score}".format(
                **{key: _show(value) or "—" for key, value in stats.items()}
            )
        )

        class_table = self.query_one("#data-class-table", DataTable)
        class_table.clear()
        for row in class_student_counts(self.repository.db_path):
            class_table.add_row(
                _show(row["name"]),
                _show(row["major_name"]),
                _show(row["student_count"]),
            )

        element_table = self.query_one("#data-element-table", DataTable)
        element_table.clear()
        for row in element_distribution(self.repository.db_path):
            element_table.add_row(
                _show(row["element"]),
                _show(row["student_count"]),
            )

        course_table = self.query_one("#data-course-table", DataTable)
        course_table.clear()
        for row in course_score_stats(self.repository.db_path):
            course_table.add_row(
                _show(row["name"]),
                _show(row["graded_count"]),
                _show(row["average_score"]) or "—",
                _show(row["max_score"]) or "—",
                _show(row["min_score"]) or "—",
            )

    def _switch_tab(self, button: Button, target: str) -> None:
        for tab in self.query("#data-tabs Button"):
            tab.remove_class("active")
        button.add_class("active")
        self.query_one("#data-switcher", ContentSwitcher).current = target

    def on_button_pressed(self, event: Button.Pressed) -> None:
        tabs = {
            "data-tab-overview": "data-overview",
            "data-tab-distribution": "data-distribution",
            "data-tab-transfer": "data-transfer",
        }
        target = tabs.get(event.button.id)
        if target is not None:
            self._switch_tab(event.button, target)
            return

        if event.button.id == "data-refresh":
            self.refresh_data()
            return

        if event.button.id not in {"data-import", "data-export"}:
            return

        path = self.query_one("#data-path", Input).value.strip()
        if not path:
            self.app.notify("请填写 CSV 文件路径", title="无法继续", severity="error")
            return

        try:
            if event.button.id == "data-export":
                count = export_students_csv(path, self.repository.db_path)
                self.app.notify(f"已导出 {count} 条学生记录")
            else:
                result = import_students_csv(path, self.repository.db_path)
                self.refresh_data()
                if result.errors:
                    self.app.notify(
                        f"导入 {result.imported} 条，另有 {len(result.errors)} 条失败",
                        title="导入完成",
                    )
                else:
                    self.app.notify(f"已导入 {result.imported} 条学生记录")
        except (OSError, ValueError) as error:
            self.app.notify(str(error), title="操作失败", severity="error")
