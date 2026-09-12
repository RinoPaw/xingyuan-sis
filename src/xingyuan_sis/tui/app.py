"""Home navigation and workspace dispatch."""
from __future__ import annotations
from pathlib import Path
import sys
import time
from typing import Callable, Sequence
from . import keys, screen


def _students(db_path: Path | str | None) -> None:
    from .workspace import run as run_workspace
    run_workspace(db_path, "students")


def _academics(db_path: Path | str | None) -> None:
    from .workspace import run as run_workspace
    run_workspace(db_path, "departments")


def _courses(db_path: Path | str | None) -> None:
    from .workspace import run as run_workspace
    run_workspace(db_path, "courses")


def _grades(db_path: Path | str | None) -> None:
    from .workspace import run as run_workspace
    run_workspace(db_path, "grades")


def _data(db_path: Path | str | None) -> None:
    from .workspace import run as run_workspace
    run_workspace(db_path, "data")


def _home_frame(
    labels: Sequence[str],
    selected: int,
    stats: dict[str, object],
    angle: float,
    *,
    animate: bool = True,
    database: str = "xingyuan.db",
) -> screen.ScreenFrame:
    from .theme import home_frame

    return home_frame(labels, selected, stats, angle, animate=animate, database=database)


def _home_lines(*args, **kwargs) -> list[str]:
    return _home_frame(*args, **kwargs).lines


def _home(
    db_path: Path | str | None,
    labels: Sequence[str],
    *,
    selected: int = 0,
    preferences: dict[str, bool] | None = None,
) -> int | None:
    from ..service import XingyuanService

    stats = dict(XingyuanService(db_path).stats())
    preferences = preferences if preferences is not None else {"animate": True}
    angle = time.monotonic() * 0.85
    previous_lines: list[str] = []
    screen._clear()
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()

    try:
        with keys._mouse_tracking():
            return _home_loop(labels, stats, db_path, selected, preferences, angle, previous_lines)
    finally:
        if sys.stdout.isatty():
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()


def _home_loop(
    labels: Sequence[str], stats: dict[str, object], db_path: Path | str | None,
    selected: int, preferences: dict[str, bool], angle: float, previous_lines: list[str],
) -> int | None:
    while True:
        animate = preferences.get("animate", True)
        if animate:
            angle = time.monotonic() * 0.85
        frame = _home_frame(labels, selected, stats, angle, animate=animate,
                            database=Path(db_path).name if db_path else "xingyuan.db")
        lines = frame.lines
        if lines != previous_lines:
            screen._paint(lines, previous_lines)
            previous_lines = lines
        key = keys._read_key(0.08 if animate else 0.15)
        if isinstance(key, keys.MouseScroll):
            key = key.direction
        if isinstance(key, screen.MouseClick):
            key = screen._hit_action(key, frame.regions)
            if key and key.startswith("item:"):
                return int(key.split(":")[1])
        if key == "up":
            selected = (selected - 1) % len(labels)
        elif key == "down":
            selected = (selected + 1) % len(labels)
        elif key == "select":
            return selected
        elif key == "home":
            selected = 0
        elif key == "end":
            selected = len(labels) - 1
        elif key in tuple("123456789") and int(key) <= len(labels):
            return int(key) - 1
        elif key == "pause":
            preferences["animate"] = not animate
        elif key == "back":
            return None


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

    selected = 0
    preferences = {"animate": True}
    with screen._terminal_session():
        try:
            while True:
                choice = _home(db_path, labels, selected=selected, preferences=preferences)
                if choice is None or choice == len(labels) - 1:
                    return
                selected = choice
                try:
                    actions[choice]()
                except screen.NavigateTo as navigation:
                    if navigation.path:
                        raise
        except (KeyboardInterrupt, EOFError):
            pass
