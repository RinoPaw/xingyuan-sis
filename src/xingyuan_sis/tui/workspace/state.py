from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .data import Catalog, Field


class FocusArea(str, Enum):
    """The single keyboard-focus owner inside a workspace."""

    ROSTER = "roster"
    INSPECTOR = "inspector"
    DASHBOARD = "dashboard"


class ContentPanel(str, Enum):
    """The record panel that remains the current content context.

    Wide layouts show both panels; narrow layouts render only the active panel.
    """

    ROSTER = "roster"
    INSPECTOR = "inspector"


class FieldSessionOwner(str, Enum):
    """Where a confirmed field session writes its values."""

    RECORD = "record"
    FORM = "form"


@dataclass(frozen=True)
class FocusContext:
    """Exact interaction context that a temporary task may restore."""

    focus: FocusArea
    content_panel: ContentPanel
    detail_scroll: int
    detail_selected: int


@dataclass
class Form:
    """A complete transaction draft.

    Forms own transaction-wide values and the currently selected field. They do
    not own a second field editor: entering any field creates a FieldSession,
    exactly as it does for an existing record.
    """

    mode: str
    fields: tuple[Field, ...] = ()
    values: dict[str, Any] = field(default_factory=dict)
    original: dict[str, Any] | None = None
    position: int = 0
    return_to: FocusContext | None = None


@dataclass
class FieldSession:
    """One local field/group edit, independent of its persistence destination."""

    fields: tuple[Field, ...]
    values: dict[str, Any]
    original: dict[str, Any]
    anchor_key: str
    owner: FieldSessionOwner = FieldSessionOwner.RECORD
    active: int = 0
    options: list[tuple[Any, str]] | None = None
    option_index: int = 0
    # Unconfirmed masked text is previewed without modifying confirmed values.
    preview_values: dict[str, Any] | None = None

    @property
    def field(self) -> Field:
        return self.fields[self.active]

    @property
    def active_key(self) -> str:
        return self.field.key


@dataclass(frozen=True)
class SearchContext:
    """Roster position to restore when a temporary filter is dismissed."""

    query: str
    selected: int
    roster_scroll: int


@dataclass(frozen=True)
class Location:
    key: str
    view: int
    query: str
    selected: int
    roster_scroll: int
    record_id: int | None
    focus: FocusArea
    content_panel: ContentPanel
    detail_scroll: int
    detail_selected: int
    search_context: SearchContext | None = None


