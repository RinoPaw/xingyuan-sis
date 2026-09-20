"""Shared local field editing for existing records and transaction drafts."""
from __future__ import annotations

import sys

from ...terminal_input import editing_cursor, input_style, read_inline_input
from .. import screen
from ..text_edit import input_mode, read_event
from .birth_date_editor import BIRTH_DATE_FIELDS, BIRTH_DATE_KEYS, canonical as birth_canonical
from .birth_date_editor import options as birth_options, parts as birth_parts, projected as projected_birth_date
from .data import COLLECTIONS, Catalog
from .presentation import project_record
from .state import FieldSession, FieldSessionOwner, FocusArea, Workspace


_BIRTH_SLOT_WIDTHS = {
    "birth_year": 4,
    "birth_month": 2,
    "birth_day": 2,
}


def _related_anchor(anchor_key: str) -> tuple[str, str, str] | None:
    """Return collection, record id and real field for an inline related-record target."""
    if not anchor_key.startswith("related:"):
        return None
    parts = anchor_key.split(":", 3)
    if len(parts) != 4:
        return None
    _, collection, identifier, field_key = parts
    return collection, identifier, field_key


def _session_collection(state: Workspace, session: FieldSession) -> str:
    related = _related_anchor(session.anchor_key)
    return related[0] if related else state.key


def _session_action(session: FieldSession) -> str:
    """Return the exact rendered target owned by the current field session."""
    return (
        f"field:{session.anchor_key}"
        if _related_anchor(session.anchor_key)
        else f"field:{session.active_key}"
    )


def _is_birth_session(state: Workspace, session: FieldSession | None = None) -> bool:
    session = state.field_session if session is None else session
    return (
        session is not None
        and _session_collection(state, session) == "students"
        and session.anchor_key == "birth_date"
        and tuple(field.key for field in session.fields) == BIRTH_DATE_KEYS
    )


def _session_values(
    collection: str,
    field_key: str,
    source: dict,
    fields: tuple,
) -> dict:
    if collection == "students" and field_key == "birth_date":
        return birth_parts(source.get("birth_date"))
    return {field.key: source.get(field.key) for field in fields}


def _session_changes(state: Workspace, session: FieldSession) -> dict:
    if _is_birth_session(state, session):
        return {"birth_date": birth_canonical(session.values)}
    return {field.key: session.values.get(field.key) for field in session.fields}


def start(state: Workspace, catalog: Catalog, field_key: str) -> None:
    """Attach a FieldSession to one stable field target in an existing record."""
    if catalog.read_only:
        raise ValueError("当前档案为只读。")

    related = _related_anchor(field_key)
    if related:
        collection, identifier, real_field_key = related
        row = next(
            (row for row in catalog.records.get(collection, ()) if str(row["id"]) == identifier),
            None,
        )
        if row is None:
            raise ValueError("关联记录已经不存在。")
        fields = catalog.edit_group(collection, real_field_key)
        if not fields:
            raise ValueError("该字段为只读。")
        state.field_session = FieldSession(
            fields=fields,
            values=_session_values(collection, real_field_key, row, fields),
            original=dict(row),
            anchor_key=field_key,
            owner=FieldSessionOwner.RECORD,
        )
        state.form = None
        state.set_focus(FocusArea.INSPECTOR)
        state.notice = ""
        return

    row = state.current(catalog)
    if row is None:
        raise ValueError("先选择一条记录。")

    fields = BIRTH_DATE_FIELDS if state.key == "students" and field_key == "birth_date" else catalog.edit_group(
        state.key, field_key
    )
    if not fields:
        raise ValueError("该字段为只读。")
    if field_key == "age":
        from ...schema import is_complete_birth_date

        if is_complete_birth_date(row.get("birth_date")):
            raise ValueError("完整出生日期已自动计算年龄，请修改出生日期。")

    state.field_session = FieldSession(
        fields=fields,
        values=_session_values(state.key, field_key, row, fields),
        original=dict(row),
        anchor_key=field_key,
        owner=FieldSessionOwner.RECORD,
    )
    state.form = None
    state.set_focus(FocusArea.INSPECTOR)
    state.notice = ""


