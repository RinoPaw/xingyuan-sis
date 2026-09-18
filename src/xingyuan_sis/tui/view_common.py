from __future__ import annotations

from typing import Any

from . import screen, theme
from .board import Board as CoordinateBoard


class Board(CoordinateBoard):
    """Workspace board with the shared themed-button convenience."""

    def button(
        self,
        x: int,
        y: int,
        label: str,
        action: str,
        *,
        selected: bool = False,
        current: bool = False,
    ) -> int:
        text = theme.button(label, selected=selected, current=current)
        self.put(x, y, text, action=action)
        return x + screen._display_width(text) + 1


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


def identity(key: str, row: dict[str, Any]) -> tuple[str, str]:
    if key == "announcements":
        return safe(row["title"]), f"{safe(row['class_name'])} · #{row['id']}"
    if key == "grades":
        return safe(row["student_name"]), f"{safe(row['course_name'])} · {safe(row['semester'])}"
    identifier = row.get("student_no", row.get("course_code", row.get("code")))
    return safe(row["name"]), safe(identifier)
