"""Shared layout and styling for the interactive terminal screen."""
from __future__ import annotations

from typing import Sequence

from . import screen, animation


_BUTTON = screen._SURFACE_INTERACTIVE + screen._TEXT_PRIMARY
_BAR_SURFACE = screen._SURFACE_FOOTER + screen._TEXT_PRIMARY
_TOPBAR = screen._SURFACE_TOPBAR + screen._TEXT_ACCENT + screen._BOLD
_SECTION_HEADING = screen._TEXT_PRIMARY + screen._BOLD


def bar_space(count: int) -> str:
    return screen._ansi(" " * max(0, count), _BAR_SURFACE)


def button(label: str, *, selected: bool = False, width: int | None = None) -> str:
    shown = f"[ {label} ]"
    if width is not None:
        shown = screen._pad_cells(screen._clip_cells(shown, width), width)
    style = screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED if selected else _BUTTON
    return screen._ansi(shown, style)


def nav_item(label: str, *, selected: bool = False, width: int | None = None) -> str:
    """Render a lightweight home navigation row.

    Only the active item gets a marker and accent; inactive rows stay plain so
    the sidebar reads as navigation rather than a wall of buttons.
    """
    shown = f"{'▌' if selected else ' '} {label}"
    if width is not None:
        shown = screen._pad_cells(screen._clip_cells(shown, width), width)
    style = screen._BOLD + screen._TEXT_ACCENT if selected else screen._TEXT_PRIMARY
    return screen._ansi(shown, style)


def overview_row(
    left_label: str,
    left_value: object,
    right_label: str,
    right_value: object,
) -> str:
    """Render one compact two-column campus overview row."""
    return (
        screen._ansi(left_label, screen._TEXT_SECONDARY)
        + " "
        + screen._ansi(str(left_value), screen._BOLD + screen._TEXT_ACCENT)
        + "  "
        + screen._ansi(right_label, screen._TEXT_SECONDARY)
        + " "
        + screen._ansi(str(right_value), screen._BOLD + screen._TEXT_ACCENT)
    )


def topbar(width: int, *, database: str | None = None) -> str:
    left = "✦ 星原 / 教务台"
    right = f"LOCAL / {database}" if database else ""
    if right and screen._display_width(left) + screen._display_width(right) + 2 <= width:
        gap = width - screen._display_width(left) - screen._display_width(right)
        plain = left + " " * gap + right
    else:
        plain = screen._pad_cells(screen._clip_cells(left, width), width)
    return screen._ansi(screen._pad_cells(screen._clip_cells(plain, width), width), _TOPBAR)


