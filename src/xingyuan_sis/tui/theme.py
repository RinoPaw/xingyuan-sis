"""Shared layout and styling for the interactive terminal screen."""
from __future__ import annotations

from typing import Sequence

from . import animation, screen
from .board import Board


_BUTTON = screen._SURFACE_INTERACTIVE + screen._TEXT_PRIMARY
_BUTTON_CURRENT = screen._SURFACE_SELECTED + screen._TEXT_ACCENT
_BAR_SURFACE = screen._SURFACE_FOOTER + screen._TEXT_PRIMARY
_TOPBAR = screen._SURFACE_TOPBAR + screen._TEXT_ACCENT + screen._BOLD
_SECTION_HEADING = screen._TEXT_PRIMARY + screen._BOLD


def bar_space(count: int) -> str:
    return screen._ansi(" " * max(0, count), _BAR_SURFACE)


def button(
    label: str,
    *,
    selected: bool = False,
    current: bool = False,
    width: int | None = None,
) -> str:
    """Render an action button with separate focus and current-location states."""
    marker = "›" if selected else "·" if current else " "
    shown = f"[{marker}{label} ]"
    if width is not None:
        shown = screen._pad_cells(screen._clip_cells(shown, width), width)
    if selected:
        style = screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
    elif current:
        style = _BUTTON_CURRENT
    else:
        style = _BUTTON
    return screen._ansi(shown, style)


def nav_item(
    label: str,
    *,
    selected: bool = False,
    current: bool = False,
    width: int | None = None,
) -> str:
    """Render navigation with strong focus and weak current-location states."""
    marker = "▌" if selected else "▏" if current else " "
    shown = f"{marker} {label}"
    if width is not None:
        shown = screen._pad_cells(screen._clip_cells(shown, width), width)
    if selected:
        style = screen._BOLD + screen._TEXT_ACCENT
    elif current:
        style = screen._TEXT_ACCENT
    else:
        style = screen._TEXT_PRIMARY
    return screen._ansi(shown, style)


def overview_item(label: str, value: object) -> str:
    return (
        screen._ansi(label, screen._TEXT_SECONDARY)
        + "  "
        + screen._ansi(str(value), screen._BOLD + screen._TEXT_ACCENT)
    )


def topbar(width: int, *, database: str | None = None, context: str = "") -> str:
    """One application identity; account and storage are secondary context."""
    left = screen._clip_cells("✦ 星原 SIS", width)
    available = width - screen._display_width(left)
    database_text = f"LOCAL / {database}" if database else ""
    right = "   ".join(part for part in (context, database_text) if part)
    if screen._display_width(right) + 2 > available:
        right = database_text if screen._display_width(database_text) + 2 <= available else ""
    gap = max(0, available - screen._display_width(right))
    return (screen._ansi(left, _TOPBAR)
            + screen._ansi(" " * gap + right, screen._SURFACE_TOPBAR + screen._TEXT_SECONDARY))


def view_labels(width: int, choices: Sequence[tuple[str, int | None, str, bool]]) -> list[str]:
    """Fit all views before sacrificing their descriptive labels."""
    full = [f"{i + 1} {label}" + (f" · {count}" if count is not None else "")
            for i, (label, count, _, _) in enumerate(choices)]
    short = [f"{i + 1} · {count}" if count is not None else f"{i + 1} {label}"
             for i, (label, count, _, _) in enumerate(choices)]
    for labels in (full, short):
        if sum(screen._display_width(label) + 5 for label in labels) <= width:
            return labels
    return [str(i + 1) for i in range(len(choices))]


def notice(message: str, *, error: bool = False) -> str:
    style = screen._TEXT_DANGER if error else screen._TEXT_SECONDARY
    return screen._ansi(("! " if error else "· ") + message, style) if message else ""


def footer(
    width: int,
    buttons: Sequence[tuple[str, str, str]],
    row: int,
) -> tuple[str, list[screen.HitRegion]]:
    def labels(use_short: bool) -> list[tuple[str, str]]:
        return [
            (f"[ {short if use_short else long} ]", action)
            for long, short, action in buttons
        ]

    chosen = labels(False)
    minimum = sum(screen._display_width(text) for text, _ in chosen) + max(0, len(chosen) - 1)
    if minimum > width:
        chosen = labels(True)

    while chosen and (
        sum(screen._display_width(text) for text, _ in chosen) + max(0, len(chosen) - 1) > width
    ):
        if len(chosen) > 2:
            chosen.pop(-2)
        else:
            chosen.pop(0)

    if not chosen:
        return bar_space(width), []

    button_width = sum(screen._display_width(text) for text, _ in chosen)
    free = max(0, width - button_width)
    slots = len(chosen) + 1
    base_gap, extra = divmod(free, slots)
    gaps = [base_gap + (1 if index < extra else 0) for index in range(slots)]

    parts: list[str] = [bar_space(gaps[0])]
    regions: list[screen.HitRegion] = []
    cell = gaps[0]
    for index, (shown, action) in enumerate(chosen):
        regions.append(screen.HitRegion(cell + 1, row, screen._display_width(shown), action))
        parts.append(screen._ansi(shown, _BUTTON))
        cell += screen._display_width(shown)
        parts.append(bar_space(gaps[index + 1]))
        cell += gaps[index + 1]

    return "".join(parts), regions


