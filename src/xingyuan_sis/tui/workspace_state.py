from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .workspace_data import Catalog, Field


@dataclass
class Form:
    mode: str
    fields: tuple[Field, ...] = ()
    values: dict[str, Any] = field(default_factory=dict)
    original: dict[str, Any] | None = None
    position: int = 0
    options: list[tuple[Any, str]] | None = None
    option_index: int = 0


@dataclass
class Workspace:
    key: str
    view: int = 0
    query: str = ""
    selected: int = 0
    roster_scroll: int = 0
    details: bool = False
    detail_scroll: int = 0
    detail_selected: int = 0
    notice: str = ""
    form: Form | None = None
    report: list[str] = field(default_factory=list)
    history: list[tuple[str, int, str, int, int]] = field(default_factory=list)

    def rows(self, catalog: Catalog) -> list[dict[str, Any]]:
        rows = catalog.rows(self.key, self.view, self.query) if self.key != "data" else []
        self.selected = min(max(0, self.selected), max(0, len(rows) - 1))
        self.roster_scroll = min(max(0, self.roster_scroll), max(0, len(rows) - 1))
        return rows

    def current(self, catalog: Catalog) -> dict[str, Any] | None:
        rows = self.rows(catalog)
        return rows[self.selected] if rows else None

    def switch(self, key: str) -> None:
        self.key, self.view, self.query, self.selected, self.roster_scroll = key, 0, "", 0, 0
        self.details, self.detail_scroll, self.detail_selected, self.form = False, 0, 0, None
