from __future__ import annotations

from typing import Any

from . import screen, theme


def safe(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return " ".join("".join(char for char in str(value) if char.isprintable() or char == "\n").split())


def metric_summary(metrics: list[tuple[str, str]]) -> str:
    return "    ".join(
        screen._ansi(value, screen._BOLD + screen._TEXT_ACCENT)
        + " "
        + screen._ansi(label, screen._TEXT_SECONDARY)
        for label, value in metrics
    )


def metric_pair(label: str, value: object) -> str:
    return (
        screen._ansi(str(value), screen._BOLD + screen._TEXT_ACCENT)
        + " "
        + screen._ansi(label, screen._TEXT_SECONDARY)
    )


def panel_heading(text: str, focused: bool) -> str:
    marker = "▌ " if focused else "  "
    style = screen._BOLD + (screen._TEXT_ACCENT if focused else screen._TEXT_PRIMARY)
    return screen._ansi(marker + text, style)


class Board:
    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        self.rows: list[list[tuple[int, str]]] = [[] for _ in range(height)]
        self.regions: list[screen.HitRegion] = []

    def put(self, x: int, y: int, text: str, style: str = "", action: str = "", width: int | None = None) -> None:
        if not (0 <= y < self.height and 0 <= x < self.width):
            return
        text = screen._clip_cells(text, min(width if width is not None else self.width - x, self.width - x))
        if style:
            text = screen._ansi(text, style)
        self.rows[y].append((x, text))
        if action and text:
            self.regions.append(screen.HitRegion(x + 1, y + 1, screen._display_width(text), action))

    def button(self, x: int, y: int, label: str, action: str, *, selected: bool = False) -> int:
        text = theme.button(label, selected=selected)
        self.put(x, y, text, action=action)
        return x + screen._display_width(text) + 1

    def frame(self) -> screen.ScreenFrame:
        lines = []
        for parts in self.rows:
            text = ""
            for x, part in sorted(parts, key=lambda part: part[0]):
                text = screen._pad_cells(text, x) + part
            lines.append(screen._pad_cells(screen._clip_cells(text, self.width), self.width))
        return screen.ScreenFrame(lines, self.regions)


def identity(key: str, row: dict[str, Any]) -> tuple[str, str]:
    if key == "grades":
        return safe(row["student_name"]), f"{safe(row['course_name'])} · {safe(row['semester'])}"
    identifier = row.get("student_no", row.get("course_code", row.get("code")))
    return safe(row["name"]), safe(identifier)
