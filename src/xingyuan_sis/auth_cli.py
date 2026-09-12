from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from typing import Callable

from .auth import (
    ADMIN_USERNAME,
    Identity,
    authenticate,
    change_password,
    clear_session,
    has_admin,
    initialize_admin,
    read_session,
    reset_student_password,
    write_session,
)
from .database import initialize_database

InputFn = Callable[[str], str]
PasswordFn = Callable[[str], str]


def run(
    db_path: Path | str | None,
    args: argparse.Namespace,
    *,
    input_fn: InputFn | None = None,
    password_fn: PasswordFn | None = None,
) -> int:
    input_fn = input_fn or input
    password_fn = password_fn or getpass.getpass
    initialize_database(db_path)
    action = args.action
    if action is None:
        _print_status(db_path, verbose=True)
        return 0
    if action == "login":
        identity = login(
            db_path,
            username=args.username,
            input_fn=input_fn,
            password_fn=password_fn,
        )
        print(f"✓ 已登录：{identity.username}")
        return 0
    if action == "logout":
        clear_session()
        print("✓ 已退出登录")
        return 0
    if action == "status":
        _print_status(db_path)
        return 0
    if action == "passwd":
        identity = require_identity(db_path, initialize=False)
        current = password_fn("当前密码: ")
        verified = authenticate(db_path, identity.username, current)
        if verified is None:
            raise ValueError("当前密码错误")
        updated = _change_to_new_password(db_path, identity, password_fn=password_fn)
        write_session(updated, db_path)
        print("✓ 密码已修改")
        return 0
    return 2


def login(
    db_path: Path | str | None,
    *,
    username: str | None = None,
    input_fn: InputFn | None = None,
    password_fn: PasswordFn | None = None,
) -> Identity:
    input_fn = input_fn or input
    password_fn = password_fn or getpass.getpass
    initialized = ensure_admin_initialized(password_fn=password_fn)
    if initialized is not None and username in {None, "", ADMIN_USERNAME}:
        write_session(initialized, db_path)
        return initialized

    login_name = username.strip() if username else input_fn("账号: ").strip()
    password = password_fn("密码: ")
    identity = authenticate(db_path, login_name, password)
    if identity is None:
        raise ValueError("账号或密码错误")
    if identity.must_change_password:
        print("首次登录必须修改密码。")
        identity = _change_to_new_password(db_path, identity, password_fn=password_fn)
    write_session(identity, db_path)
    return identity


def ensure_admin_initialized(*, password_fn: PasswordFn | None = None) -> Identity | None:
    password_fn = password_fn or getpass.getpass
    if has_admin():
        return None
    print("未检测到管理员，开始初始化星原 SIS。\n")
    print(f"管理员账号：{ADMIN_USERNAME}")
    while True:
        password = password_fn("设置密码: ")
        confirm = password_fn("确认密码: ")
        if password != confirm:
            print("两次输入的密码不一致。\n")
            continue
        identity = initialize_admin(password)
        print("✓ 管理员初始化完成\n")
        return identity


def require_identity(
    db_path: Path | str | None,
    *,
    initialize: bool = True,
    password_fn: PasswordFn | None = None,
) -> Identity:
    password_fn = password_fn or getpass.getpass
    if initialize:
        initialized = ensure_admin_initialized(password_fn=password_fn)
        if initialized is not None:
            write_session(initialized, db_path)
            return initialized
    identity = read_session(db_path)
    if identity is None:
        raise ValueError("尚未登录，请先执行 xy auth login")
    return identity


def authorize(identity: Identity, args: argparse.Namespace) -> None:
    if identity.is_admin:
        return
    if args.group in {"stu", "student"} and args.action in {"ls", "list", "show"}:
        return
    raise ValueError("学生账户无权执行此操作")


def reset_student_password_command(
    db_path: Path | str | None,
    student_no: str,
) -> int:
    password = reset_student_password(db_path, student_no)
    print(f"✓ 已重置 {student_no} 的初始密码")
    print(f"初始密码：{password}")
    print("首次登录必须修改密码")
    return 0


def _change_to_new_password(
    db_path: Path | str | None,
    identity: Identity,
    *,
    password_fn: PasswordFn,
) -> Identity:
    while True:
        password = password_fn("新密码: ")
        confirm = password_fn("确认新密码: ")
        if password != confirm:
            print("两次输入的密码不一致。\n")
            continue
        return change_password(db_path, identity, password)


def _print_status(db_path: Path | str | None, *, verbose: bool = False) -> None:
    identity = read_session(db_path)
    if identity is None:
        if has_admin():
            print("当前状态：未登录")
        else:
            print("管理员：未初始化")
            print("当前状态：未登录")
        if verbose:
            print("\n  login    登录")
        return

    print(f"当前用户：{identity.username}")
    print(f"身份：{'管理员' if identity.is_admin else '学生'}")
    if identity.student_no is not None:
        print(f"学号：{identity.student_no}")
    if verbose:
        print("\n  status   查看身份")
        print("  passwd   修改密码")
        print("  logout   退出登录")
