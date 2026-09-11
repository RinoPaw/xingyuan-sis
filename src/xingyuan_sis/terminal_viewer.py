"""Resize-aware, mouse-enabled viewer for menu query results."""
from bisect import bisect_right
from . import menu
from .terminal_ui import _wrap_line


def show(text: str, title: str) -> None:
    anchor = 0
    cached_width = -1
    records = []
    positions = []
    previous = []
    with menu._mouse_tracking():
        while True:
            terminal = menu._terminal_size()
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
            lines = [menu._ansi(f"✦ 星原 / {title}", menu._BOLD + menu._ACCENT),
                     menu._ansi(f"第 {first + 1}–{last} / {len(records)} 行", menu._DIM),
                     menu._ansi("─" * width, menu._DIM), *records[first:last]]
            while len(lines) < height - 1:
                lines.append("")
            next_text = "Enter 返回" if last == len(records) else "Enter 下一页"
            footer, regions = menu._footer(width, (("p 上一页", "p上页", "prev"),
                                                    (next_text, "Enter", "next"),
                                                    ("q 返回", "q返回", "back")), height)
            lines.append(footer)
            lines = [menu._clip_cells(line, width) for line in lines]
            if lines != previous:
                menu._paint(lines, previous)
                previous = lines
            key = menu._read_key(0.15)
            if isinstance(key, menu.MouseClick):
                key = menu._hit_action(key, regions)
            if key == "back":
                return
            if key in {"select", "next", "page_down"}:
                if last == len(records):
                    return
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
