"""Workspace controller orchestration."""
from __future__ import annotations

from pathlib import Path
import sqlite3

from .. import keys
from .data import Catalog
from .events import (
    _detail_geometry,
    detail_targets as _detail_targets,
    interact as _interact,
    reveal_detail_selection as _reveal_detail_selection,
    select_visible_detail_target as _select_visible_detail_target,
)
from .forms import (
    apply_form as _apply_form,
    open_field as _open_field,
    open_form as _open_form,
    read_value as _read_value,
)
from .state import Form, Workspace


__all__ = ["Form", "Workspace", "run"]


def run(db_path: Path | str | None, collection: str) -> None:
    catalog, state = Catalog(db_path), Workspace(collection)
    while True:
        try:
            with keys._mouse_tracking():
                event = _interact(state, catalog)
            if event is None:
                return
            if event[0] in {"field", "search"}:
                try:
                    _read_value(state, catalog, event)
                except KeyboardInterrupt:
                    if state.form and state.form.mode == "edit":
                        state.form = None
                    state.notice = "已取消输入。"
            elif event[0] == "save":
                _apply_form(state, catalog)
            elif event[0] == "refresh":
                row = state.current(catalog)
                catalog.refresh()
                state.selected = next(
                    (i for i, record in enumerate(state.rows(catalog)) if row and record["id"] == row["id"]),
                    0,
                )
                state.notice = "已刷新。"
        except KeyboardInterrupt:
            if state.form:
                state.form = None
                state.notice = "已取消编辑，记录保持原样。"
            else:
                return
        except (ValueError, sqlite3.Error, OSError) as error:
            state.notice = f"未完成：{error}"
