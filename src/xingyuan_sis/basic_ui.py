from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Callable

from .terminal_ui import read_number, run_action, run_command, search_grades, search_students


def _clear() -> None:
    if os.name == "nt":
        os.system("cls")
    elif sys.stdout.isatty():
        print("\x1b[2J\x1b[H", end="", flush=True)


def _read(label: str) -> str:
    return input(f"{label}: ").strip()


def _command(db_path: Path | str | None, argv: list[str]) -> None:
    run_command(db_path, argv, _clear)


def _menu(
    title: str,
    items: list[tuple[str, str, Callable[[], None]]],
    *,
    back_label: str = "返回",
) -> None:
    notice = ""
    while True:
        _clear()
        path = "首页" if title == "首页" else f"首页 / {title}"
        print(f"✦ 星原 / 教务台\n{path}\n")
        for key, label, _ in items:
            print(f"{key}. {label}")
        print(f"0. {back_label}")
        if notice:
            print(f"\n{notice}")
        try:
            choice = input(f"\n输入编号 · q {back_label} > ").strip().lower()
        except KeyboardInterrupt:
            return
        if choice in {"0", "q"}:
            return
        action = next((action for key, _, action in items if key == choice), None)
        if action is not None:
            notice = ""
            run_action(action, _clear)
        else:
            notice = "没有这个选项，请输入菜单中的编号。"


def _students(db_path: Path | str | None) -> None:
    def show() -> None:
        no = _read("学号")
        if no:
            _command(db_path, ["stu", "show", no])

    def edit() -> None:
        no = _read("学号")
        if no:
            _command(db_path, ["stu", "edit", no])

    def remove() -> None:
        no = _read("学号")
        if no:
            _command(db_path, ["stu", "rm", no])

    _menu(
        "学生",
        [
            ("1", "学生列表", lambda: _command(db_path, ["stu", "ls"])),
            ("2", "查看学生", show),
            ("3", "新建学生", lambda: _command(db_path, ["stu", "add"])),
            ("4", "编辑学生", edit),
            ("5", "删除学生", remove),
            ("6", "搜索学生", lambda: search_students(lambda argv: _command(db_path, argv))),
        ],
    )


def _academic_entity(db_path: Path | str | None, entity: str, title: str) -> None:
    def add() -> None:
        _command(db_path, [entity, "add"])

    def edit() -> None:
        code = _read("编号")
        if not code:
            return
        argv = [entity, "edit", code]
        new_code = _read("新编号（留空不改）")
        name = _read("新名称（留空不改）")
        if new_code:
            argv += ["--new-code", new_code]
        if name:
            argv += ["--name", name]
        if entity == "major":
            college = _read("新学院编号（留空不改）")
            if college:
                argv += ["--college", college]
        elif entity == "class":
            major = _read("新专业编号（留空不改）")
            year = read_number("新入学年份（留空不改）", integer=True, minimum=1900)
            if major:
                argv += ["--major", major]
            if year:
                argv += ["--year", year]
        _command(db_path, argv)

    def remove() -> None:
        code = _read("编号")
        if code:
            _command(db_path, [entity, "rm", code])

    _menu(
        title,
        [
            ("1", "列表", lambda: _command(db_path, [entity, "ls"])),
            ("2", "新建", add),
            ("3", "编辑", edit),
            ("4", "删除", remove),
        ],
    )


def _academics(db_path: Path | str | None) -> None:
    _menu(
        "教务",
        [
            ("1", "学院", lambda: _academic_entity(db_path, "college", "教务 / 学院")),
            ("2", "专业", lambda: _academic_entity(db_path, "major", "教务 / 专业")),
            ("3", "班级", lambda: _academic_entity(db_path, "class", "教务 / 班级")),
        ],
    )


def _courses(db_path: Path | str | None) -> None:
    def show() -> None:
        code = _read("课程编号")
        if code:
            _command(db_path, ["course", "show", code])

    def edit() -> None:
        code = _read("课程编号")
        if not code:
            return
        argv = ["course", "edit", code]
        new_code = _read("新课程编号（留空不改）")
        name = _read("新名称（留空不改）")
        department = _read("新学院编号（留空不改）")
        credits = read_number("新学分（留空不改）")
        hours = read_number("新课时（留空不改）", integer=True)
        if new_code:
            argv += ["--new-code", new_code]
        if name:
            argv += ["--name", name]
        if department:
            argv += ["--department", department]
        if credits:
            argv += ["--credits", credits]
        if hours:
            argv += ["--hours", hours]
        _command(db_path, argv)

    def remove() -> None:
        code = _read("课程编号")
        if code:
            _command(db_path, ["course", "rm", code])

    _menu(
        "课程",
        [
            ("1", "课程列表", lambda: _command(db_path, ["course", "ls"])),
            ("2", "查看课程", show),
            ("3", "新建课程", lambda: _command(db_path, ["course", "add"])),
            ("4", "编辑课程", edit),
            ("5", "删除课程", remove),
        ],
    )


def _grades(db_path: Path | str | None) -> None:
    def edit() -> None:
        student = _read("学号")
        course = _read("课程编号")
        semester = _read("学期")
        if not all((student, course, semester)):
            return
        score = read_number("新成绩（输入 - 清空，留空保持）", maximum=100, clearable=True)
        argv = ["grade", "edit", student, course, semester]
        if score == "-":
            argv.append("--clear-score")
        elif score:
            argv += ["--score", score]
        _command(db_path, argv)

    def remove() -> None:
        student = _read("学号")
        course = _read("课程编号")
        semester = _read("学期")
        if all((student, course, semester)):
            _command(db_path, ["grade", "rm", student, course, semester])

    _menu(
        "成绩",
        [
            ("1", "成绩列表", lambda: _command(db_path, ["grade", "ls"])),
            ("2", "添加选课 / 成绩", lambda: _command(db_path, ["grade", "add"])),
            ("3", "编辑成绩", edit),
            ("4", "删除选课", remove),
            ("5", "搜索成绩", lambda: search_grades(lambda argv: _command(db_path, argv))),
        ],
    )


def _data(db_path: Path | str | None) -> None:
    def export() -> None:
        path = _read("导出文件") or "data/students.csv"
        _command(db_path, ["data", "export", path])

    def import_() -> None:
        path = _read("导入文件") or "data/students.csv"
        _command(db_path, ["data", "import", path])

    _menu(
        "数据",
        [
            ("1", "统计摘要", lambda: _command(db_path, ["data", "stats"])),
            ("2", "导出学生 CSV", export),
            ("3", "导入学生 CSV", import_),
            ("4", "写入演示数据", lambda: _command(db_path, ["data", "seed"])),
        ],
    )


def run(db_path: Path | str | None = None) -> None:
    try:
        _menu("首页", [
            ("1", "学生", lambda: _students(db_path)),
            ("2", "教务", lambda: _academics(db_path)),
            ("3", "课程", lambda: _courses(db_path)),
            ("4", "成绩", lambda: _grades(db_path)),
            ("5", "数据", lambda: _data(db_path)),
        ], back_label="退出")
    except EOFError:
        print("\n已退出星原 SIS。")
