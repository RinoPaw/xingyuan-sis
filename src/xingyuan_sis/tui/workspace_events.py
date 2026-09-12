from __future__ import annotations

from . import keys, screen
from .workspace_data import ACADEMICS, COLLECTIONS, Catalog
from .workspace_forms import open_form
from .workspace_state import Workspace


def _detail_geometry() -> tuple[int, int]:
    terminal = screen._terminal_size()
    width, height = max(1, terminal.columns - 1), max(4, terminal.lines)
    if width >= 76:
        split = width // 2
        panel_width = max(1, width - split - 4)
    else:
        panel_width = max(1, width - 2)
    return panel_width, max(1, height - 12)


def detail_targets(state: Workspace, catalog: Catalog) -> list[tuple[int, str]]:
    from .workspace_view import detail_targets as view_targets

    row = state.current(catalog)
    if row is None:
        return []
    width, _ = _detail_geometry()
    return view_targets(state.key, row, catalog, width)


def reveal_detail_selection(state: Workspace, catalog: Catalog) -> None:
    targets = detail_targets(state, catalog)
    if not targets:
        state.detail_selected = 0
        return
    state.detail_selected = min(max(0, state.detail_selected), len(targets) - 1)
    _, capacity = _detail_geometry()
    line = targets[state.detail_selected][0]
    if line < state.detail_scroll:
        state.detail_scroll = line
    elif line >= state.detail_scroll + capacity:
        state.detail_scroll = line - capacity + 1


def select_visible_detail_target(state: Workspace, catalog: Catalog) -> None:
    targets = detail_targets(state, catalog)
    if not targets:
        state.detail_selected = 0
        return
    _, capacity = _detail_geometry()
    first, last = state.detail_scroll, state.detail_scroll + capacity - 1
    visible = [(index, line) for index, (line, _) in enumerate(targets) if first <= line <= last]
    if visible:
        state.detail_selected = min(visible, key=lambda item: abs(item[0] - state.detail_selected))[0]
    else:
        state.detail_selected = min(
            range(len(targets)),
            key=lambda index: abs(targets[index][0] - first),
        )


