from __future__ import annotations

from . import keys, screen
from .layout import WorkspaceLayout
from .workspace_data import ACADEMICS, COLLECTIONS, Catalog
from .workspace_forms import open_form
from .workspace_state import Workspace


_RECORD_ACTIONS = ("search", "create", "edit", "delete")
_DATA_ACTIONS = ("import", "export", "seed")


def _actions(state: Workspace) -> tuple[str, ...]:
    return _DATA_ACTIONS if state.key == "data" else _RECORD_ACTIONS


def _detail_geometry(state: Workspace) -> tuple[int, int]:
    layout = WorkspaceLayout.measure()
    return layout.panel_width, layout.panel_capacity(state.key)


def detail_targets(state: Workspace, catalog: Catalog) -> list[tuple[int, str]]:
    from .workspace_view import detail_targets as view_targets

    row = state.current(catalog)
    if row is None:
        return []
    layout = WorkspaceLayout.measure()
    return [(line - layout.detail_offset, action)
            for line, action in view_targets(state.key, row, catalog, layout.panel_width)]


def reveal_detail_selection(state: Workspace, catalog: Catalog) -> None:
    targets = detail_targets(state, catalog)
    if not targets:
        state.detail_selected = 0
        return
    state.detail_selected = min(max(0, state.detail_selected), len(targets) - 1)
    _, capacity = _detail_geometry(state)
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
    _, capacity = _detail_geometry(state)
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

        actions = _actions(state)
        if state.action_focus and not state.form:
            if key == "left":
                state.action_selected = max(0, state.action_selected - 1)
                continue
            if key == "right":
                state.action_selected = min(len(actions) - 1, state.action_selected + 1)
                continue
            if key == "home":
                state.action_selected = 0
                continue
            if key == "end":
                state.action_selected = len(actions) - 1
                continue
            if key == "up":
                continue
            if key == "down":
                state.action_focus = False
                continue
            if key == "select":
                key = actions[state.action_selected]

        if key in {"back", "cancel"}:
            if state.form and state.form.options is not None:
                state.form.options = None
            elif state.form:
                state.form = None
                state.notice = "已取消，记录保持原样。"
            elif state.details:
                state.details = False
                state.detail_scroll = 0
            elif state.action_focus:
                if state.history:
                    state.restore(catalog)
                else:
                    return None
            elif state.key != "data":
                # Esc first moves from the roster into the page action bar.
                # The selected record remains unchanged and is rendered as
                # weak context while the action bar owns keyboard focus.
                state.action_focus = True
            elif state.history:
                state.restore(catalog)
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
            raise screen.NavigateTo(key.removeprefix("navigate:"))
        if key.startswith("collection:"):
            state.history.clear()
            state.switch(key.split(":")[1])
        elif key.startswith("related:"):
            _, collection, identifier = key.split(":")
            state.visit(collection, identifier, catalog)
        elif key.startswith("row:"):
            state.action_focus = False
            state.selected = int(key.split(":")[1])
            state.detail_scroll = 0
            state.detail_selected = 0
            state.details = not WorkspaceLayout.measure().split
        elif key.startswith("edit-field:"):
            state.action_focus = False
            open_form(state, catalog, "edit")
            field_key = key.split(":")[1]
            state.form.position = next(i for i, field in enumerate(state.form.fields) if field.key == field_key)
            return "field", state.form.position
        elif key == "right":
            if state.key != "data":
                state.action_focus = False
                state.details = True
                reveal_detail_selection(state, catalog)
        elif key == "left":
            if state.key != "data":
                state.action_focus = False
                state.details = False
        elif key == "focus-details":
            state.action_focus = False
            state.details = True
            reveal_detail_selection(state, catalog)
        elif key == "focus":
            state.action_focus = False
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
                state.visit(collection, identifier, catalog)
            elif key.startswith("edit-field:"):
                open_form(state, catalog, "edit")
                field_key = key.split(":")[1]
                state.form.position = next(i for i, field in enumerate(state.form.fields) if field.key == field_key)
                return "field", state.form.position
        elif key in {"up", "down", "page_up", "page_down", "home", "end"}:
            if not state.details and key == "up":
                if state.key == "data" and state.detail_scroll == 0:
                    state.action_focus = True
                    continue
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
            state.action_focus = False
            index = int(key.split(":")[1]) if key.startswith("view:") else int(key) - 1
            if state.key == "data":
                state.switch(("students", "courses", "grades", "departments")[index])
            elif state.key in ACADEMICS and index < len(ACADEMICS):
                state.switch(ACADEMICS[index])
            elif state.key != "data" and index < len(COLLECTIONS[state.key].views):
                state.view, state.selected, state.roster_scroll = index, 0, 0
                state.detail_scroll, state.detail_selected = 0, 0
        elif key == "search" and state.key != "data":
            state.action_focus = False
            return "search", 0
        elif key == "reset-search":
            state.query, state.selected, state.roster_scroll = "", 0, 0
            state.detail_scroll, state.detail_selected = 0, 0
        elif key == "refresh":
            return "refresh", 0
        elif key in _RECORD_ACTIONS and state.key != "data":
            state.action_focus = False
            open_form(state, catalog, key)
        elif key in _DATA_ACTIONS and state.key == "data":
            state.action_focus = False
            open_form(state, catalog, key)
