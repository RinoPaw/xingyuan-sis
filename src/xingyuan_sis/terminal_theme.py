from __future__ import annotations

import math
from types import ModuleType
from typing import Sequence


_BUTTON = "\x1b[48;5;237m\x1b[38;5;252m"
_BAR_SURFACE = "\x1b[48;5;236m\x1b[38;5;250m"
_TOPBAR = "\x1b[48;5;234m\x1b[38;5;110m\x1b[1m"
_SPARKLE_DOTS = ("⠁", "⠂", "⠄", "⠈", "⠐", "⠠", "⡀", "⢀")
_SPARKLE_FRAME = 0.150
_SPARKLE_BG = 38
_SPARKLE_FG = 208


def install(menu: ModuleType) -> None:
    """Install the responsive visual theme onto the stdlib terminal menu."""
    if getattr(menu, "_xingyuan_theme_installed", False):
        return
    menu._xingyuan_theme_installed = True

    base_paint = menu._paint
    last_geometry: tuple[int, int] | None = None

    def bar_space(count: int) -> str:
        return menu._ansi(" " * max(0, count), _BAR_SURFACE)

    def button(label: str, *, selected: bool = False, width: int | None = None) -> str:
        shown = f"[ {label} ]"
        if width is not None:
            shown = menu._pad_cells(menu._clip_cells(shown, width), width)
        return menu._ansi(shown, menu._SELECTED if selected else _BUTTON)

    def topbar(width: int, *, database: str | None = None) -> str:
        left = "✦ 星原 / 教务台"
        right = f"LOCAL / {database}" if database else ""
        if right and menu._display_width(left) + menu._display_width(right) + 2 <= width:
            gap = width - menu._display_width(left) - menu._display_width(right)
            plain = left + " " * gap + right
        else:
            plain = menu._pad_cells(menu._clip_cells(left, width), width)
        return menu._ansi(menu._pad_cells(menu._clip_cells(plain, width), width), _TOPBAR)

    def footer(
        width: int,
        buttons: Sequence[tuple[str, str, str]],
        row: int,
    ) -> tuple[str, list[object]]:
        def labels(use_short: bool) -> list[tuple[str, str]]:
            return [
                (f"[ {short if use_short else long} ]", action)
                for long, short, action in buttons
            ]

        chosen = labels(False)
        minimum = sum(menu._display_width(text) for text, _ in chosen) + max(0, len(chosen) - 1)
        if minimum > width:
            chosen = labels(True)

        # Keep the exit control when an unusually narrow terminal cannot fit
        # every compact button. Drop optional middle controls first.
        while chosen and (
            sum(menu._display_width(text) for text, _ in chosen) + max(0, len(chosen) - 1) > width
        ):
            if len(chosen) > 2:
                chosen.pop(-2)
            else:
                chosen.pop(0)

        if not chosen:
            return bar_space(width), []

        button_width = sum(menu._display_width(text) for text, _ in chosen)
        free = max(0, width - button_width)
        slots = len(chosen) + 1
        base_gap, extra = divmod(free, slots)
        gaps = [base_gap + (1 if index < extra else 0) for index in range(slots)]

        parts: list[str] = [bar_space(gaps[0])]
        regions: list[object] = []
        cell = gaps[0]
        for index, (shown, action) in enumerate(chosen):
            regions.append(menu.HitRegion(cell + 1, row, menu._display_width(shown), action))
            parts.append(menu._ansi(shown, _BUTTON))
            cell += menu._display_width(shown)
            parts.append(bar_space(gaps[index + 1]))
            cell += gaps[index + 1]

        return "".join(parts), regions

    def sparkle(frame, width: int, phase: float):
        """Render the Codex-style stable sparkle field over untouched space.

        Coordinates decide whether a star exists and also choose its Braille dot,
        period and phase. Nothing is born, moved or destroyed while the layout is
        stable; only brightness changes. That makes the field feel quiet instead
        of like particles popping around the screen.
        """
        # ``phase`` is the globe angle (monotonic seconds * 0.85). Convert it
        # back to seconds and quantize to Codex's 150 ms sparkle cadence.
        seconds = max(0.0, phase / 0.85)
        seconds = math.floor(seconds / _SPARKLE_FRAME) * _SPARKLE_FRAME
        mask = (1 << 64) - 1
        truecolor = menu.os.environ.get("COLORTERM", "").lower() in {"truecolor", "24bit"}

        for row in range(1, len(frame.lines) - 1):
            original = frame.lines[row]
            plain = menu._ANSI_RE.sub("", original)

            # Treat only the interior of genuinely empty runs as sky. This is
            # our equivalent of Codex's protected composer text area, and keeps
            # dots out of labels, prose and clickable controls.
            allowed: set[int] = set()
            cell = 0
            run_start: int | None = None
            for char in plain + "x":
                if char == " " and run_start is None:
                    run_start = cell
                elif char != " " and run_start is not None:
                    start = run_start + 2
                    stop = min(cell - 2, width)
                    for x in range(start, stop):
                        if menu._hit_action(menu.MouseClick(x + 1, row + 1), frame.regions) is None:
                            allowed.add(x)
                    run_start = None
                cell += menu._cell_width(char)

            if not allowed:
                continue

            targets: dict[int, str] = {}
            for x in allowed:
                # Same coordinate hash used by Codex's sparkle.rs.
                hash_value = ((row - 1) * 65537 + x) & mask
                hash_value = ((hash_value ^ (hash_value >> 16)) * 0x45D9F3B) & mask
                hash_value = ((hash_value ^ (hash_value >> 16)) * 0x45D9F3B) & mask
                hash_value ^= hash_value >> 16
                if hash_value % 5 != 0:
                    continue

                period = 4.0 + (hash_value % 31) / 10.0
                sparkle_phase = (
                    seconds / period + (hash_value % 997) / 997.0
                ) % 1.0
                brightness = (
                    math.sin(sparkle_phase * math.pi) ** 12
                    * 0.55
                )
                if brightness < 0.04:
                    continue

                glyph = _SPARKLE_DOTS[(hash_value // 161) % len(_SPARKLE_DOTS)]
                level = round(_SPARKLE_BG + (_SPARKLE_FG - _SPARKLE_BG) * brightness)
                if truecolor:
                    style = f"\x1b[38;2;{level};{level};{level}m"
                else:
                    # xterm's grayscale ramp is close enough to the same blend.
                    gray = max(235, min(244, 232 + round((level - 8) / 10)))
                    style = f"\x1b[38;5;{gray}m"
                targets[x] = menu._ansi(glyph, style)

            if not targets:
                continue

            parts: list[str] = []
            cell = 0
            for token in menu.re.split(f"({menu._ANSI_RE.pattern})", original):
                if menu._ANSI_RE.fullmatch(token):
                    parts.append(token)
                    continue
                for char in token:
                    parts.append(targets.get(cell, char) if char == " " else char)
                    cell += menu._cell_width(char)
            frame.lines[row] = "".join(parts)

        return frame

    def selection_frame(
        title: str,
        items: Sequence[str],
        selected: int,
        back_label: str,
    ):
        terminal = menu._terminal_size()
        width, height = max(1, terminal.columns - 1), max(3, terminal.lines)
        capacity = max(1, height - 3)
        first = min(max(0, selected - capacity + 1), max(0, len(items) - capacity))
        lines = [topbar(width), menu._ansi(f"首页 / {title}", menu._DIM)]
        regions: list[object] = []
        panel_width = min(width, 36 if width >= 72 else width)

        for index in range(first, min(len(items), first + capacity)):
            label = f"{index + 1}  {items[index]}"
            line = button(label, selected=index == selected, width=panel_width)
            regions.append(menu.HitRegion(1, len(lines) + 1, panel_width, f"item:{index}"))
            lines.append(line)

        while len(lines) < height:
            lines.append("")

        if width >= 72 and height >= 9:
            details = [
                items[selected],
                "",
                "点击按钮或按 Enter 打开。",
                "方向键 / 滚轮切换选项。",
                "q 返回上一级。",
            ]
            for offset, detail in enumerate(details, start=2):
                if offset < height - 1:
                    lines[offset] = (
                        menu._pad_cells(lines[offset], panel_width + 3)
                        + menu._ansi(detail, menu._ACCENT if offset == 2 else menu._DIM)
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

        top = [topbar(width, database=database)]
        body_height = max(0, height - 2)
        footer_line, controls = menu._home_footer(width, height, animate)
        regions: list[object] = []

        # The layout mode depends only on width. Soft-keyboard height changes
        # therefore cannot make the whole home screen oscillate between modes.
        if width < 38:
            columns = 2 if width >= 28 else 1
            nav_rows = (len(labels) + columns - 1) // columns
            graph_height = max(0, body_height - nav_rows - 1)
            body = [menu._ansi(title, menu._BOLD + menu._ACCENT)]
            if graph_height:
                body.extend(menu._orbit(width, graph_height, angle, selected))
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
                        button(f"{number} {labels[index]}", selected=index == selected, width=cell_width)
                    )
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

        nav_width = min(22, max(14, width // 5))
        graph_width = max(1, width - nav_width - 3)
        left: list[str] = [menu._ansi("工作区", menu._DIM)]

        # Keep navigation density fixed at every height; the earlier blank rows
        # made Termux visibly jump as the IME changed the reported line count.
        for index, label in enumerate(labels):
            number = "0" if index == len(labels) - 1 else str(index + 1)
            line = button(f"{number} {label}", selected=index == selected, width=nav_width)
            regions.append(menu.HitRegion(1, len(top) + len(left) + 1, nav_width, f"item:{index}"))
            left.append(line)

        for line in (
            "",
            menu._ansi("校园概览", menu._DIM),
            f"学生 {stats.get('students', 0)} / 班级 {stats.get('classes', 0)}",
            f"课程 {stats.get('courses', 0)} / 选课 {stats.get('enrollments', 0)}",
        ):
            if len(left) < body_height:
                left.append(line)

        right = [menu._ansi(f"{selected + 1:02d} / {title}", menu._BOLD + menu._ACCENT)]
        if graph_width >= 28 and body_height >= 8:
            right.extend([menu._ansi(description, menu._DIM), ""])
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

    def paint(lines: Sequence[str], previous: Sequence[str] = ()) -> None:
        nonlocal last_geometry
        geometry = (len(lines), max((menu._display_width(line) for line in lines), default=0))
        if geometry != last_geometry:
            if menu.sys.stdout.isatty():
                menu.sys.stdout.write("\x1b[0m\x1b[2J\x1b[H")
                menu.sys.stdout.flush()
            previous = ()
            last_geometry = geometry
        base_paint(lines, previous)

    menu._footer = footer
    menu._selection_frame = selection_frame
    menu._starlight = sparkle
    menu._home_frame = home_frame
    menu._paint = paint
