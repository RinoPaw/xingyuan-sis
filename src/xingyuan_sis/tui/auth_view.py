"""Native authentication screens for the full-screen TUI."""
from __future__ import annotations

from pathlib import Path
import sys
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


_FIELD_WIDTH = 42


def login(db_path: Path | str | None) -> Identity | None:
    """Initialize the administrator when needed, then show the TUI login page."""
    initialized = False
    if not has_admin():
        if not _initialize_admin(db_path):
            return None
        initialized = True

    message = "管理员初始化完成，请登录。" if initialized else ""
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
                message = "首次登录必须修改密码。"
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
    message = "首次登录需要设置新的密码。" if forced else ""

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
            mode, values, "password", "新密码", secret=True,
            database=_database_name(db_path), message=message,
        )
        if password is None:
            return None if forced else identity
        values["password"] = password

        confirm = _read_field(
            mode, values, "confirm", "确认新密码", secret=True,
            database=_database_name(db_path), message="",
        )
        if confirm is None:
            return None if forced else identity
        values["confirm"] = confirm
        if password != confirm:
            values["password"] = ""
            values["confirm"] = ""
            message = "两次输入的密码不一致。"
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

    title, subtitle = _copy(mode)
    board.put(left, top, title, screen._BOLD + screen._TEXT_ACCENT, width=field_width)
    if top + 1 < height - 1:
        board.put(left, top + 1, subtitle, screen._TEXT_SECONDARY, width=field_width)

    field_top = top + 3
    for index, (key, label, secret, fixed) in enumerate(fields):
        row = field_top + index * 2
        if row >= height - 1:
            break
        value = values.get(key, "")
        if fixed:
            shown = value
        elif secret and value:
            shown = "•" * min(len(value), max(1, field_width - 14))
        elif value:
            shown = value
        elif key == "username" and mode == "login":
            shown = f"[{ADMIN_USERNAME}]"
        else:
            shown = ""
        label_text = screen._pad_cells(label, min(12, max(1, field_width // 3)))
        line = screen._pad_cells(f"{label_text}  {shown}", field_width)
        style = (
            screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
            if key == active
            else screen._SURFACE_INTERACTIVE + screen._TEXT_PRIMARY
        )
        board.put(left, row, line, style, width=field_width)

    message_row = field_top + len(fields) * 2
    if message and message_row < height - 1:
        board.put(left, message_row, message, screen._TEXT_ACCENT, width=field_width)

    return animation._starlight(board.frame(), width, 0.35)


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
            message = "两次输入的密码不一致。"
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
    rendered = frame(mode, values, active=key, message=message, database=database)
    screen._paint(rendered.lines)

    width, height = max(1, screen._terminal_size().columns - 1), max(5, screen._terminal_size().lines)
    fields = _fields(mode)
    left, top, field_width = _layout(width, height, len(fields))
    field_index = next(index for index, field in enumerate(fields) if field[0] == key)
    row = min(height - 2, top + 3 + field_index * 2)
    label_width = min(12, max(1, field_width // 3))
    prompt = " " * max(0, left - 2) + screen._pad_cells(label, label_width) + "  "

    try:
        if sys.stdout.isatty():
            sys.stdout.write(f"\x1b[{row + 1};1H{screen._RESET}{screen._SURFACE}\x1b[2K")
            sys.stdout.flush()
        with input_style(True):
            return read_input(prompt, secret=secret)
    except (KeyboardInterrupt, EOFError):
        return None


def _wait_message(
    mode: str,
    values: Mapping[str, str],
    message: str,
    *,
    database: str,
) -> None:
    rendered = frame(mode, values, message=message, database=database)
    screen._paint(rendered.lines)
    while True:
        try:
            key = keys._read_key()
        except (KeyboardInterrupt, EOFError):
            return
        if key in {"select", "back"}:
            return


def _fields(mode: str) -> tuple[tuple[str, str, bool, bool], ...]:
    if mode == "initialize":
        return (
            ("username", "管理员账号", False, True),
            ("password", "设置密码", True, False),
            ("confirm", "确认密码", True, False),
        )
    if mode == "login":
        return (
            ("username", "账号", False, False),
            ("password", "密码", True, False),
        )
    if mode == "forced-password":
        return (
            ("password", "新密码", True, False),
            ("confirm", "确认新密码", True, False),
        )
    return (
        ("current", "当前密码", True, False),
        ("password", "新密码", True, False),
        ("confirm", "确认新密码", True, False),
    )


def _copy(mode: str) -> tuple[str, str]:
    if mode == "initialize":
        return "首次初始化", "创建唯一管理员 Administrator"
    if mode == "login":
        return "登录星原", "使用管理员账号或学生学号登录"
    if mode == "forced-password":
        return "首次登录 · 修改密码", "设置新密码后即可进入星原 SIS"
    return "个人中心 · 修改密码", "更新当前账户的登录密码"


def _layout(width: int, height: int, field_count: int) -> tuple[int, int, int]:
    field_width = min(_FIELD_WIDTH, max(12, width - 4))
    left = max(0, (width - field_width) // 2)
    body_height = 4 + field_count * 2 + 1
    top = max(1, (height - 1 - body_height) // 2)
    return left, top, field_width


def _topbar(width: int, database: str) -> str:
    left = "✦ 星原 SIS"
    right = f"LOCAL / {database}"
    if screen._display_width(left) + screen._display_width(right) + 2 <= width:
        gap = width - screen._display_width(left) - screen._display_width(right)
        plain = left + " " * gap + right
    else:
        plain = screen._pad_cells(screen._clip_cells(left, width), width)
    return screen._ansi(
        screen._pad_cells(screen._clip_cells(plain, width), width),
        screen._SURFACE_TOPBAR + screen._TEXT_ACCENT + screen._BOLD,
    )


def _database_name(db_path: Path | str | None) -> str:
    return Path(db_path).name if db_path else "xingyuan.db"