def footer(
    width: int,
    buttons: Sequence[tuple[str, str, str]],
    row: int,
) -> tuple[str, list[screen.HitRegion]]:
    def labels(use_short: bool) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for long, short, action in buttons:
            # Back/cancel has one universal visible hint. Legacy q/0 aliases
            # can remain functional without competing for UI space.
            label = "Esc" if action in {"back", "cancel"} else (short if use_short else long)
            result.append((f"[ {label} ]", action))
        return result

    chosen = labels(False)
    minimum = sum(screen._display_width(text) for text, _ in chosen) + max(0, len(chosen) - 1)
    if minimum > width:
        chosen = labels(True)

    # Keep the escape control when an unusually narrow terminal cannot fit
    # every compact button. Drop optional middle controls first.
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
    title, description, _ = _MODULES[selected]

    top = [topbar(width, database=database)]
    body_height = max(0, height - 2)
    footer_line, controls = home_footer(width, height, animate)
    regions: list[screen.HitRegion] = []
    protected_cells: set[tuple[int, int]] = set()

    # The layout mode depends only on width. Soft-keyboard height changes
    # therefore cannot make the whole home screen oscillate between modes.
    if width < 38:
        columns = 2 if width >= 28 else 1
        nav_rows = (len(labels) + columns - 1) // columns
        graph_height = max(0, body_height - nav_rows - 1)
        body = [screen._ansi(title, screen._BOLD + screen._TEXT_ACCENT)]
        if graph_height:
            body.extend(animation._orbit(width, graph_height, angle, selected))
            orbit_row_offset = len(top) + 1
            protected_cells.update(
                (orbit_row_offset + row, col)
                for row, col in animation._orbit_exclusion_mask(width, graph_height, angle)
            )
        cell_width = max(1, width // columns)
        for row in range(nav_rows):
            parts: list[str] = []
            screen_row = len(top) + len(body) + 1
            for col in range(columns):
                index = row * columns + col
                if index >= len(labels):
                    parts.append(" " * cell_width)
                    continue
                number = "0" if index == len(labels) - 1 else str(index + 1)
                parts.append(
                    nav_item(f"{number} {labels[index]}", selected=index == selected, width=cell_width)
                )
                regions.append(
                    screen.HitRegion(col * cell_width + 1, screen_row, cell_width, f"item:{index}")
                )
            body.append("".join(parts))
        body = (body + [""] * body_height)[:body_height]
        frame = screen.ScreenFrame(
            [screen._clip_cells(line, width) for line in [*top, *body, footer_line]],
            regions + controls,
        )
        return animation._starlight(frame, width, angle, protected_cells)

    nav_width = min(22, max(14, width // 5))
    graph_width = max(1, width - nav_width - 3)
    left: list[str] = [screen._ansi("首页", screen._TEXT_SECONDARY)]

    # Keep navigation density fixed at every height; the earlier blank rows
    # made Termux visibly jump as the IME changed the reported line count.
    for index, label in enumerate(labels):
        number = "0" if index == len(labels) - 1 else str(index + 1)
        line = nav_item(f"{number} {label}", selected=index == selected, width=nav_width)
        regions.append(screen.HitRegion(1, len(top) + len(left) + 1, nav_width, f"item:{index}"))
        left.append(line)

    for line in (
        "",
        screen._ansi("校园概览", _SECTION_HEADING),
        overview_row("学生", stats.get("students", 0), "班级", stats.get("classes", 0)),
        overview_row("课程", stats.get("courses", 0), "选课", stats.get("enrollments", 0)),
    ):
        if len(left) < body_height:
            left.append(line)

    right = [screen._ansi(f"{selected + 1:02d} / {title}", screen._BOLD + screen._TEXT_ACCENT)]
    if graph_width >= 28 and body_height >= 8:
        right.extend([screen._ansi(description, screen._TEXT_SECONDARY), ""])
    orbit_row_offset = len(top) + len(right)
    graph_height = max(1, body_height - len(right))
    right.extend(animation._orbit(graph_width, graph_height, angle, selected))
    orbit_col_offset = nav_width + 3
    protected_cells.update(
        (orbit_row_offset + row, orbit_col_offset + col)
        for row, col in animation._orbit_exclusion_mask(graph_width, graph_height, angle)
    )

    body: list[str] = []
    for row in range(body_height):
        left_line = left[row] if row < len(left) else ""
        right_line = right[row] if row < len(right) else ""
        body.append(
            screen._pad_cells(screen._clip_cells(left_line, nav_width), nav_width)
            + screen._ansi(" │ ", screen._BORDER_SUBTLE)
            + screen._clip_cells(right_line, graph_width)
        )

    frame = screen.ScreenFrame(
        [screen._clip_cells(line, width) for line in [*top, *body, footer_line]],
        regions + controls,
    )
    return animation._starlight(frame, width, angle, protected_cells)


_MODULES = (
    ("学生档案", "查询每位学生的档案与成长记录。", "查询 / 搜索 / 新建 / 编辑"),
    ("教务结构", "从学院到班级，管理校园的组织。", "学院 / 专业 / 班级"),
    ("课程目录", "课程安排、学分与课时一目了然。", "课程详情 / 学分 / 课时"),
    ("选课与成绩", "记录选课，跟进每一次学习进展。", "选课 / 录入成绩 / 搜索"),
    ("数据工作台", "查看全校概况，导入或带走记录。", "统计 / CSV / 演示数据"),
    ("结束本次工作", "已完成的操作已保存。", "Enter 退出 / 上下键继续浏览"),
)


def home_footer(width: int, height: int, animate: bool) -> tuple[str, list[screen.HitRegion]]:
    motion = "暂停" if animate else "播放"
    return footer(width, (("↑↓/滚轮 移动", "↑↓", "down"),
                           ("Enter/点击 打开", "↵", "select"),
                           (f"p {motion}", "p", "pause"),
                           ("Esc", "Esc", "back")), height)
