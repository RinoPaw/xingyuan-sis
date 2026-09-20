from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .data import Catalog, Field


class FocusArea(str, Enum):
    """The single keyboard-focus owner inside a workspace."""

    ROSTER = "roster"
    INSPECTOR = "inspector"
    TOOLBAR = "toolbar"
    DASHBOARD = "dashboard"


class ContentPanel(str, Enum):
    """The record panel that remains the current content context.

    Wide layouts show both panels, while single-pane layouts render only this
    panel. Toolbar focus does not change it, so leaving the toolbar returns to
    the content panel the user came from.
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
    action_selected: int


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

    @property
    def field(self) -> Field:
        return self.fields[self.active]

    @property
    def active_key(self) -> str:
        return self.field.key


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
    action_selected: int = 0


@dataclass
class Workspace:
    key: str
    view: int = 0
    query: str = ""
    selected: int = 0
    roster_scroll: int = 0
    focus: FocusArea = FocusArea.ROSTER
    content_panel: ContentPanel = ContentPanel.ROSTER
    detail_scroll: int = 0
    detail_selected: int = 0
    action_selected: int = 0
    notice: str = ""
    form: Form | None = None
    field_session: FieldSession | None = None
    report: list[str] = field(default_factory=list)
    history: list[Location] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.key == "data" and self.focus is FocusArea.ROSTER:
            self.focus = FocusArea.DASHBOARD

    def rows(self, catalog: Catalog) -> list[dict[str, Any]]:
        rows = catalog.rows(self.key, self.view, self.query) if self.key != "data" else []
        self.selected = min(max(0, self.selected), max(0, len(rows) - 1))
        self.roster_scroll = min(max(0, self.roster_scroll), max(0, len(rows) - 1))
        return rows

    def current(self, catalog: Catalog) -> dict[str, Any] | None:
        rows = self.rows(catalog)
        return rows[self.selected] if rows else None

    def set_focus(self, area: FocusArea) -> None:
        """Move keyboard focus while keeping the content-panel invariant."""
        self.focus = area
        if area is FocusArea.ROSTER:
            self.content_panel = ContentPanel.ROSTER
        elif area is FocusArea.INSPECTOR:
            self.content_panel = ContentPanel.INSPECTOR

    def focus_content(self) -> None:
        """Return from toolbar focus to the content panel it belongs to."""
        if self.key == "data":
            self.focus = FocusArea.DASHBOARD
        else:
            self.focus = (
                FocusArea.INSPECTOR
                if self.content_panel is ContentPanel.INSPECTOR
                else FocusArea.ROSTER
            )

    def capture_focus_context(self) -> FocusContext:
        """Snapshot the interaction context before a temporary task takes focus."""
        return FocusContext(
            self.focus,
            self.content_panel,
            self.detail_scroll,
            self.detail_selected,
            self.action_selected,
        )

    def restore_focus_context(self, context: FocusContext | None) -> None:
        """Restore a context previously returned by :meth:`capture_focus_context`."""
        if context is None:
            return
        self.focus = context.focus
        self.content_panel = context.content_panel
        self.detail_scroll = context.detail_scroll
        self.detail_selected = context.detail_selected
        self.action_selected = context.action_selected

    def switch(self, key: str) -> None:
        self.key, self.view, self.query, self.selected, self.roster_scroll = key, 0, "", 0, 0
        self.focus = FocusArea.DASHBOARD if key == "data" else FocusArea.ROSTER
        self.content_panel = ContentPanel.ROSTER
        self.detail_scroll, self.detail_selected = 0, 0
        self.form, self.field_session = None, None
        self.action_selected = 0

    def visit(self, key: str, identifier: str, catalog: Catalog) -> None:
        row = self.current(catalog)
        self.history.append(Location(
            self.key, self.view, self.query, self.selected, self.roster_scroll,
            row["id"] if row else None, self.focus, self.content_panel,
            self.detail_scroll, self.detail_selected, self.action_selected,
        ))
        self.switch(key)
        self.selected = next((i for i, row in enumerate(self.rows(catalog))
                              if str(row["id"]) == identifier), 0)

    def restore(self, catalog: Catalog) -> None:
        location = self.history.pop()
        self.switch(location.key)
        self.view, self.query = location.view, location.query
        self.selected = next((i for i, row in enumerate(self.rows(catalog))
                              if row["id"] == location.record_id), location.selected)
        self.roster_scroll = location.roster_scroll
        self.focus, self.content_panel = location.focus, location.content_panel
        self.detail_scroll, self.detail_selected = location.detail_scroll, location.detail_selected
        self.action_selected = location.action_selected
        self.rows(catalog)
