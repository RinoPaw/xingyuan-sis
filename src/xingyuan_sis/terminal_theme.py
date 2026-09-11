from __future__ import annotations

from types import ModuleType
from typing import Sequence


_BUTTON = "\x1b[48;5;237m\x1b[38;5;252m"


def install(menu: ModuleType) -> None:
    """Install the responsive visual theme onto the stdlib terminal menu.

    The interaction engine stays in ``menu.py``.  This module only owns the
    visual treatment so landscape layout and clickable affordances can evolve
    without making the input loop even larger.
    """

    def button(label: str, *, selected: bool = False, width: int | None = None) -> str:
        shown = f"[ {label} ]"
        if width is not None:
            shown = menu._pad_cells(menu._clip_cells(shown, width), width)
        return menu._ansi(shown, menu._SELECTED if selected else _BUTTON)

    def footer(
        width: int,
        buttons: Sequence[tuple[str, str, str]],
        row: int,
    ) -> tuple[str, list[object]]:
        def render(use_short: bool) -> tuple[str, list[object]]:
            text = ""
            regions: list[object] = []
            for long, short, action in buttons:
                label = short if use_short else long
                shown = f"[ {label} ]"
                separator = " " if text else ""
                if menu._display_width(text + separator + shown) > width:
                    continue
                if separator:
                    text += separator
                x = menu._display_width(text) + 1
                regions.append(menu.HitRegion(x, row, menu._display_width(shown), action))
                text += menu._ansi(shown, _BUTTON)
            return text, regions

        long_text, long_regions = render(False)
        expected_long = " ".join(f"[ {long} ]" for long, _, _ in buttons)
        if menu._display_width(expected_long) <= width:
            text, regions = long_text, long_regions
        else:
            text, regions = render(True)

        # Never wrap a footer.  If the compact labels still do not fit,
        # render() simply keeps the highest-priority controls from the left.
        return menu._pad_cells(menu._clip_cells(text, width), width), regions

    def selection_frame(
        title: str,
        items: Sequence[str],
        selected: int,
        back_label: str,
    ):
        terminal = menu._terminal_size()
        width, height = max(1, terminal.columns - 1), max(3, terminal.lines)
        capacity = max(1, height - 5)
        first = min(max(0, selected - capacity + 1), max(0, len(items) - capacity))
        lines = [
            menu._ansi("✦ 星原 / 教务台", menu._BOLD + menu._ACCENT),
            menu._ansi(f"首页 / {title}", menu._DIM),
            menu._ansi("─" * width, menu._DIM),
        ]
        regions: list[object] = []
        panel_width = min(width, 36 if width >= 72 else width)

        for index in range(first, min(len(items), first + capacity)):
            label = f"{index + 1}  {items[index]}"
            line = button(label, selected=index == selected, width=panel_width)
            regions.append(menu.HitRegion(1, len(lines) + 1, panel_width, f"item:{index}"))
            lines.append(line)

        while len(lines) < height:
            lines.append("")

        if width >= 72 and height >= 10:
            details = [
                items[selected],
                "",
                "点击按钮或按 Enter 打开。",
                "方向键 / 滚轮切换选项。",
                "q 返回上一级。",
            ]
            for offset, detail in enumerate(details, start=3):
                if offset < height - 1:
                    lines[offset] = (
                        menu._pad_cells(lines[offset], panel_width + 3)
                        + menu._ansi(detail, menu._ACCENT if offset == 3 else menu._DIM)
                    )

        footer_line, controls = footer(
            width,
            (
                ("↑↓/滚轮 移动", "↑↓", "down"),
                ("Enter/点击 打开", "打开", "select"),
                (f"q {back_label}", f"q{back_label}", "back"),
            ),
            height,
        )
        lines[-1] = footer_line
        return menu.ScreenFrame(
            [menu._clip_cells(line, width) for line in lines],
            regions + controls,
        )

    def home_frame(
        labels: Sequence[str],
        selected: int,
        stats: dict[str, object],
        angle: float,
        *,
        animate: bool = True,
        database: str = "xingyuan.db",
    ):
        terminal = menu._terminal_size()
        width, height = max(1, terminal.columns - 1), max(3, terminal.lines)
        title, description, _ = menu._MODULES[selected]

        header = menu._ansi("✦ 星原 / 教务台", menu._BOLD + menu._ACCENT)
        database_label = menu._ansi(f"LOCAL / {database}", menu._DIM)
        if width >= 64:
            header = (
                menu._pad_cells(header, max(24, width - menu._display_width(database_label)))
                + database_label
            )

        top = [header, menu._ansi("─" * width, menu._DIM)]
        body_height = max(0, height - len(top) - 1)
        footer_line, controls = menu._home_footer(width, height, animate)
        regions: list[object] = []

        # Compact/portrait mode: keep the globe above a dense two-column grid.
        if width < 50 or height < 10:
            columns = 2 if width >= 28 else 1
            nav_rows = (len(labels) + columns - 1) // columns
            graph_height = max(0, body_height - nav_rows - 1)
            body = (
                [menu._ansi(title, menu._BOLD + menu._ACCENT),
                 *menu._orbit(width, graph_height, angle, selected)]
                if graph_height
                else []
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
                    label = f"{number} {labels[index]}"
                    parts.append(button(label, selected=index == selected, width=cell_width))
                    regions.append(
                        menu.HitRegion(col * cell_width + 1, screen_row, cell_width, f"item:{index}")
                    )
                body.append("".join(parts))
            body = (body + [""] * body_height)[:body_height]
            frame = menu.ScreenFrame(
                [menu._clip_cells(line, width) for line in [*top, *body, footer_line]],
                regions + controls,
            )
            return menu._starlight(frame, width, angle)

        # Landscape mode: a narrow, stable navigation rail leaves the visual
        # field to the module description and the animated globe.
        nav_width = min(22, max(16, width // 5))
        graph_width = max(1, width - nav_width - 3)
        spacious = body_height >= 16
        left: list[str] = [menu._ansi("工作区", menu._DIM), ""] if spacious else []

        for index, label in enumerate(labels):
            number = "0" if index == len(labels) - 1 else str(index + 1)
            line = button(
                f"{number} {label}",
                selected=index == selected,
                width=nav_width,
            )
            regions.append(menu.HitRegion(1, len(top) + len(left) + 1, nav_width, f"item:{index}"))
            left.append(line)
            if spacious and index < len(labels) - 1:
                left.append("")

        stats_lines = [
            "",
            menu._ansi("校园概览", menu._DIM),
            f"学生 {stats.get('students', 0)} / 班级 {stats.get('classes', 0)}",
            f"课程 {stats.get('courses', 0)} / 选课 {stats.get('enrollments', 0)}",
        ]
        for line in stats_lines:
            if len(left) < body_height:
                left.append(line)

        right = [menu._ansi(f"{selected + 1:02d} / {title}", menu._BOLD + menu._ACCENT)]
        if graph_width >= 28 and body_height >= 9:
            right.extend([menu._ansi(description, menu._DIM), ""])

        # The former actions line lived immediately above the real footer and
        # visually looked like a second bottom bar.  Module actions stay in the
        # clickable submenu; the home page gives all remaining height to art.
        graph_height = max(1, body_height - len(right))
        right.extend(menu._orbit(graph_width, graph_height, angle, selected))

        body: list[str] = []
        for row in range(body_height):
            left_line = left[row] if row < len(left) else ""
            right_line = right[row] if row < len(right) else ""
            body.append(
                menu._pad_cells(menu._clip_cells(left_line, nav_width), nav_width)
                + menu._ansi(" │ ", menu._DIM)
                + menu._clip_cells(right_line, graph_width)
            )

        frame = menu.ScreenFrame(
            [menu._clip_cells(line, width) for line in [*top, *body, footer_line]],
            regions + controls,
        )
        return menu._starlight(frame, width, angle)

    menu._footer = footer
    menu._selection_frame = selection_frame
    menu._home_frame = home_frame
