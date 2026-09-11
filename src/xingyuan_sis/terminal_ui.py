"""Shared interaction helpers for the keyboard and basic menus."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import math
from pathlib import Path
import shutil
from typing import Callable
import unicodedata


def _wrap_line(line: str, width: int) -> list[str]:
    parts: list[str] = []
    part = ""
    used = 0
    for char in line.expandtabs(4):
        cells = 0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        if part and used + cells > width:
            parts.append(part)
            part, used = "", 0
        part += char
        used += cells
    parts.append(part)
    return parts


def show_output(text: str, clear: Callable[[], None]) -> None:
    terminal = shutil.get_terminal_size((80, 24))
    lines = [part for line in text.rstrip("\n").splitlines()
             for part in _wrap_line(line, max(2, terminal.columns - 1))]
    page_size = max(1, terminal.lines - 5)
    pages = max(1, (len(lines) + page_size - 1) // page_size)
    page = 0
    while True:
        clear()
        print("\n".join(lines[page * page_size:(page + 1) * page_size]))
        if pages == 1:
            input("\n按 Enter 返回…")
            return
        print(f"\n第 {page + 1}/{pages} 页 · 共 {len(lines)} 行")
        next_hint = "Enter/n 返回" if page == pages - 1 else "Enter/n 下一页"
        key = input(f"{next_hint} · p 上一页 · q 返回：").strip().lower()
        if key in {"q", "0"}:
            return
        if key in {"", "n"}:
            if page == pages - 1:
                return
            page += 1
        elif key == "p":
            page = max(0, page - 1)


def run_command(
    db_path: Path | str | None,
    argv: list[str],
    clear: Callable[[], None],
) -> None:
    from .entry import main

    clear()
    args = ([] if db_path is None else ["--db", str(db_path)]) + argv
    # Only capture read-only commands: form prompts must remain visible.
    action_index = 2 if argv[0] == "acad" else 1
    paginate = len(argv) > action_index and argv[action_index] in {"ls", "show", "stats"}
    output = StringIO()
    try:
        if paginate:
            with redirect_stdout(output):
                code = main(args)
        else:
            print("Ctrl+C 取消当前操作，返回菜单。\n")
            code = main(args)
    except SystemExit as error:
        code = int(error.code or 0)
    if paginate and code == 0:
        show_output(output.getvalue(), clear)
        return
    if output.getvalue():
        print(output.getvalue(), end="")
    if code and code != 130:
        print("\n操作未完成，请按上方提示检查后重试。")
    input("\n按 Enter 返回…")


def run_action(action: Callable[[], None], clear: Callable[[], None]) -> None:
    clear()
    print("Ctrl+C 取消当前操作，返回菜单。\n")
    try:
        action()
    except KeyboardInterrupt:
        print("\n已取消当前操作。")


def search_students(command: Callable[[list[str]], None]) -> None:
    keyword = input("搜索学生（学号、姓名、班级等；留空返回）：").strip()
    if keyword:
        command(["stu", "ls", "--search", keyword])


def search_grades(command: Callable[[list[str]], None]) -> None:
    keyword = input("搜索成绩（学号、姓名、课程、学期；留空返回）：").strip()
    if keyword:
        command(["grade", "ls", "--search", keyword])


def read_number(
    label: str,
    *,
    integer: bool = False,
    minimum: float = 0,
    maximum: float | None = None,
    clearable: bool = False,
) -> str:
    while True:
        raw = input(f"{label}: ").strip()
        if not raw or (clearable and raw == "-"):
            return raw
        try:
            value = int(raw) if integer else float(raw)
            if math.isfinite(value) and value >= minimum and (maximum is None or value <= maximum):
                return raw
        except ValueError:
            pass
        kind = "整数" if integer else "数字"
        bounds = f"{minimum:g}～{maximum:g}" if maximum is not None else f"不小于 {minimum:g}"
        print(f"请输入{bounds}的{kind}；留空保持原值。")
