"""Resize-aware, mouse-enabled viewer for menu query results."""
from bisect import bisect_right
from . import screen, keys, theme
from ..terminal_ui import _wrap_line


def show(text: str, title: str) -> None:
    anchor = 0
    cached_width = -1
    records = []
    positions = []
    previous = []
    with keys._mouse_tracking():
        while True:
            terminal = screen._terminal_size()
            width, height = max(2, terminal.columns - 1), max(5, terminal.lines)
            if width != cached_width:
                records, positions = [], []
                position = 0
                for line in (text.rstrip("\n").splitlines() or ["(无数据)"]):
                    for part in _wrap_line(line, width):
                        positions.append(position)
                        records.append(part)
                        position += len(part)
                    position += 1
                cached_width = width
            first = max(0, bisect_right(positions, anchor) - 1)
            page_size = max(1, height - 4)
            last = min(len(records), first + page_size)
            breadcrumb, navigation = screen._breadcrumb(title, width)
            lines = [
                theme.topbar(width),
                breadcrumb,
                screen._ansi(f"第 {first + 1}–{last} / {len(records)} 行", screen._TEXT_SECONDARY),
                *records[first:last],
            ]
            while len(lines) < height - 1:
                lines.append("")

            buttons = [("p 上一页", "p上页", "prev")]
            if last < len(records):
                buttons.append(("Enter 下一页", "Enter", "next"))
            buttons.append(("Esc", "Esc", "back"))
            footer, regions = theme.footer(width, tuple(buttons), height)

            lines.append(footer)
            lines = [screen._clip_cells(line, width) for line in lines]
            if lines != previous:
                screen._paint(lines, previous)
                previous = lines
            key = keys._read_key(0.15)
            if isinstance(key, keys.MouseScroll):
                key = key.direction
            if isinstance(key, screen.MouseClick):
                key = screen._hit_action(key, navigation + regions)
                if key and key.startswith("navigate:"):
                    raise screen.NavigateTo(key.removeprefix("navigate:"))
            if key == "back":
                return
            if key in {"select", "next", "page_down"}:
                if last < len(records):
                    first = last
            elif key in {"pause", "prev", "page_up"}:
                first = max(0, first - page_size)
            elif key == "down":
                first = min(len(records) - 1, first + 1)
            elif key == "up":
                first = max(0, first - 1)
            elif key == "home":
                first = 0
            elif key == "end":
                first = max(0, len(records) - page_size)
            anchor = positions[first]
