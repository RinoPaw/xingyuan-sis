"""Primary navigation and responsive second-level previews for the TUI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from ..auth import Identity
from . import animation, screen, theme
from .board import Board


PRIMARY_LABELS = ("首页", "教务", "个人中心", "退出登录")
NARROW_WIDTH = 38


@dataclass(frozen=True)
class MenuItem:
    label: str
    action: str


_ADMIN_ACADEMIC = (
    MenuItem("学生", "workspace:students"),
    MenuItem("学院", "workspace:departments"),
    MenuItem("专业", "workspace:majors"),
    MenuItem("班级", "workspace:classes"),
    MenuItem("课程", "workspace:courses"),
    MenuItem("成绩", "workspace:grades"),
    MenuItem("数据", "workspace:data"),
)
_STUDENT_ACADEMIC = (
    MenuItem("学生查询", "student-directory"),
)
_PROFILE = (
    MenuItem("个人数据", "profile-data"),
    MenuItem("修改密码", "profile-password"),
)


def secondary_items(identity: Identity, primary: int) -> tuple[MenuItem, ...]:
    if primary == 1:
        return _ADMIN_ACADEMIC if identity.is_admin else _STUDENT_ACADEMIC
    if primary == 2:
        return _PROFILE
    return ()


def secondary_columns(total_width: int, focus: str = "secondary") -> int:
    content_width = _secondary_content_width(total_width, focus)
    if content_width >= 68:
        return 4
    if content_width >= 48:
        return 3
    if content_width >= 30:
        return 2
    return 1


def frame(
    identity: Identity,
    selected: int,
    focus: str,
    secondary_selected: Mapping[int, int],
    stats: Mapping[str, object],
    angle: float,
    *,
    animate: bool = True,
    database: str = "xingyuan.db",
    display_name: str | None = None,
    announcements: Sequence[str] = (),
) -> screen.ScreenFrame:
    terminal = screen._terminal_size()
    width, height = max(1, terminal.columns - 1), max(5, terminal.lines)
    selected = max(0, min(selected, len(PRIMARY_LABELS) - 1))
    items = secondary_items(identity, selected)
    secondary = max(0, min(secondary_selected.get(selected, 0), max(0, len(items) - 1)))
    name = display_name or identity.username

    board = Board(width, height)
    board.put(0, 0, _topbar(width, identity, name, database))
    footer_line, controls = _footer(width, height, selected, focus, bool(items), animate)
    board.put(0, height - 1, footer_line)
    board.regions.extend(controls)

    if width < NARROW_WIDTH:
        _compact_body(
            board, identity, selected, focus, secondary, items, name, angle, announcements
        )
        return animation._starlight(board.frame(), width, angle)

    nav_width = min(21, max(15, width // 5))
    separator_x = nav_width + 1
    right_x = nav_width + 3
    content_width = max(1, width - right_x)

    board.put(0, 1, "导航", screen._TEXT_SECONDARY)
    for index, label in enumerate(PRIMARY_LABELS):
        board.put(
            0,
            2 + index,
            theme.nav_item(label, selected=index == selected),
            action=f"primary:{index}",
            width=nav_width,
        )
    for y in range(1, height - 1):
        board.put(separator_x, y, "│", screen._BORDER_SUBTLE)

    if selected == 0:
        protected = _home_preview(
            board, right_x, content_width, height, identity, name, angle, announcements
        )
        return animation._starlight(board.frame(), width, angle, protected)

    if selected == 1:
        board.put(right_x, 1, "教务", screen._BOLD + screen._TEXT_ACCENT)
        description = "增删改查与校园业务管理" if identity.is_admin else "查询校园学生信息"
        board.put(right_x, 2, description, screen._TEXT_SECONDARY)
        _secondary_grid(
            board, right_x, 4, content_width, items, secondary,
            selected=focus == "secondary",
        )
    elif selected == 2:
        board.put(right_x, 1, "个人中心", screen._BOLD + screen._TEXT_ACCENT)
        board.put(
            right_x, 2,
            f"{name} · {'管理员' if identity.is_admin else identity.student_no}",
            screen._TEXT_SECONDARY,
        )
        _secondary_grid(
            board, right_x, 4, content_width, items, secondary,
            selected=focus == "secondary",
        )
    else:
        board.put(right_x, 1, "退出登录", screen._BOLD + screen._TEXT_ACCENT)
        board.put(right_x, 3, f"当前用户  {name}", screen._TEXT_PRIMARY)
        board.put(right_x, 5, "Enter / Space / → 退出当前账户", screen._TEXT_SECONDARY)

    return animation._starlight(board.frame(), width, angle)


def _topbar(
    width: int,
    identity: Identity,
    display_name: str,
    database: str,
) -> str:
    left = "✦ 星原 SIS"
    role = "管理员" if identity.is_admin else "学生"
    right = f"{display_name} · {role}   LOCAL / {database}"
    if screen._display_width(left) + screen._display_width(right) + 2 <= width:
        gap = width - screen._display_width(left) - screen._display_width(right)
        plain = left + " " * gap + right
    else:
        plain = screen._pad_cells(screen._clip_cells(left, width), width)
    return screen._ansi(
        screen._pad_cells(screen._clip_cells(plain, width), width),
        screen._SURFACE_TOPBAR + screen._TEXT_ACCENT + screen._BOLD,
    )


def _footer(
    width: int,
    height: int,
    selected: int,
    focus: str,
    has_secondary: bool,
    animate: bool,
) -> tuple[str, list[screen.HitRegion]]:
    if focus == "secondary":
        buttons = (
            ("方向键 选择", "方向", "down"),
            ("Enter 打开", "↵", "select"),
            ("Esc 返回", "Esc", "back"),
        )
    else:
        buttons: tuple[tuple[str, str, str], ...] = (
            ("↑↓ 移动", "↑↓", "down"),
        )
        if has_secondary:
            buttons += (("Enter / → 进入", "↵/→", "select"),)
        elif selected == 3:
            buttons += (("Enter 退出登录", "↵退出", "select"),)
        if selected == 0:
            motion = "暂停动画" if animate else "播放动画"
            buttons += ((f"p {motion}", "p", "pause"),)
        buttons += (("Esc 退出", "Esc", "back"),)
    return theme.footer(width, buttons, height)


def _compact_body(
    board: Board,
    identity: Identity,
    selected: int,
    focus: str,
    secondary: int,
    items: Sequence[MenuItem],
    display_name: str,
    angle: float,
    announcements: Sequence[str],
) -> None:
    width, height = board.width, board.height
    if focus == "secondary" and items:
        board.put(0, 1, PRIMARY_LABELS[selected], screen._BOLD + screen._TEXT_ACCENT)
        for index, item in enumerate(items):
            y = 3 + index
            if y >= height - 1:
                break
            board.put(
                0, y,
                theme.nav_item(item.label, selected=index == secondary),
                action=f"secondary:{index}",
                width=width,
            )
        return

    board.put(0, 1, "导航", screen._TEXT_SECONDARY)
    for index, label in enumerate(PRIMARY_LABELS):
        suffix = "  ›" if index == selected and secondary_items(identity, index) else ""
        board.put(
            0, 2 + index,
            theme.nav_item(label + suffix, selected=index == selected),
            action=f"primary:{index}",
            width=width,
        )

    y = 7
    if y >= height - 1:
        return
    if selected == 0:
        board.put(0, y, "星原学生信息系统", screen._BOLD + screen._TEXT_ACCENT)
        if y + 2 < height - 1:
            board.put(0, y + 2, "公告", screen._BOLD + screen._TEXT_PRIMARY)
        if y + 3 < height - 1:
            board.put(0, y + 3, announcements[0] if announcements else "暂无公告", screen._TEXT_SECONDARY)
    elif selected in {1, 2}:
        board.put(0, y, PRIMARY_LABELS[selected], screen._BOLD + screen._TEXT_ACCENT)
        if y + 2 < height - 1:
            board.put(0, y + 2, "Enter / Space / → 进入", screen._TEXT_SECONDARY)
    else:
        board.put(0, y, f"{display_name} · {'管理员' if identity.is_admin else '学生'}",
                  screen._TEXT_SECONDARY)


def _home_preview(
    board: Board,
    x: int,
    width: int,
    height: int,
    identity: Identity,
    display_name: str,
    angle: float,
    announcements: Sequence[str],
) -> set[tuple[int, int]]:
    board.put(x, 1, "星原学生信息系统", screen._BOLD + screen._TEXT_ACCENT)
    identity_text = (
        f"{display_name} · 管理员"
        if identity.is_admin
        else f"{display_name} · {identity.student_no}"
    )
    board.put(x, 2, identity_text, screen._TEXT_SECONDARY)

    announcement_lines = list(announcements[:3]) or ["暂无公告"]
    announcement_top = max(7, height - len(announcement_lines) - 3)
    orbit_top = 4
    orbit_height = max(1, announcement_top - orbit_top - 1)
    protected: set[tuple[int, int]] = set()
    if width >= 12 and orbit_height > 0:
        for row, line in enumerate(animation._orbit(width, orbit_height, angle, 0)):
            board.put(x, orbit_top + row, line, width=width)
        protected.update(
            (orbit_top + row, x + col)
            for row, col in animation._orbit_exclusion_mask(width, orbit_height, angle)
        )

    if announcement_top < height - 1:
        board.put(x, announcement_top, "公告", screen._BOLD + screen._TEXT_PRIMARY)
    for offset, notice in enumerate(announcement_lines, start=1):
        y = announcement_top + offset
        if y < height - 1:
            board.put(x, y, f"· {notice}", screen._TEXT_SECONDARY, width=width)
    return protected


def _secondary_grid(
    board: Board,
    x: int,
    y: int,
    width: int,
    items: Sequence[MenuItem],
    secondary: int,
    *,
    selected: bool,
) -> None:
    columns = secondary_columns(board.width, "secondary")
    columns = min(columns, max(1, width // 16))
    cell_width = max(1, width // columns)
    for index, item in enumerate(items):
        row, col = divmod(index, columns)
        item_y = y + row * 2
        if item_y >= board.height - 1:
            break
        board.put(
            x + col * cell_width,
            item_y,
            theme.button(item.label, selected=selected and index == secondary,
                         width=max(1, cell_width - 1)),
            action=f"secondary:{index}",
            width=max(1, cell_width - 1),
        )


def _secondary_content_width(total_width: int, focus: str) -> int:
    if total_width < NARROW_WIDTH and focus == "secondary":
        return total_width
    if total_width < NARROW_WIDTH:
        return 0
    nav_width = min(21, max(15, total_width // 5))
    return max(1, total_width - (nav_width + 3))