def home_frame(
    labels: Sequence[str],
    selected: int,
    stats: dict[str, object],
    angle: float,
    *,
    animate: bool = True,
    database: str = "xingyuan.db",
) -> screen.ScreenFrame:
    terminal = screen._terminal_size()
    width, height = max(1, terminal.columns - 1), max(3, terminal.lines)
    body_height = max(0, height - 2)
    title, description, _ = _MODULES[selected]

    board = Board(width, height)
    board.put(0, 0, topbar(width, database=database))
    footer_line, controls = home_footer(width, height, animate)
    board.put(0, height - 1, footer_line)
    board.regions.extend(controls)
    protected_cells: set[tuple[int, int]] = set()

    # Compact layout: title and orbit occupy the body; navigation is positioned
    # directly at the bottom of that body instead of being padded into columns.
    if width < 38:
        columns = 2 if width >= 28 else 1
        nav_rows = (len(labels) + columns - 1) // columns
        graph_height = max(0, body_height - nav_rows - 1)
        board.put(0, 1, title, screen._BOLD + screen._TEXT_ACCENT)

        orbit_top = 2
        if graph_height:
            for row, line in enumerate(animation._orbit(width, graph_height, angle, selected)):
                board.put(0, orbit_top + row, line, width=width)
            protected_cells.update(
                (orbit_top + row, col)
                for row, col in animation._orbit_exclusion_mask(width, graph_height, angle)
            )

        cell_width = max(1, width // columns)
        nav_top = orbit_top + graph_height
        for row in range(nav_rows):
            for col in range(columns):
                index = row * columns + col
                if index >= len(labels):
                    continue
                number = "0" if index == len(labels) - 1 else str(index + 1)
                board.put(
                    col * cell_width,
                    nav_top + row,
                    nav_item(f"{number} {labels[index]}", selected=index == selected),
                    action=f"item:{index}",
                    width=cell_width,
                )

        return animation._starlight(board.frame(), width, angle, protected_cells)

    nav_width = min(22, max(14, width // 5))
    separator_x = nav_width + 1
    right_x = nav_width + 3
    graph_width = max(1, width - right_x)

    board.put(0, 1, "首页", screen._TEXT_SECONDARY)
    for index, label in enumerate(labels):
        number = "0" if index == len(labels) - 1 else str(index + 1)
        board.put(
            0,
            2 + index,
            nav_item(f"{number} {label}", selected=index == selected),
            action=f"item:{index}",
            width=nav_width,
        )

    if body_height > 8:
        board.put(0, 9, "校园概览", _SECTION_HEADING)
    for offset, (label, value) in enumerate((
        ("学生", stats.get("students", 0)),
        ("班级", stats.get("classes", 0)),
        ("课程", stats.get("courses", 0)),
        ("选课", stats.get("enrollments", 0)),
    )):
        y = 10 + offset
        if y < height - 1:
            board.put(0, y, overview_item(label, value), width=nav_width)

    for y in range(1, height - 1):
        board.put(separator_x, y, "│", screen._BORDER_SUBTLE)

    board.put(right_x, 1, f"{selected + 1:02d} / {title}", screen._BOLD + screen._TEXT_ACCENT)
    if graph_width >= 28 and body_height >= 8:
        board.put(right_x, 2, description, screen._TEXT_SECONDARY)
        orbit_top = 4
    else:
        orbit_top = 2

    graph_height = max(1, height - 1 - orbit_top)
    for row, line in enumerate(animation._orbit(graph_width, graph_height, angle, selected)):
        board.put(right_x, orbit_top + row, line, width=graph_width)
    protected_cells.update(
        (orbit_top + row, right_x + col)
        for row, col in animation._orbit_exclusion_mask(graph_width, graph_height, angle)
    )

    return animation._starlight(board.frame(), width, angle, protected_cells)


_MODULES = (
    ("学生档案", "查询每位学生的档案与成长记录。", "查询 / 搜索 / 新建 / 编辑"),
    ("教务结构", "从学院到班级，管理校园的组织。", "学院 / 专业 / 班级"),
    ("课程目录", "课程安排、学分与课时一目了然。", "课程详情 / 学分 / 课时"),
    ("选课与成绩", "记录选课，跟进每一次学习进展。", "选课 / 录入成绩 / 搜索"),
    ("数据工作台", "查看全校概况，导入或带走记录。", "统计 / CSV / 演示数据"),
    ("结束本次工作", "已完成的操作已保存。", "Enter 退出 / 上下键继续浏览"),
)


def home_footer(width: int, height: int, animate: bool) -> tuple[str, list[screen.HitRegion]]:
    motion = "暂停动画" if animate else "播放动画"
    return footer(width, (("↑↓ 移动", "↑↓", "down"),
                           ("Enter 打开", "↵", "select"),
                           (f"p {motion}", "p", "pause"),
                           ("Esc 退出", "Esc退", "back")), height)
