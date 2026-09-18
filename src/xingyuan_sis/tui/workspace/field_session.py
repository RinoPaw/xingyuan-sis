"""Local editing sessions for fields inside an existing record inspector."""
from __future__ import annotations

from ...terminal_input import input_style, read_inline_input
from .. import screen
from .data import Catalog
from .presentation import project_record
from .state import FieldSession, FocusArea, Workspace


def start(state: Workspace, catalog: Catalog, field_key: str) -> None:
    """Attach a local field session to an existing stable inspector target."""
    if catalog.read_only:
        raise ValueError("当前档案为只读。")
    row = state.current(catalog)
    if row is None:
        raise ValueError("先选择一条记录。")

    fields = catalog.edit_group(state.key, field_key)
    if not fields:
        raise ValueError("该字段为只读。")
    if field_key == "age":
        from ...schema import is_complete_birth_date

        if is_complete_birth_date(row.get("birth_date")):
            raise ValueError("完整出生日期已自动计算年龄，请修改出生日期。")

    state.field_session = FieldSession(
        fields=fields,
        values={field.key: row.get(field.key) for field in fields},
        original=row,
        anchor_key=field_key,
    )
    state.form = None
    state.set_focus(FocusArea.INSPECTOR)
    state.notice = "Enter 确认并保存 · Esc 取消。"


def cancel(state: Workspace, message: str = "已取消本次字段修改。") -> None:
    state.field_session = None
    state.notice = message


def projected_values(state: Workspace, catalog: Catalog | None = None) -> dict:
    session = state.field_session
    if session is None:
        return {}
    values = project_record(session.original, session)
    return catalog.project(state.key, values) if catalog is not None else values


def _open_options(state: Workspace, catalog: Catalog) -> bool:
    session = state.field_session
    if session is None:
        return False
    options = catalog.options(state.key, session.active_key, projected_values(state, catalog))
    if options is None:
        session.options = None
        return False
    session.options = options
    session.option_index = next(
        (i for i, (value, _) in enumerate(options)
         if value == session.values.get(session.active_key)),
        0,
    )
    suffix = "继续" if session.active + 1 < len(session.fields) else "保存"
    state.notice = f"↑↓ 选择，Enter {suffix} · Esc 取消。"
    return True


def _field_geometry(frame: screen.ScreenFrame, field_key: str) -> tuple[int, int, int]:
    region = next(region for region in frame.regions if region.action == f"field:{field_key}")
    return region.y, region.x, max(1, region.width)


def edit_current(state: Workspace, catalog: Catalog) -> None:
    """Open the active field in place; free-form confirmation saves immediately."""
    session = state.field_session
    if session is None:
        return
    if _open_options(state, catalog):
        return

    from .view import render

    field = session.field
    current = session.values.get(field.key)
    state.notice = (
        "直接在当前字段修改 · Enter 保存"
        + (" · 清空后 Enter 可置空" if not field.required else "")
        + " · Esc 取消"
    )
    frame = render(state, catalog)
    screen._paint(frame.lines)
    row, column, width = _field_geometry(frame, field.key)
    with input_style(True):
        raw = read_inline_input(
            f"{field.label} > ",
            row=row,
            column=column,
            width=width,
            initial_value="" if current is None else str(current),
        ).strip()

    session.values[field.key] = field.parse(raw if raw else None)
    commit(state, catalog)


def accept_option(state: Workspace, catalog: Catalog, index: int) -> None:
    """Accept an option inside the same field session and save when complete."""
    session = state.field_session
    if session is None or session.options is None or not session.options:
        return

    field = session.field
    session.values[field.key] = session.options[index][0]
    session.options = None

    if session.active + 1 < len(session.fields):
        next_field = session.fields[session.active + 1]
        next_options = catalog.options(state.key, next_field.key, projected_values(state, catalog))
        if next_options is not None and not any(
            value == session.values.get(next_field.key) for value, _ in next_options
        ):
            session.values[next_field.key] = None
        session.active += 1
        if not _open_options(state, catalog):
            state.notice = "Enter 确认并保存 · Esc 取消。"
        return

    commit(state, catalog)


def commit(state: Workspace, catalog: Catalog) -> None:
    """Atomically save the current field group and return to its stable target."""
    session = state.field_session
    if session is None:
        return

    focus_key = session.active_key
    record_id = catalog.save(
        state.key,
        {field.key: session.values.get(field.key) for field in session.fields},
        session.original,
    )
    state.field_session = None
    rows = state.rows(catalog)
    state.selected = next((i for i, row in enumerate(rows) if row["id"] == record_id), state.selected)
    state.notice = (
        "已保存。"
        if any(row["id"] == record_id for row in rows)
        else "已保存；这条记录不符合当前筛选条件。"
    )

    if any(row["id"] == record_id for row in rows):
        state.set_focus(FocusArea.INSPECTOR)
        from .events import detail_targets

        action = f"field:{focus_key}"
        state.detail_selected = next(
            (i for i, (_, target) in enumerate(detail_targets(state, catalog)) if target == action),
            0,
        )
    else:
        state.set_focus(FocusArea.ROSTER)
        state.detail_scroll, state.detail_selected = 0, 0