def start_form(state: Workspace, catalog: Catalog, index: int | None = None) -> None:
    """Edit one selected Form field through the same FieldSession state machine."""
    form = state.form
    if form is None or not form.fields:
        raise ValueError("当前事务没有可编辑字段。")
    if index is not None:
        form.position = min(max(0, index), len(form.fields) - 1)

    field = form.fields[form.position]
    group = ()
    if form.mode == "create" and state.key in COLLECTIONS:
        group = (
            BIRTH_DATE_FIELDS
            if state.key == "students" and field.key == "birth_date"
            else catalog.field_group(state.key, field.key)
        )
    fields = group or (field,)

    state.field_session = FieldSession(
        fields=fields,
        values=_session_values(state.key, field.key, form.values, fields),
        original=dict(form.values),
        anchor_key=field.key,
        owner=FieldSessionOwner.FORM,
    )
    state.set_focus(FocusArea.INSPECTOR)
    state.notice = ""


def cancel(state: Workspace, message: str = "已取消本字段编辑。") -> None:
    """Discard one local edit without touching its record or Form draft."""
    state.field_session = None
    state.notice = message


def projected_values(state: Workspace, catalog: Catalog | None = None) -> dict:
    session = state.field_session
    if session is None:
        return {}
    values = project_record(session.original, session)
    if _is_birth_session(state, session):
        values["birth_date"] = projected_birth_date(session.values)
    collection = _session_collection(state, session)
    if catalog is not None and collection in COLLECTIONS:
        return catalog.project(collection, values)
    return values


def _open_options(state: Workspace, catalog: Catalog) -> bool:
    session = state.field_session
    if session is None:
        return False

    if _is_birth_session(state, session):
        values = projected_values(state, catalog)
        values.update(session.values)
        options = birth_options(session.active_key, values)
        if options is not None:
            if not any(value == session.values.get(session.active_key) for value, _ in options):
                session.values[session.active_key] = None
            session.options = options
            session.option_index = next(
                (i for i, (value, _) in enumerate(options)
                 if value == session.values.get(session.active_key)),
                0,
            )
            state.notice = ""
            return True

    collection = _session_collection(state, session)
    if collection not in COLLECTIONS:
        session.options = None
        return False

    values = projected_values(state, catalog)
    options = catalog.normalize_option_value(collection, session.active_key, values)
    if options is None:
        session.options = None
        return False
    if session.active_key in session.values:
        session.values[session.active_key] = values.get(session.active_key)
    session.options = options
    session.option_index = next(
        (i for i, (value, _) in enumerate(options)
         if value == session.values.get(session.active_key)),
        0,
    )
    state.notice = ""
    return True


def _field_geometry(frame: screen.ScreenFrame, action: str) -> tuple[int, int, int]:
    """Return the actual field region, not the selection marker sharing its action."""
    regions = [region for region in frame.regions if region.action == action]
    if not regions:
        raise ValueError(f"找不到字段位置：{action}")
    region = max(regions, key=lambda candidate: (candidate.x, candidate.width))
    return region.y, region.x, max(1, region.width)


def _birth_raw_values(session: FieldSession) -> dict[str, str]:
    return {
        key: "" if session.values.get(key) is None else str(session.values.get(key))
        for key in BIRTH_DATE_KEYS
    }


def _sync_birth_raw(session: FieldSession, raw: dict[str, str]) -> None:
    session.values.update({key: value if value else None for key, value in raw.items()})


def _parsed_birth_values(raw: dict[str, str]) -> dict[str, int | None]:
    return {
        key: (int(value) if value else None)
        for key, value in raw.items()
    }


def _position_birth_cursor(frame: screen.ScreenFrame, session: FieldSession, raw: dict[str, str], replace: bool) -> None:
    action = f"field:{session.active_key}"
    row, column, region_width = _field_geometry(frame, action)
    width = min(region_width, _BIRTH_SLOT_WIDTHS[session.active_key])
    text_width = screen._display_width(raw[session.active_key])
    offset = 0 if replace else min(text_width, max(0, width - 1))
    sys.stdout.write(f"\x1b[{row};{column + offset}H")
    sys.stdout.flush()


