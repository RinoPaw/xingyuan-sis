"""Shared viewport geometry for rendering and keyboard navigation."""
from __future__ import annotations

from dataclasses import dataclass

from . import screen


_CONTROL_ROWS = {
    "students": 0,
    "announcements": 0,
    "courses": 1,
    "grades": 1,
    "departments": 1,
    "majors": 1,
    "classes": 1,
    "data": 2,
}

_MAX_ROSTER_WIDTH = 72
_MIN_INSPECTOR_WIDTH = 28
_MAX_INSPECTOR_WIDTH = 42


def visible_start(selected: int, total: int, capacity: int, first: int = 0) -> int:
    """Keep a selection visible without moving an already suitable viewport."""
    capacity = max(1, capacity)
    maximum = max(0, total - capacity)
    first = min(max(0, first), maximum)
    if selected < first:
        first = selected
    elif selected >= first + capacity:
        first = selected - capacity + 1
    return min(max(0, first), maximum)


@dataclass(frozen=True)
class WorkspaceLayout:
    width: int
    height: int
    inspector_width: int | None = None

    @classmethod
    def measure(cls) -> WorkspaceLayout:
        terminal = screen._terminal_size()
        return cls(max(1, terminal.columns - 1), max(4, terminal.lines))

    @property
    def compact(self) -> bool:
        return self.height < 20 or self.width < 24

    @property
    def split(self) -> bool:
        return not self.compact and self.width >= 76

    @property
    def desired_inspector_width(self) -> int:
        desired = _MAX_INSPECTOR_WIDTH if self.inspector_width is None else self.inspector_width
        return min(_MAX_INSPECTOR_WIDTH, max(_MIN_INSPECTOR_WIDTH, desired))

    @property
    def split_x(self) -> int:
        """Keep a dense roster beside a content-sized inspector on wide terminals."""
        if not self.split:
            return self.width
        desired = self.desired_inspector_width
        balanced = max(self.width // 2, self.width - desired - 4)
        return min(_MAX_ROSTER_WIDTH, balanced)

    @property
    def panel_x(self) -> int:
        return 0 if self.compact else self.split_x + 3 if self.split else 1

    @property
    def panel_width(self) -> int:
        available = max(1, self.width - self.panel_x - (0 if self.compact else 1))
        return min(available, self.desired_inspector_width) if self.split else available

    @property
    def action_row(self) -> int:
        return 2 if self.compact else 3

    def separator_row(self, key: str) -> int:
        """Row separating workspace controls from record content."""
        if self.compact:
            return self.action_row
        return self.action_row + 1 + _CONTROL_ROWS.get(key, 0)

    def panel_heading_row(self, key: str) -> int:
        """Row containing the roster/inspector heading."""
        return 3 if self.compact else self.separator_row(key) + 1

    def panel_content_row(self, key: str) -> int:
        """First row available to panel content below its heading."""
        return self.panel_heading_row(key) + 1

    def panel_capacity(self, key: str) -> int:
        """Fill inspector content through the row immediately above the footer."""
        return max(1, self.height - self.panel_content_row(key) - 1)

    def roster_capacity(self, key: str) -> int:
        """Fill every record row above the footer after the roster column header."""
        data_row = self.panel_content_row(key) + 1
        footer_row = self.height - 1
        return max(1, footer_row - data_row)
