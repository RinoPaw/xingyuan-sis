"""Top-level TUI navigation and workspace dispatch."""
from __future__ import annotations

from pathlib import Path
import sys
import time
from typing import Callable, Sequence

from ..auth import Identity, clear_session, read_session
from . import auth_view, keys, portal, screen


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


# Kept as the renderer exercised by the lower-level layout regression tests.
# The logged-in application uses portal.frame below.
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
    preferences: dict[str, object] | None = None,
) -> int | str | None:
    if tuple(labels) == portal.PRIMARY_LABELS:
        return _portal_home(db_path, selected=selected, preferences=preferences)

    from ..service import XingyuanService

    stats = dict(XingyuanService(db_path).stats())
    preferences = preferences if preferences is not None else {"animate": True}
    saved_angle = preferences.get("angle")
    if isinstance(saved_angle, (int, float)):
        angle = float(saved_angle)
    else:
        angle = time.monotonic() * 0.85
        preferences["angle"] = angle
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
    selected: int, preferences: dict[str, object], angle: float, previous_lines: list[str],
) -> int | None:
    last_tick = time.monotonic()
    while True:
        animate = bool(preferences.get("animate", True))
        now = time.monotonic()
        if animate:
            angle += max(0.0, now - last_tick) * 0.85
        last_tick = now
        preferences["angle"] = angle

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


def _portal_home(
    db_path: Path | str | None,
    *,
    selected: int,
    preferences: dict[str, object] | None,
) -> str | None:
    from ..service import XingyuanService

    preferences = preferences if preferences is not None else {"animate": True}
    identity = preferences.get("identity")
    if not isinstance(identity, Identity):
        identity = read_session(db_path)
    if identity is None:
        identity = auth_view.login(db_path)
    if identity is None:
        return None
    preferences["identity"] = identity

    selected = int(preferences.get("portal_selected", selected))
    selected = max(0, min(selected, len(portal.PRIMARY_LABELS) - 1))
    focus = str(preferences.get("portal_focus", "primary"))
    if focus not in {"primary", "secondary"}:
        focus = "primary"
    secondary_selected = preferences.setdefault("portal_secondary", {})
    if not isinstance(secondary_selected, dict):
        secondary_selected = {}
        preferences["portal_secondary"] = secondary_selected

    service = XingyuanService(db_path)
    stats = dict(service.stats())
    display_name = identity.username
    if identity.is_student and identity.student_no:
        row = service.student_by_no(identity.student_no)
        if row is not None:
            display_name = str(row["name"])

    saved_angle = preferences.get("angle")
    angle = float(saved_angle) if isinstance(saved_angle, (int, float)) else time.monotonic() * 0.85
    previous_lines: list[str] = []
    screen._clear()

    with keys._mouse_tracking():
        last_tick = time.monotonic()
        while True:
            animate = bool(preferences.get("animate", True))
            now = time.monotonic()
            if animate:
                angle += max(0.0, now - last_tick) * 0.85
            last_tick = now
            preferences["angle"] = angle
            preferences["portal_selected"] = selected
            preferences["portal_focus"] = focus

            items = portal.secondary_items(identity, selected)
            secondary = int(secondary_selected.get(selected, 0))
            secondary = max(0, min(secondary, max(0, len(items) - 1)))
            secondary_selected[selected] = secondary

            frame = portal.frame(
                identity,
                selected,
                focus,
                secondary_selected,
                stats,
                angle,
                animate=animate,
                database=Path(db_path).name if db_path else "xingyuan.db",
                display_name=display_name,
            )
            if frame.lines != previous_lines:
                screen._paint(frame.lines, previous_lines)
                previous_lines = frame.lines

            key = keys._read_key(0.08 if animate and selected == 0 else 0.15)
            if isinstance(key, keys.MouseScroll):
                key = key.direction
            if isinstance(key, screen.MouseClick):
                action = screen._hit_action(key, frame.regions)
                if action and action.startswith("primary:"):
                    target = int(action.split(":")[1])
                    if target == selected:
                        key = "select"
                    else:
                        selected = target
                        focus = "primary"
                        continue
                elif action and action.startswith("secondary:"):
                    target = int(action.split(":")[1])
                    if target < len(items):
                        secondary_selected[selected] = target
                        return items[target].action
                elif action:
                    key = action

            if focus == "primary":
                if key == "up":
                    selected = (selected - 1) % len(portal.PRIMARY_LABELS)
                elif key == "down":
                    selected = (selected + 1) % len(portal.PRIMARY_LABELS)
                elif key == "home":
                    selected = 0
                elif key == "end":
                    selected = len(portal.PRIMARY_LABELS) - 1
                elif key in tuple("1234"):
                    selected = int(key) - 1
                elif key == "pause" and selected == 0:
                    preferences["animate"] = not animate
                elif key == "select":
                    if selected == 3:
                        return "logout"
                    if items:
                        focus = "secondary"
                elif key == "right" and items:
                    focus = "secondary"
                elif key == "back":
                    return None
                continue

            terminal = screen._terminal_size()
            columns = portal.secondary_columns(max(1, terminal.columns - 1), focus, height=terminal.lines)
            if key == "up":
                secondary = max(0, secondary - columns)
            elif key == "down":
                secondary = min(len(items) - 1, secondary + columns)
            elif key == "left":
                if secondary % columns == 0:
                    focus = "primary"
                else:
                    secondary -= 1
            elif key == "right":
                next_index = secondary + 1
                if next_index < len(items) and next_index // columns == secondary // columns:
                    secondary = next_index
            elif key == "home":
                secondary = 0
            elif key == "end":
                secondary = max(0, len(items) - 1)
            elif key == "back":
                focus = "primary"
            elif key == "select" and items:
                secondary_selected[selected] = secondary
                return items[secondary].action
            secondary_selected[selected] = secondary


