from __future__ import annotations

from . import screen


class Board:
    """Compose terminal content by coordinates, independent of theme and domain."""

    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        self.rows: list[list[tuple[int, str]]] = [[] for _ in range(height)]
        self.regions: list[screen.HitRegion] = []

    def put(
        self,
        x: int,
        y: int,
        text: str,
        style: str = "",
        action: str = "",
        width: int | None = None,
    ) -> None:
        if not (0 <= y < self.height and 0 <= x < self.width):
            return
        limit = min(width if width is not None else self.width - x, self.width - x)
        text = screen._clip_cells(text, limit)
        if style:
            text = screen._ansi(text, style)
        self.rows[y].append((x, text))
        if action and text:
            self.regions.append(
                screen.HitRegion(x + 1, y + 1, screen._display_width(text), action)
            )

    def frame(self) -> screen.ScreenFrame:
        lines: list[str] = []
        for parts in self.rows:
            text = ""
            for x, part in sorted(parts, key=lambda item: item[0]):
                text = screen._pad_cells(text, x) + part
            lines.append(screen._pad_cells(screen._clip_cells(text, self.width), self.width))
        return screen.ScreenFrame(lines, self.regions)