def _edit_birth_date(state: Workspace, catalog: Catalog) -> None:
    """Edit year/month/day as one masked control with three independent slots."""
    session = state.field_session
    if session is None:
        return

    from .view import render

    raw = _birth_raw_values(session)
    replace = True

    def redraw() -> None:
        _sync_birth_raw(session, raw)
        frame = render(state, catalog)
        screen._paint(frame.lines)
        _position_birth_cursor(frame, session, raw, replace)

    state.notice = ""
    redraw()
    with input_mode(), editing_cursor():
        while True:
            event = read_event(None)
            if event is None:
                continue
            kind = event.kind

            if kind == "cancel":
                raise KeyboardInterrupt
            if kind == "submit":
                parsed = _parsed_birth_values(raw)
                try:
                    birth_canonical(parsed)
                except (TypeError, ValueError):
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                    continue
                session.values.update(parsed)
                commit(state, catalog)
                return

            if kind in {"left", "right", "home", "end", "tab"}:
                if kind == "left":
                    session.active = max(0, session.active - 1)
                elif kind in {"right", "tab"}:
                    session.active = min(len(session.fields) - 1, session.active + 1)
                elif kind == "home":
                    session.active = 0
                else:
                    session.active = len(session.fields) - 1
                replace = True
                redraw()
                continue

            key = session.active_key
            before = raw[key]
            if kind == "insert":
                digits = "".join(char for char in event.text if char.isdigit())
                if not digits:
                    continue
                width = _BIRTH_SLOT_WIDTHS[key]
                base = "" if replace else raw[key]
                raw[key] = (base + digits)[:width]
                replace = False
            elif kind in {"backspace", "delete", "clear"}:
                if kind == "backspace" and not replace:
                    raw[key] = raw[key][:-1]
                else:
                    raw[key] = ""
                replace = False
            else:
                continue

            if key == "birth_month" and not raw[key]:
                raw["birth_day"] = ""
            if raw[key] != before or key == "birth_month":
                redraw()


def edit_current(state: Workspace, catalog: Catalog) -> None:
    """Open the active field in place; Enter confirms the local FieldSession."""
    session = state.field_session
    if session is None:
        return
    if _is_birth_session(state, session):
        _edit_birth_date(state, catalog)
        return
    if _open_options(state, catalog):
        return

    from .view import render

    field = session.field
    current = session.values.get(field.key)
    state.notice = ""
    frame = render(state, catalog)
    screen._paint(frame.lines)
    row, column, width = _field_geometry(frame, _session_action(session))
    with input_style(True):
        raw = read_inline_input(
            f"{field.label} > ",
            row=row,
            column=column,
            width=width,
            initial_value="" if current is None else str(current),
        ).strip()

    session.values[field.key] = field.parse(raw if raw else None)
    if session.active + 1 < len(session.fields):
        session.active += 1
        if session.owner is FieldSessionOwner.FORM and state.form is not None:
            state.form.position = next(
                (i for i, candidate in enumerate(state.form.fields)
                 if candidate.key == session.active_key),
                state.form.position,
            )
        if not _open_options(state, catalog):
            edit_current(state, catalog)
        return
    commit(state, catalog)


def accept_option(state: Workspace, catalog: Catalog, index: int) -> bool:
    """Confirm one option; return True only when the next group field needs text input."""
    session = state.field_session
    if session is None or session.options is None or not session.options:
        return False

    field = session.field
    session.values[field.key] = session.options[index][0]
    session.options = None

    if _is_birth_session(state, session) and field.key == "birth_month" and session.values[field.key] is None:
        session.values["birth_day"] = None
        commit(state, catalog)
        return False

    if session.active + 1 < len(session.fields):
        session.active += 1
        if session.owner is FieldSessionOwner.FORM and state.form is not None:
            state.form.position = next(
                (i for i, candidate in enumerate(state.form.fields)
                 if candidate.key == session.active_key),
                state.form.position,
            )
        return not _open_options(state, catalog)

    commit(state, catalog)
    return False


def commit(state: Workspace, catalog: Catalog) -> None:
    """Confirm the local field group to its Form draft or existing record."""
    session = state.field_session
    if session is None:
        return

    focus_key = session.anchor_key if _is_birth_session(state, session) else session.active_key
    changes = _session_changes(state, session)
    if session.owner is FieldSessionOwner.FORM:
        form = state.form
        if form is None:
            raise ValueError("字段所属事务已经结束。")
        form.values.update(changes)
        form.position = next(
            (i for i, field in enumerate(form.fields) if field.key == session.anchor_key),
            form.position,
        )
        state.field_session = None
        state.notice = ""
        return

    collection = _session_collection(state, session)
    record_id = catalog.save(collection, changes, session.original)
    state.field_session = None

    if collection != state.key:
        state.notice = "已保存。"
        state.set_focus(FocusArea.INSPECTOR)
        from .events import detail_targets

        action = f"field:{session.anchor_key}"
        state.detail_selected = next(
            (i for i, (_, target) in enumerate(detail_targets(state, catalog)) if target == action),
            state.detail_selected,
        )
        return

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