def _workspace(db_path: Path | str | None, key: str) -> None:
    from .workspace import run as run_workspace
    run_workspace(db_path, key)


def _show_student_directory(db_path: Path | str | None) -> None:
    from ..service import XingyuanService
    from .viewer import show

    rows = XingyuanService(db_path).list_students()
    text = "\n".join(
        f"{row['student_no']}  {row['name']}  {row['class_name'] or '未分班'}"
        for row in rows
    )
    show(text, "教务 / 学生查询")


def _show_profile(db_path: Path | str | None, identity: Identity) -> None:
    from ..service import XingyuanService
    from .viewer import show

    if identity.is_admin:
        text = "账号        Administrator\n身份        系统管理员"
    else:
        row = XingyuanService(db_path).student_by_no(identity.student_no or "")
        if row is None:
            raise ValueError("当前学生档案不存在")
        fields = (
            ("学号", row["student_no"]),
            ("姓名", row["name"]),
            ("学院", row["department_name"]),
            ("专业", row["major_name"]),
            ("班级", row["class_name"]),
            ("族系", row["family"]),
            ("支系", row["branch"]),
            ("状态", row["status"]),
            ("联系方式", row["contact"]),
            ("宿舍", row["dormitory"]),
        )
        text = "\n".join(f"{label:<6}  {value if value is not None else '—'}" for label, value in fields)
    show(text, "个人中心 / 个人数据")


def _change_password_screen(
    db_path: Path | str | None,
    identity: Identity,
) -> Identity:
    return auth_view.change_password(db_path, identity) or identity


def _execute_portal_action(
    action: str,
    db_path: Path | str | None,
    identity: Identity,
) -> Identity:
    if action.startswith("workspace:"):
        if not identity.is_admin:
            raise ValueError("学生账户无权执行管理操作")
        _workspace(db_path, action.removeprefix("workspace:"))
    elif action == "student-directory":
        _show_student_directory(db_path)
    elif action == "profile-data":
        _show_profile(db_path, identity)
    elif action == "profile-password":
        return _change_password_screen(db_path, identity)
    return identity


def run(db_path: Path | str | None = None) -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise RuntimeError("当前环境不是交互终端；请使用 xy <command>")

    legacy_actions: tuple[Callable[[], None], ...] = (
        lambda: _students(db_path),
        lambda: _academics(db_path),
        lambda: _courses(db_path),
        lambda: _grades(db_path),
        lambda: _data(db_path),
    )

    selected = 0
    preferences: dict[str, object] = {"animate": True}
    with screen._terminal_session():
        try:
            while True:
                choice = _home(
                    db_path,
                    portal.PRIMARY_LABELS,
                    selected=selected,
                    preferences=preferences,
                )
                if choice is None:
                    return

                if isinstance(choice, int):
                    if choice >= len(legacy_actions):
                        return
                    selected = choice
                    legacy_actions[choice]()
                    continue

                selected = int(preferences.get("portal_selected", selected))
                identity = preferences.get("identity")
                if not isinstance(identity, Identity):
                    continue

                if choice == "logout":
                    clear_session()
                    preferences.pop("identity", None)
                    preferences["portal_selected"] = 0
                    preferences["portal_focus"] = "primary"
                    selected = 0
                    screen._clear()
                    continue

                try:
                    updated = _execute_portal_action(choice, db_path, identity)
                    preferences["identity"] = updated
                except screen.NavigateTo as navigation:
                    if not navigation.path:
                        preferences["portal_selected"] = 0
                    elif navigation.path.startswith("教务"):
                        preferences["portal_selected"] = 1
                    preferences["portal_focus"] = "primary"
        except (KeyboardInterrupt, EOFError):
            pass
