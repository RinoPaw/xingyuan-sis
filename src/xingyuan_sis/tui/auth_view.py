"""Native authentication screens for the full-screen TUI."""
from __future__ import annotations

from pathlib import Path
import sys
import time
from typing import Mapping

from ..auth import (
    ADMIN_USERNAME,
    Identity,
    authenticate,
    change_password as set_password,
    clear_session,
    has_admin,
    initialize_admin,
    write_session,
)
from ..terminal_input import input_style, read_input
from . import animation, keys, screen, theme
from .board import Board


_FIELD_WIDTH = 40
_LABEL_WIDTH = 10


def login(db_path: Path | str | None) -> Identity | None:
    """Initialize the administrator when needed, then show the TUI login page."""
    initialized = False
    if not has_admin():
        if not _initialize_admin(db_path):
            return None
        initialized = True

    message = "管理员已创建。" if initialized else ""
    while True:
        values = {"username": "", "password": ""}
        username = _read_field(
            "login", values, "username", "账号", database=_database_name(db_path), message=message
        )
        if username is None:
            return None
        username = username.strip() or ADMIN_USERNAME
        values["username"] = username

        password = _read_field(
            "login", values, "password", "密码", secret=True,
            database=_database_name(db_path), message="",
        )
        if password is None:
            return None
        identity = authenticate(db_path, username, password)
        if identity is None:
            message = "账号或密码错误。"
            continue

        if identity.must_change_password:
            updated = change_password(db_path, identity, forced=True)
            if updated is None:
                message = "请先修改密码。"
                continue
            identity = updated

        write_session(identity, db_path)
        return identity


def change_password(
    db_path: Path | str | None,
    identity: Identity,
    *,
    forced: bool = False,
) -> Identity | None:
    """Change a password inside the TUI; forced mode is used on first login."""
    mode = "forced-password" if forced else "password"
    values = {"current": "", "password": "", "confirm": ""}
    message = "首次登录，请设置新密码。" if forced else ""

    if not forced:
        while True:
            current = _read_field(
                mode, values, "current", "当前密码", secret=True,
                database=_database_name(db_path), message=message,
            )
            if current is None:
                return identity
            values["current"] = current
            if authenticate(db_path, identity.username, current) is not None:
                break
            message = "当前密码错误。"

    while True:
        password = _read_field(
            mode, values, "password", "设置密码", secret=True,
            database=_database_name(db_path), message=message,
        )
        if password is None:
            return None if forced else identity
        values["password"] = password

        confirm = _read_field(
            mode, values, "confirm", "确认密码", secret=True,
            database=_database_name(db_path), message="",
        )
        if confirm is None:
            return None if forced else identity
        values["confirm"] = confirm
        if password != confirm:
            values["password"] = ""
            values["confirm"] = ""
            message = "两次密码不一致。"
            continue

        try:
            updated = set_password(db_path, identity, password)
        except ValueError as error:
            values["password"] = ""
            values["confirm"] = ""
            message = str(error)
            continue

        write_session(updated, db_path)
        if not forced:
            _wait_message(
                mode,
                values,
                "密码已修改。",
                database=_database_name(db_path),
            )
        return updated


