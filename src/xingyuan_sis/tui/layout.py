"""Shared viewport geometry for rendering and keyboard navigation."""
from __future__ import annotations

from dataclasses import dataclass

from . import screen


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
    def panel_x(self) -> int:
        return 0 if self.compact else self.width // 2 + 3 if self.split else 1

    @property
    def panel_width(self) -> int:
        return max(1, self.width - self.panel_x - (0 if self.compact else 1))

    @property
    def detail_top(self) -> int:
        return 4 if self.compact else 9

    @property
    def detail_capacity(self) -> int:
        return max(1, self.height - self.detail_top - (2 if self.compact else 3))

    @property
    def detail_offset(self) -> int:
        # The compact heading already identifies the current record.
        return 1 if self.compact else 0
