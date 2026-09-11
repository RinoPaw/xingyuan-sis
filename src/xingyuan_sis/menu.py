from __future__ import annotations

import os
from pathlib import Path
import select
import sys
from typing import Callable, Sequence


_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_ACCENT = "\x1b[36m"
_DIM = "\x1b[2m"


def _ansi(text: str, style: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR") is not None:
        return text
    return f"{style}{text}{_RESET}"


def _clear() -> None:
    if sys.stdout.isatty():
        print("\x1b[2J\x1b[H", end="", flush=True)
    else:
        print("\n" * 40)


def _read_key_windows() -> str:
    import msvcrt

    char = msvcrt.getwch()
    if char in {"\x00", "\xe0"}:
        code = msvcrt.getwch()
        if code == "H":
            return "up"
        if code == "P":
            return "down"
        return "other"
    if char in {" ", "\r", "\n"}:
        return "select"
    if char == "\x1b" or char.lower() == "q":
        return "back"
    return "other"


def _read_key_posix() -> str:
    import termios
    import tty

    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        char = sys.stdin.read(1)
        if char == "\x1b":
            sequence = ""
            while len(sequence) < 2 and select.select([sys.stdin], [], [], 0.03)[0]:
                sequence += sys.stdin.read(1)
            if sequence == "[A":
                return "up"
            if sequence == "[B":
                return "down"
            return "back"
        if char in {" ", "\r", "\n"}:
            return "select"
        if char.lower() == "q":
            return "back"
        return "other"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def _read_key() -> str:
    if os.name == "nt":
        return _read_key_windows()
    return _read_key_posix()


def _select(title: str, items: Sequence[str], *, allow_back: bool = True) -> int | None:
    if not items:
        return None
    selected = 0
    while True:
        _clear()
        print(_ansi("星原 SIS", _BOLD + _ACCENT))
        if title:
            print(_ansi(f"{title}\n", _DIM))
        else:
            print()

        for index, label in enumerate(items):
            if index == selected:
                print(f"{_ansi('›', _ACCENT)} {_ansi(label, _BOLD)}")
            else:
                print(f"  {label}")

        back_hint = "   Esc/q 返回" if allow_back else ""
        print(_ansi(f"\n↑↓ 移动   Space 确定{back_hint}", _DIM))

        key = _read_key()
        if key == "up":
            selected = (selected - 1) % len(items)
        elif key == "down":
            selected = (selected + 1) % len(items)
        elif key == "select":
            return selected
        elif key == "back" and allow_back:
            return None


def _pause() -> None:
    input("\n按 Enter 返回…")


def _read(label: str) -> str:
    return input(f"{label}: ").strip()


def _db_args(db_path: Path | str | None) -> list[str]:
    return [] if db_path is None else ["--db", str(db_path)]


def _command(db_path: Path | str | None, argv: list[str]) -> None:
    from .entry import main as entry_main

    _clear()
    try:
        code = entry_main([*_db_args(db_path), *argv])
    except SystemExit as error:
        code = int(error.code or 0)
    if code:
        print(f"\n命令返回状态 {code}")
    _pause()


def _menu(title: str, items: Sequence[tuple[str, Callable[[], None]]]) -> None:
    while True:
        choice = _select(title, [label for label, _ in items])
        if choice is None:
            return
        items[choice][1]()


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
        (
            ("学生列表", lambda: _command(db_path, ["stu", "ls"])),
            ("查看学生", show),
            ("新建学生", lambda: _command(db_path, ["stu", "add"])),
            ("编辑学生", edit),
            ("删除学生", remove),
        ),
    )


def _academic_entity(db_path: Path | str | None, entity: str, title: str) -> None:
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
        (
            ("列表", lambda: _command(db_path, ["acad", entity, "ls"])),
            ("新建", lambda: _command(db_path, ["acad", entity, "add"])),
            ("编辑", edit),
            ("删除", remove),
        ),
    )


def _academics(db_path: Path | str | None) -> None:
    _menu(
        "教务",
        (
            ("学院", lambda: _academic_entity(db_path, "college", "教务 / 学院")),
            ("专业", lambda: _academic_entity(db_path, "major", "教务 / 专业")),
            ("班级", lambda: _academic_entity(db_path, "class", "教务 / 班级")),
        ),
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
        (
            ("课程列表", lambda: _command(db_path, ["course", "ls"])),
            ("查看课程", show),
            ("新建课程", lambda: _command(db_path, ["course", "add"])),
            ("编辑课程", edit),
            ("删除课程", remove),
        ),
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
        (
            ("成绩列表", lambda: _command(db_path, ["grade", "ls"])),
            ("添加选课 / 成绩", lambda: _command(db_path, ["grade", "add"])),
            ("编辑成绩", edit),
            ("删除选课", remove),
        ),
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
        (
            ("统计摘要", lambda: _command(db_path, ["data", "stats"])),
            ("导出学生 CSV", export),
            ("导入学生 CSV", import_),
            ("写入演示数据", lambda: _command(db_path, ["data", "seed"])),
        ),
    )


def run(db_path: Path | str | None = None) -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise RuntimeError("当前环境不是交互终端；请使用 xy <command>")

    actions: tuple[Callable[[], None], ...] = (
        lambda: _students(db_path),
        lambda: _academics(db_path),
        lambda: _courses(db_path),
        lambda: _grades(db_path),
        lambda: _data(db_path),
    )
    labels = ("学生", "教务", "课程", "成绩", "数据", "退出")

    while True:
        choice = _select("", labels, allow_back=False)
        if choice == len(labels) - 1:
            _clear()
            return
        actions[choice]()