def frame(
    mode: str,
    values: Mapping[str, str],
    *,
    active: str = "",
    message: str = "",
    database: str = "xingyuan.db",
    phase: float = 0.35,
) -> screen.ScreenFrame:
    """Render an authentication page without reading input."""
    terminal = screen._terminal_size()
    width, height = max(1, terminal.columns - 1), max(5, terminal.lines)
    fields = _fields(mode)
    left, top, field_width = _layout(width, height, len(fields))

    board = Board(width, height)
    board.put(0, 0, _topbar(width, database))
    footer, regions = theme.footer(
        width,
        (("Enter 确认", "Enter", "select"), ("Esc 退出" if mode in {"login", "initialize"} else "Esc 返回", "Esc", "back")),
        height,
    )
    board.put(0, height - 1, footer)
    board.regions.extend(regions)

    title = _title(mode)
    board.put(left, top, title, screen._BOLD + screen._TEXT_ACCENT, width=field_width)

    field_top = top + 2
    label_width = min(_LABEL_WIDTH, max(1, field_width // 3))
    box_width = max(4, field_width - label_width - 2)
    protected_cells: set[tuple[int, int]] = set()
    for index, (key, label, secret, editable) in enumerate(fields):
        row = field_top + index * 2
        if row >= height - 1:
            break
        value = values.get(key, "")
        if secret and value:
            shown = "•" * min(len(value), max(1, box_width - 2))
        elif value:
            shown = str(value)
        elif key == "username" and mode == "login":
            shown = ADMIN_USERNAME
        else:
            shown = ""

        label_style = screen._TEXT_PRIMARY if key == active else screen._TEXT_SECONDARY
        label_text = screen._ansi(screen._pad_cells(label, label_width), label_style)
        if editable:
            box_text = screen._pad_cells(screen._clip_cells(f" {shown}", box_width), box_width)
            box_style = (
                screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
                if key == active
                else screen._SURFACE_INTERACTIVE + screen._TEXT_PRIMARY
            )
            line = label_text + "  " + screen._ansi(box_text, box_style)
            box_x = left + label_width + 2
            protected_cells.update((row, box_x + offset) for offset in range(box_width))
        else:
            value_text = screen._ansi(screen._clip_cells(shown, box_width), screen._TEXT_PRIMARY)
            line = label_text + "  " + value_text
        board.put(left, row, line, width=field_width)

    message_row = field_top + len(fields) * 2
    if message and message_row < height - 1:
        board.put(left, message_row, message, screen._TEXT_ACCENT, width=field_width)

    return animation._starlight(board.frame(), width, phase, protected_cells)


def _initialize_admin(db_path: Path | str | None) -> bool:
    message = ""
    while True:
        values = {"username": ADMIN_USERNAME, "password": "", "confirm": ""}
        password = _read_field(
            "initialize", values, "password", "设置密码", secret=True,
            database=_database_name(db_path), message=message,
        )
        if password is None:
            return False
        values["password"] = password

        confirm = _read_field(
            "initialize", values, "confirm", "确认密码", secret=True,
            database=_database_name(db_path), message="",
        )
        if confirm is None:
            return False
        if password != confirm:
            message = "两次密码不一致。"
            continue
        try:
            initialize_admin(password)
        except ValueError as error:
            message = str(error)
            continue
        clear_session()
        return True


def _read_field(
    mode: str,
    values: Mapping[str, str],
    key: str,
    label: str,
    *,
    secret: bool = False,
    database: str,
    message: str,
) -> str | None:
    width, height = max(1, screen._terminal_size().columns - 1), max(5, screen._terminal_size().lines)
    fields = _fields(mode)
    left, top, field_width = _layout(width, height, len(fields))
    field_index = next(index for index, field in enumerate(fields) if field[0] == key)
    row = min(height - 2, top + 2 + field_index * 2)
    label_width = min(_LABEL_WIDTH, max(1, field_width // 3))
    box_width = max(4, field_width - label_width - 2)
    prompt = " " * max(0, left - 2) + screen._pad_cells(label, label_width) + "  "

    rendered = frame(
        mode, values, active=key, message=message, database=database, phase=_phase()
    )
    screen._paint(rendered.lines)
    previous_lines = rendered.lines

    def refresh(current: str) -> None:
        nonlocal previous_lines
        current_values = dict(values)
        current_values[key] = current
        animated = frame(
            mode,
            current_values,
            active=key,
            message=message,
            database=database,
            phase=_phase(),
        )
        screen._paint(animated.lines, previous_lines)
        previous_lines = animated.lines
        _move_cursor_to_row(row)

    try:
        _move_cursor_to_row(row)
        with input_style(True):
            return read_input(
                prompt,
                secret=secret,
                field_width=box_width,
                on_idle=refresh,
                idle_interval=animation._SPARKLE_FRAME,
            )
    except (KeyboardInterrupt, EOFError):
        return None


def _wait_message(
    mode: str,
    values: Mapping[str, str],
    message: str,
    *,
    database: str,
) -> None:
    previous_lines: list[str] = []
    while True:
        rendered = frame(
            mode, values, message=message, database=database, phase=_phase()
        )
        screen._paint(rendered.lines, previous_lines)
        previous_lines = rendered.lines
        try:
            key = keys._read_key(animation._SPARKLE_FRAME)
        except (KeyboardInterrupt, EOFError):
            return
        if key in {"select", "back"}:
            return


def _move_cursor_to_row(row: int) -> None:
    if not sys.stdout.isatty():
        return
    sys.stdout.write(f"\x1b[{row + 1};1H{screen._RESET}{screen._SURFACE}\x1b[2K")
    sys.stdout.flush()


def _phase() -> float:
    return time.monotonic() * 0.85


def _fields(mode: str) -> tuple[tuple[str, str, bool, bool], ...]:
    if mode == "initialize":
        return (
            ("username", "账号", False, False),
            ("password", "设置密码", True, True),
            ("confirm", "确认密码", True, True),
        )
    if mode == "login":
        return (
            ("username", "账号", False, True),
            ("password", "密码", True, True),
        )
    if mode == "forced-password":
        return (
            ("password", "设置密码", True, True),
            ("confirm", "确认密码", True, True),
        )
    return (
        ("current", "当前密码", True, True),
        ("password", "设置密码", True, True),
        ("confirm", "确认密码", True, True),
    )


def _title(mode: str) -> str:
    if mode == "initialize":
        return "管理员设置"
    if mode == "login":
        return "登录"
    if mode == "forced-password":
        return "设置新密码"
    return "修改密码"


def _layout(width: int, height: int, field_count: int) -> tuple[int, int, int]:
    field_width = min(_FIELD_WIDTH, max(12, width - 4))
    left = max(0, (width - field_width) // 2)
    body_height = 3 + field_count * 2
    top = max(1, (height - 1 - body_height) // 2)
    return left, top, field_width


def _topbar(width: int, database: str) -> str:
    return theme.topbar(width, database=database)


def _database_name(db_path: Path | str | None) -> str:
    return Path(db_path).name if db_path else "xingyuan.db"
