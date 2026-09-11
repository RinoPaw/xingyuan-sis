from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Input, Static

from .csv_io import export_students_csv, import_students_csv
from .reports import class_student_counts, course_score_stats, element_distribution, summary


def _show(value: object) -> str:
    return "" if value is None else str(value)


class ReportsPage(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static("查询与统计", classes="page-title")
        yield Static("", id="summary-text")
        with Horizontal(classes="actions"):
            yield Button("刷新统计", id="reports-refresh", variant="primary")
            yield Input(value="data/students.csv", placeholder="CSV 文件路径", id="csv-path")
            yield Button("导出学生 CSV", id="csv-export", variant="success")
            yield Button("导入学生 CSV", id="csv-import")
        yield Static("班级人数", classes="section-title")
        yield DataTable(id="class-count-table", zebra_stripes=True)
        yield Static("主元素亲和分布", classes="section-title")
        yield DataTable(id="element-table", zebra_stripes=True)
        yield Static("课程成绩统计", classes="section-title")
        yield DataTable(id="course-stat-table", zebra_stripes=True)

    def on_mount(self) -> None:
        self.query_one("#class-count-table", DataTable).add_columns("班级编号", "班级", "专业", "人数")
        self.query_one("#element-table", DataTable).add_columns("主元素", "人数")
        self.query_one("#course-stat-table", DataTable).add_columns(
            "课程编号", "课程", "已评分", "平均分", "最高分", "最低分"
        )
        self.refresh_reports()

    def refresh_reports(self) -> None:
        stats = summary()
        self.query_one("#summary-text", Static).update(
            "学生 {students} 人 ｜ 学院 {departments} ｜ 专业 {majors} ｜ 班级 {classes} ｜ "
            "课程 {courses} ｜ 选课 {enrollments} ｜ 平均分 {average_score} ｜ "
            "最高分 {max_score} ｜ 最低分 {min_score}".format(
                **{key: _show(value) or "-" for key, value in stats.items()}
            )
        )

        class_table = self.query_one("#class-count-table", DataTable)
        class_table.clear()
        for row in class_student_counts():
            class_table.add_row(row["code"], row["name"], row["major_name"], _show(row["student_count"]))

        element_table = self.query_one("#element-table", DataTable)
        element_table.clear()
        for row in element_distribution():
            element_table.add_row(row["element"], _show(row["student_count"]))

        course_table = self.query_one("#course-stat-table", DataTable)
        course_table.clear()
        for row in course_score_stats():
            course_table.add_row(
                row["course_code"], row["name"], _show(row["graded_count"]),
                _show(row["average_score"]), _show(row["max_score"]), _show(row["min_score"]),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        try:
            if event.button.id == "reports-refresh":
                self.refresh_reports()
            elif event.button.id == "csv-export":
                path = self.query_one("#csv-path", Input).value.strip()
                if not path:
                    raise ValueError("请输入 CSV 文件路径")
                count = export_students_csv(path)
                self.app.notify(f"已导出 {count} 条学生记录到 {path}")
            elif event.button.id == "csv-import":
                path = self.query_one("#csv-path", Input).value.strip()
                if not path:
                    raise ValueError("请输入 CSV 文件路径")
                result = import_students_csv(path)
                self.refresh_reports()
                message = f"成功导入 {result.imported} 条"
                if result.errors:
                    preview = "\n".join(result.errors[:3])
                    message += f"，失败 {len(result.errors)} 条\n{preview}"
                self.app.notify(message, title="CSV 导入结果")
        except (OSError, ValueError) as error:
            self.app.notify(str(error), title="操作失败", severity="error")