@dataclass
class Workspace:
    key: str
    view: int = 0
    query: str = ""
    search_context: SearchContext | None = None
    searching: bool = False
    selected: int = 0
    roster_scroll: int = 0
    focus: FocusArea = FocusArea.ROSTER
    content_panel: ContentPanel = ContentPanel.ROSTER
    detail_scroll: int = 0
    detail_selected: int = 0
    notice: str = ""
    form: Form | None = None
    field_session: FieldSession | None = None
    report: list[str] = field(default_factory=list)
    history: list[Location] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.key == "data" and self.focus is FocusArea.ROSTER:
            self.focus = FocusArea.DASHBOARD

    def rows(self, catalog: Catalog) -> list[dict[str, Any]]:
        """Return the current roster projection without mutating interaction state."""
        return catalog.rows(self.key, self.view, self.query) if self.key != "data" else []

    def reconcile_roster(self, row_count: int) -> None:
        """Normalize roster interaction state after an explicit state/data mutation."""
        row_count = max(0, row_count)
        self.selected = min(max(0, self.selected), max(0, row_count - 1))
        self.roster_scroll = min(max(0, self.roster_scroll), max(0, row_count - 1))

    def current(self, catalog: Catalog) -> dict[str, Any] | None:
        rows = self.rows(catalog)
        if not 0 <= self.selected < len(rows):
            return None
        return rows[self.selected]

    def commit_search(self, query: str) -> None:
        """Apply a confirmed filter; preserve the original unfiltered viewport."""
        if not query:
            self.clear_search()
            return
        if self.search_context is None:
            self.search_context = SearchContext(self.query, self.selected, self.roster_scroll)
        self.query, self.selected, self.roster_scroll = query, 0, 0
        self.detail_scroll, self.detail_selected = 0, 0
        self.set_focus(FocusArea.ROSTER)

    def clear_search(self) -> None:
        """Dismiss the confirmed filter and restore the original roster."""
        if self.search_context is not None:
            context = self.search_context
            self.query = context.query
            self.selected = context.selected
            self.roster_scroll = context.roster_scroll
        else:
            self.query, self.selected, self.roster_scroll = "", 0, 0
        self.search_context = None
        self.searching = False
        self.detail_scroll, self.detail_selected = 0, 0
        self.set_focus(FocusArea.ROSTER)

    def select_row(self, index: int) -> None:
        """Select a real roster record."""
        self.selected = max(0, index)

    def set_focus(self, area: FocusArea) -> None:
        """Move keyboard focus while keeping the content-panel invariant."""
        self.focus = area
        if area is FocusArea.ROSTER:
            self.content_panel = ContentPanel.ROSTER
        elif area is FocusArea.INSPECTOR:
            self.content_panel = ContentPanel.INSPECTOR

    def focus_roster(self) -> None:
        """Return to record selection."""
        self.set_focus(FocusArea.ROSTER)

    def focus_content(self) -> None:
        """Restore the active content panel after a transaction."""
        if self.key == "data":
            self.set_focus(FocusArea.DASHBOARD)
        elif self.content_panel is ContentPanel.INSPECTOR:
            self.set_focus(FocusArea.INSPECTOR)
        else:
            self.focus_roster()

    def capture_focus_context(self) -> FocusContext:
        """Snapshot the interaction context before a temporary task may restore."""
        return FocusContext(
            self.focus,
            self.content_panel,
            self.detail_scroll,
            self.detail_selected,
        )

    def restore_focus_context(self, context: FocusContext | None) -> None:
        """Restore a context previously returned by :meth:`capture_focus_context`."""
        if context is None:
            return
        self.focus = context.focus
        self.content_panel = context.content_panel
        self.detail_scroll = context.detail_scroll
        self.detail_selected = context.detail_selected

    def switch(self, key: str) -> None:
        self.key, self.view, self.query, self.selected, self.roster_scroll = key, 0, "", 0, 0
        self.focus = FocusArea.DASHBOARD if key == "data" else FocusArea.ROSTER
        self.content_panel = ContentPanel.ROSTER
        self.detail_scroll, self.detail_selected = 0, 0
        self.form, self.field_session = None, None
        self.search_context, self.searching = None, False

    def visit(self, key: str, identifier: str, catalog: Catalog) -> None:
        row = self.current(catalog)
        self.history.append(Location(
            self.key, self.view, self.query, self.selected, self.roster_scroll,
            row["id"] if row else None, self.focus, self.content_panel,
            self.detail_scroll, self.detail_selected,
            self.search_context,
        ))
        self.switch(key)
        rows = self.rows(catalog)
        self.selected = next((i for i, row in enumerate(rows)
                              if str(row["id"]) == identifier), 0)
        self.reconcile_roster(len(rows))

    def restore(self, catalog: Catalog) -> None:
        location = self.history.pop()
        self.switch(location.key)
        self.view, self.query = location.view, location.query
        self.search_context = location.search_context
        rows = self.rows(catalog)
        self.selected = next((i for i, row in enumerate(rows)
                              if row["id"] == location.record_id), location.selected)
        self.roster_scroll = location.roster_scroll
        self.focus, self.content_panel = location.focus, location.content_panel
        self.detail_scroll, self.detail_selected = location.detail_scroll, location.detail_selected
        self.reconcile_roster(len(rows))