def interact(state: Workspace, catalog: Catalog) -> tuple[str, int] | None:
    from .workspace_view import render

    previous: list[str] = []
    while True:
        frame = render(state, catalog)
        if frame.lines != previous:
            screen._paint(frame.lines, previous)
            previous = frame.lines
        key = keys._read_key(0.15)
        wheel = isinstance(key, keys.MouseScroll)
        wheel_over_details = False
        if wheel:
            if not state.form:
                wheel_over_details = any(
                    region.action == "focus-details" and region.y == key.y
                    and region.x <= key.x < region.x + region.width
                    for region in frame.regions
                )
            key = key.direction
        if isinstance(key, keys.MouseClick):
            key = screen._hit_action(key, frame.regions)
        if not key:
            continue

        if key in {"back", "cancel"}:
            if state.form and state.form.options is not None:
                state.form.options = None
            elif state.form:
                state.form = None
                state.notice = "已取消，记录保持原样。"
            elif state.details:
                state.details = False
                state.detail_scroll = 0
            elif state.history:
                state.key, state.view, state.query, state.selected, state.roster_scroll = state.history.pop()
                state.detail_scroll = 0
                state.detail_selected = 0
            else:
                return None
            continue

        if state.form:
            form = state.form
            if form.options is not None:
                if key in {"up", "down", "home", "end"}:
                    index = form.option_index + (-1 if key == "up" else 1)
                    if key == "home":
                        index = 0
                    elif key == "end":
                        index = len(form.options) - 1
                    form.option_index = min(max(0, index), max(0, len(form.options) - 1))
                elif key == "select" or key.startswith("option:"):
                    if form.options:
                        index = int(key.split(":")[1]) if key.startswith("option:") else form.option_index
                        form.values[form.fields[form.position].key] = form.options[index][0]
                        form.options = None
                        state.notice = "已选择，尚未保存。"
                continue
            if key == "save":
                return "save", 0
            if key == "select" and state.form.fields:
                return "field", state.form.position
            if key.startswith("field:"):
                state.form.position = int(key.split(":")[1])
                return "field", state.form.position
            if key in {"up", "down", "home", "end"}:
                position = state.form.position + (-1 if key == "up" else 1)
                if key == "home":
                    position = 0
                elif key == "end":
                    position = len(state.form.fields) - 1
                state.form.position = min(max(0, position), max(0, len(state.form.fields) - 1))
            continue

        if key.startswith("navigate:"):
            path = key.removeprefix("navigate:")
            if not path:
                raise screen.NavigateTo("")
            if path == "教务":
                state.switch("departments")
            continue
        if key.startswith("collection:"):
            state.history.clear()
            state.switch(key.split(":")[1])
        elif key.startswith("related:"):
            _, collection, identifier = key.split(":")
            state.history.append((state.key, state.view, state.query, state.selected, state.roster_scroll))
            state.switch(collection)
            state.selected = next(
                (i for i, row in enumerate(state.rows(catalog)) if str(row["id"]) == identifier),
                0,
            )
        elif key.startswith("row:"):
            state.selected = int(key.split(":")[1])
            state.detail_scroll = 0
            state.detail_selected = 0
            state.details = screen._terminal_size().columns < 76
        elif key.startswith("edit-field:"):
            open_form(state, catalog, "edit")
            field_key = key.split(":")[1]
            state.form.position = next(i for i, field in enumerate(state.form.fields) if field.key == field_key)
            return "field", state.form.position
        elif key == "right":
            if state.key != "data":
                state.details = True
                reveal_detail_selection(state, catalog)
        elif key == "left":
            if state.key != "data":
                state.details = False
        elif key == "focus-details":
            state.details = True
            reveal_detail_selection(state, catalog)
        elif key == "focus":
            state.details = not state.details
            if state.details:
                reveal_detail_selection(state, catalog)
        elif key == "select":
            if state.details and state.key != "data":
                targets = detail_targets(state, catalog)
                if targets:
                    state.detail_selected = min(max(0, state.detail_selected), len(targets) - 1)
                    key = targets[state.detail_selected][1]
                else:
                    continue
            else:
                state.details = not state.details
                if state.details:
                    reveal_detail_selection(state, catalog)
                continue
            if key.startswith("related:"):
                _, collection, identifier = key.split(":")
                state.history.append((state.key, state.view, state.query, state.selected, state.roster_scroll))
                state.switch(collection)
                state.selected = next(
                    (i for i, row in enumerate(state.rows(catalog)) if str(row["id"]) == identifier),
                    0,
                )
            elif key.startswith("edit-field:"):
                open_form(state, catalog, "edit")
                field_key = key.split(":")[1]
                state.form.position = next(i for i, field in enumerate(state.form.fields) if field.key == field_key)
                return "field", state.form.position
        elif key in {"up", "down", "page_up", "page_down", "home", "end"}:
            amount = max(1, screen._terminal_size().lines - 11) if key.startswith("page_") else 1
            amount *= -1 if key in {"up", "page_up"} else 1
            if wheel and state.key != "data":
                if wheel_over_details:
                    state.detail_scroll = max(0, state.detail_scroll + amount)
                    if state.details:
                        select_visible_detail_target(state, catalog)
                else:
                    state.selected += amount
                    state.detail_scroll = 0
                    state.detail_selected = 0
            elif state.details and state.key != "data":
                targets = detail_targets(state, catalog)
                if key in {"page_up", "page_down"} or not targets:
                    state.detail_scroll = max(0, state.detail_scroll + amount)
                    select_visible_detail_target(state, catalog)
                else:
                    if key == "home":
                        state.detail_selected = 0
                    elif key == "end":
                        state.detail_selected = len(targets) - 1
                    else:
                        state.detail_selected += -1 if key == "up" else 1
                    state.detail_selected = min(max(0, state.detail_selected), len(targets) - 1)
                    reveal_detail_selection(state, catalog)
            elif state.key == "data":
                state.detail_scroll = max(0, state.detail_scroll + amount)
                if key == "home":
                    state.detail_scroll = 0
                elif key == "end":
                    state.detail_scroll = 10**6
            else:
                state.selected += amount
                if key == "home":
                    state.selected = 0
                elif key == "end":
                    state.selected = len(state.rows(catalog)) - 1
                state.detail_scroll = 0
                state.detail_selected = 0
        elif key.startswith("view:") or key in {"1", "2", "3", "4"}:
            index = int(key.split(":")[1]) if key.startswith("view:") else int(key) - 1
            if state.key == "data":
                state.switch(("students", "courses", "grades", "departments")[index])
            elif state.key in ACADEMICS and index < len(ACADEMICS):
                state.switch(ACADEMICS[index])
            elif state.key != "data" and index < len(COLLECTIONS[state.key].views):
                state.view, state.selected, state.roster_scroll = index, 0, 0
                state.detail_scroll, state.detail_selected = 0, 0
        elif key == "search" and state.key != "data":
            return "search", 0
        elif key == "reset-search":
            state.query, state.selected, state.roster_scroll = "", 0, 0
            state.detail_scroll, state.detail_selected = 0, 0
        elif key == "refresh":
            return "refresh", 0
        elif key in {"create", "edit", "delete"} and state.key != "data":
            open_form(state, catalog, key)
        elif key in {"import", "export", "seed"}:
            open_form(state, catalog, key)
