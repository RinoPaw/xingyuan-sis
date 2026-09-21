"""Workspace controller orchestration."""
from __future__ import annotations

from pathlib import Path
import sqlite3

from .. import keys
from ...auth import Identity
from .data import Catalog
from .events import interact
from .field_session import cancel as cancel_field_session, edit_current
from .forms import apply_form, read_search
from .roster_effects import play_student_roster_effect
from .state import ContentPanel, FieldSession, FieldSessionOwner, FocusArea, Form, Workspace


__all__ = [
    "ContentPanel", "FieldSession", "FieldSessionOwner", "FocusArea", "Form", "Workspace", "run"
]


def run(
    db_path: Path | str | None,
    collection: str,
    *,
    identity: Identity | None = None,
    query: str = "",
) -> None:
    catalog = Catalog(db_path, identity)
    focus = FocusArea.INSPECTOR if query and collection != "data" else (
        FocusArea.DASHBOARD if collection == "data" else FocusArea.ROSTER
    )
    panel = ContentPanel.INSPECTOR if focus is FocusArea.INSPECTOR else ContentPanel.ROSTER
    state = Workspace(collection, query=query, focus=focus, content_panel=panel)
    if not catalog.can_browse(collection):
        raise ValueError("学生账户无权执行管理操作")
    while True:
        try:
            with keys._mouse_tracking():
                event = interact(state, catalog)
            if event is None:
                return
            if event[0] == "field-edit":
                try:
                    edit_current(state, catalog)
                except KeyboardInterrupt:
                    cancel_field_session(state, "已取消输入。")
            elif event[0] == "search":
                try:
                    read_search(state, catalog)
                except KeyboardInterrupt:
                    state.notice = "已取消输入。"
            elif event[0] == "save":
                form = state.form
                mode = form.mode if form is not None else ""
                deleting_id = (
                    int(form.original["id"])
                    if state.key == "students"
                    and form is not None
                    and form.mode == "delete"
                    and form.original is not None
                    else None
                )
                deleting_position = state.selected if deleting_id is not None else None

                if deleting_id is not None:
                    # Burn owns the selected roster row while the record still
                    # exists. Confirmation then commits the deletion underneath it.
                    play_student_roster_effect(state, catalog, deleting_id, "burn")

                created_id = apply_form(state, catalog)
                if state.key == "students" and mode == "delete" and deleting_position is not None:
                    # Keep the exact deleted slot empty. No neighboring student
                    # becomes current until the user explicitly presses up/down.
                    rows = state.rows(catalog)
                    state.leave_roster_gap(min(deleting_position, len(rows)))
                elif state.key == "students" and mode == "create" and created_id is not None:
                    # apply_form has already converted the draft into the normal
                    # inspector and left focus there. Print only introduces the
                    # new row at its real sorted position on the left.
                    play_student_roster_effect(state, catalog, created_id, "print")
            elif event[0] == "refresh":
                row = state.current(catalog)
                catalog.refresh()
                if state.roster_gap is None:
                    state.selected = next(
                        (i for i, record in enumerate(state.rows(catalog)) if row and record["id"] == row["id"]),
                        0,
                    )
                else:
                    state.rows(catalog)
                state.notice = "已刷新。"
        except KeyboardInterrupt:
            if state.field_session is not None:
                cancel_field_session(state, "已取消输入。")
            elif state.form:
                state.form = None
                state.notice = "已取消操作，记录保持原样。"
            else:
                return
        except (ValueError, sqlite3.Error, OSError) as error:
            if state.field_session is not None:
                state.field_session = None
            state.notice = f"未完成：{error}"
