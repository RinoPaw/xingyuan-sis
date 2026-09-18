"""Workspace controller orchestration."""
from __future__ import annotations

from pathlib import Path
import sqlite3

from .. import keys
from ...auth import Identity
from .data import Catalog
from .events import interact
from .forms import apply_form, read_value
from .state import Form, Workspace


__all__ = ["Form", "Workspace", "run"]


def run(
    db_path: Path | str | None, collection: str, *, identity: Identity | None = None, query: str = "",
) -> None:
    catalog, state = Catalog(db_path, identity), Workspace(collection, query=query, details=bool(query))
    if not catalog.can_browse(collection):
        raise ValueError("学生账户无权执行管理操作")
    while True:
        try:
            with keys._mouse_tracking():
                event = interact(state, catalog)
            if event is None:
                return
            if event[0] in {"field", "search"}:
                try:
                    read_value(state, catalog, event)
                except KeyboardInterrupt:
                    if state.form and state.form.mode == "edit":
                        state.form = None
                    state.notice = "已取消输入。"
            elif event[0] == "save":
                apply_form(state, catalog)
                if state.credentials:
                    from ..viewer import show

                    text = "首次登录必须修改密码。请将初始密码交给对应学生。\n\n" + "\n".join(
                        f"学号  {no}\n初始密码  {password}\n" for no, password in state.credentials
                    )
                    try:
                        show(text, "学生 / 初始密码")
                    finally:
                        state.credentials.clear()
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
