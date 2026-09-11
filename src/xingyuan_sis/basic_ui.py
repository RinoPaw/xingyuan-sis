from __future__ import annotations

import os
from pathlib import Path
from typing import Callable


def _clear() -> None:
    command = "cls" if os.name == "nt" else "clear"
    result = os.system(command)
    if result != 0:
        print("\n" * 40)


def _pause() -> None:
    input("\n按 Enter 继续…")


def _read(label: str) -> str:
    return input(f"{label}: ").strip()


def _db_args(db_path: Path | str | None) -> list[str]:
    return [] if db_path is None else ["--db", str(db_path)]


def _command(db_path: Path | str | None, argv: list[str]) -> None:
    from .cli import main as cli_main

    _clear()
    try:
        code = cli_main([*_db_args(db_path), *argv])
    except SystemExit as error:
        code = int(error.code or 0)
    if code:
        print(f"\n命令返回状态 {code}")
    _pause()


def _menu(title: str, items: list[tuple[str, str, Callable[[], None]]]) -> None:
    while True:
        _clear()
        print(f"星原 SIS / {title}\n")
        for key, label, _ in items:
            print(f"{key}. {label}")
        print("0. 返回")
        choice = input("\n> ").strip()
        if choice == "0":
            return
        action = next((action for key, _, action in items if key == choice), None)
        if action is not None:
            action()


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
        ],
    )


def _academic_entity(db_path: Path | str | None, entity: str, title: str) -> None:
    def add() -> None:
        _command(db_path, ["acad", entity, "add"])

    def edit() -> None:
        code = _read("编号")
        if not code:
            return
        argv = ["acad", entity, "edit", code]
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
            year = _read("新入学年份（留空不改）")
            if major:
                argv += ["--major", major]
            if year:
                argv += ["--year", year]
        _command(db_path, argv)

    def remove() -> None:
        code = _read("编号")
        if code:
            _command(db_path, ["acad", entity, "rm", code])

    _menu(
        title,
        [
            ("1", "列表", lambda: _command(db_path, ["acad", entity, "ls"])),
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
        credits = _read("新学分（留空不改）")
        hours = _read("新课时（留空不改）")
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
        score = _read("新成绩（输入 - 清空，留空保持）")
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
        ],
    )


def run(db_path: Path | str | None = None) -> None:
    while True:
        _clear()
        print("星原 SIS\n")
        print("1. 学生")
        print("2. 教务")
        print("3. 课程")
        print("4. 成绩")
        print("5. 数据")
        print("0. 退出")
        choice = input("\n> ").strip()
        if choice == "0":
            return
        actions = {
            "1": lambda: _students(db_path),
            "2": lambda: _academics(db_path),
            "3": lambda: _courses(db_path),
            "4": lambda: _grades(db_path),
            "5": lambda: _data(db_path),
        }
        action = actions.get(choice)
        if action is not None:
            action()
