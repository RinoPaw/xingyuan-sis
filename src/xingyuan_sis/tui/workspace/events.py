from __future__ import annotations

from .. import keys, screen
from ..commands import resolve_shortcut
from ..layout import WorkspaceLayout
from .commands import FORM_SAVE, available as available_commands, toolbar as toolbar_commands
from .data import ACADEMICS, COLLECTIONS, Catalog
from .field_session import accept_option as accept_field_option, cancel as cancel_field_session, start as start_field_session
from .forms import accept_option as accept_form_option, move_form_position, open_form
from .state import Workspace


def _detail_geometry(state: Workspace, catalog: Catalog) -> tuple[int, int]:
    from .view import workspace_layout

    layout = workspace_layout(state, catalog)
    return layout.panel_width, layout.panel_capacity(state.key)


def detail_targets(state: Workspace, catalog: Catalog) -> list[tuple[int, str]]:
    from .view import detail_targets as view_targets, workspace_layout

    row = state.current(catalog)
    if row is None:
        return []
    layout = workspace_layout(state, catalog)
    return view_targets(state.key, row, catalog, layout.panel_width)


def reveal_detail_selection(state: Workspace, catalog: Catalog) -> None:
    targets = detail_targets(state, catalog)
    if not targets:
        state.detail_selected = 0
        return
    state.detail_selected = min(max(0, state.detail_selected), len(targets) - 1)
    _, capacity = _detail_geometry(state, catalog)
    line = targets[state.detail_selected][0]
    if line < state.detail_scroll:
        state.detail_scroll = line
    elif line >= state.detail_scroll + capacity:
        state.detail_scroll = line - capacity + 1


def select_visible_detail_target(state: Workspace, catalog: Catalog) -> None:
    from .view import detail_lines, workspace_layout

    row = state.current(catalog)
    if row is None:
        state.detail_selected = -1
        return
    layout = workspace_layout(state, catalog)
    lines = detail_lines(state.key, row, catalog, layout.panel_width)
    capacity = layout.panel_capacity(state.key)
    state.detail_scroll = min(max(0, state.detail_scroll), max(0, len(lines) - capacity))
    targets = detail_targets(state, catalog)
    if not targets:
        state.detail_selected = -1
        return
    first, last = state.detail_scroll, state.detail_scroll + capacity - 1
    visible = [(index, line) for index, (line, _) in enumerate(targets) if first <= line <= last]
    if visible:
        state.detail_selected = min(visible, key=lambda item: abs(item[0] - state.detail_selected))[0]
    else:
        state.detail_selected = -1


def move_detail_selection(state: Workspace, catalog: Catalog, direction: str) -> None:
    from .inspector import directional_target
    from .view import detail_lines, workspace_layout

    targets = detail_targets(state, catalog)
    if not targets or state.detail_selected < 0:
        if direction == "left":
            state.details = False
        return
    actions = [action for _, action in targets]
    current = actions[min(state.detail_selected, len(actions) - 1)]
    row = state.current(catalog)
    layout = workspace_layout(state, catalog)
    target = directional_target(
        detail_lines(state.key, row, catalog, layout.panel_width),
        current,
        direction,
    )
    if target is None:
        if direction == "left":
            state.details = False
        return
    state.detail_selected = actions.index(target)
    reveal_detail_selection(state, catalog)


def _page_roster(state: Workspace, catalog: Catalog, direction: str) -> None:
    rows = state.rows(catalog)
    if not rows:
        return
    capacity = WorkspaceLayout.measure().panel_capacity(state.key)
    maximum = max(0, len(rows) - capacity)
    delta = capacity if direction == "page_down" else -capacity
    first = min(max(0, state.roster_scroll + delta), maximum)
    state.roster_scroll = first
    last = min(len(rows) - 1, first + capacity - 1)
    state.selected = min(max(state.selected, first), last)
    state.detail_scroll = 0
    state.detail_selected = 0


def _page_detail(state: Workspace, catalog: Catalog, direction: str) -> None:
    _, capacity = _detail_geometry(state, catalog)
    state.detail_scroll = max(
        0,
        state.detail_scroll + (capacity if direction == "page_down" else -capacity),
    )
    select_visible_detail_target(state, catalog)


def _activate_detail_action(
    state: Workspace,
    catalog: Catalog,
    action: str,
) -> tuple[bool, tuple[str, int] | None]:
    """Activate a stable inspector target without page-specific field knowledge."""
    if action.startswith("related:"):
        _, collection, identifier = action.split(":")
        state.visit(collection, identifier, catalog)
        return True, None

    if not action.startswith("field:"):
        return False, None

    field_key = action.removeprefix("field:")
    targets = detail_targets(state, catalog)
    actions = [target for _, target in targets]
    if action in actions:
        state.detail_selected = actions.index(action)
    state.action_focus = False
    state.details = True
    reveal_detail_selection(state, catalog)

    if catalog.read_only:
        state.notice = "当前档案为只读。"
        return True, None
    editable = {field.key for field in catalog.fields(state.key, True)}
    if field_key not in editable:
        state.notice = "该字段为只读。"
        return True, None

    start_field_session(state, catalog, field_key)
    return True, ("field-edit", 0)


def interact(state: Workspace, catalog: Catalog) -> tuple[str, int] | None:
    from .view import render

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
            if state.form is None and state.field_session is None:
                wheel_over_details = any(
                    region.action == "focus-details"
                    and region.y == key.y
                    and region.x <= key.x < region.x + region.width
                    for region in frame.regions
                )
            key = key.direction
        if isinstance(key, screen.MouseClick):
            key = screen._hit_action(key, frame.regions)
        if not key:
            continue

        commands = available_commands(catalog, state.key)
        if state.form is None and state.field_session is None:
            key = resolve_shortcut(key, commands)
        elif state.form is not None and state.form.fields:
            key = resolve_shortcut(key, (FORM_SAVE,))

        if key in {"focus", "focus_prev"} and state.form is None and state.field_session is None:
            areas = (
                ("roster", "details", "actions")
                if state.key != "data" and state.current(catalog)
                else ("roster", "actions")
            )
            current_area = "actions" if state.action_focus else "details" if state.details else "roster"
            if current_area not in areas:
                current_area = "roster"
            area = areas[(areas.index(current_area) + (1 if key == "focus" else -1)) % len(areas)]
            state.action_focus, state.details = area == "actions", area == "details"
            if state.details:
                reveal_detail_selection(state, catalog)
            continue

        toolbar = toolbar_commands(catalog, state.key)
        toolbar_actions = tuple(command.action for command in toolbar)
        if state.action_focus and state.form is None and state.field_session is None:
            if key == "left":
                state.action_selected = max(0, state.action_selected - 1)
                continue
            if key == "right":
                state.action_selected = min(len(toolbar_actions) - 1, state.action_selected + 1)
                continue
            if key == "home":
                state.action_selected = 0
                continue
            if key == "end":
                state.action_selected = max(0, len(toolbar_actions) - 1)
                continue
            if key == "up":
                continue
            if key == "down":
                state.action_focus = False
                continue
            if key == "select" and toolbar_actions:
                key = toolbar_actions[state.action_selected]

        if key == "back":
            if state.field_session is not None:
                cancel_field_session(state)
            elif state.form and state.form.options is not None:
                state.form.options = None
            elif state.form:
                state.form = None
                state.notice = "已取消，记录保持原样。"
            elif state.details:
                state.details = False
                state.detail_scroll = 0
            elif state.action_focus:
                state.action_focus = False
            elif state.history:
                state.restore(catalog)
            else:
                return None
            continue

        if state.field_session is not None:
            session = state.field_session
            if session.options is not None:
                if key in {"up", "down", "home", "end"}:
                    index = session.option_index + (-1 if key == "up" else 1)
                    if key == "home":
                        index = 0
                    elif key == "end":
                        index = len(session.options) - 1
                    session.option_index = min(max(0, index), max(0, len(session.options) - 1))
                elif key == "select" or (isinstance(key, str) and key.startswith("option:")):
                    if session.options:
                        index = int(key.split(":")[1]) if key.startswith("option:") else session.option_index
                        accept_field_option(state, catalog, index)
                continue
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
                elif key == "select" or (isinstance(key, str) and key.startswith("option:")):
                    if form.options:
                        index = int(key.split(":")[1]) if key.startswith("option:") else form.option_index
                        accept_form_option(state, index)
                continue
            if key == "save" or (key == "select" and (form.focus_save or not form.fields)):
                return "save", 0
            if key == "select" and form.fields:
                return "field", form.position
            if isinstance(key, str) and key.startswith("field:"):
                form.position = int(key.split(":")[1])
                form.focus_save = False
                return "field", form.position
            if key in {"up", "down", "left", "right", "home", "end", "focus", "focus_prev"}:
                move_form_position(state, key)
            continue

        if isinstance(key, str) and key.startswith(("collection:", "related:")) \
                and not catalog.can_browse(key.split(":")[1]):
            continue

        handled, event = _activate_detail_action(state, catalog, key)
        if handled:
            if event is not None:
                return event
            continue

        if isinstance(key, str) and key.startswith("navigate:"):
            raise screen.NavigateTo(key.removeprefix("navigate:"))
        if isinstance(key, str) and key.startswith("collection:"):
            state.history.clear()
            state.switch(key.split(":")[1])
        elif isinstance(key, str) and key.startswith("row:"):
            state.action_focus = False
            state.selected = int(key.split(":")[1])
            state.detail_scroll = 0
            state.detail_selected = 0
            state.details = not WorkspaceLayout.measure().split
        elif key == "right":
            if state.details and state.key != "data":
                move_detail_selection(state, catalog, "right")
            elif state.key != "data":
                state.action_focus = False
                state.details = True
                state.detail_selected = 0
                reveal_detail_selection(state, catalog)
        elif key == "left":
            if state.key != "data":
                state.action_focus = False
                move_detail_selection(state, catalog, "left")
        elif key == "focus-details":
            state.action_focus = False
            state.details = True
            reveal_detail_selection(state, catalog)
        elif key == "select":
            if state.details and state.key != "data":
                targets = detail_targets(state, catalog)
                if targets and state.detail_selected >= 0:
                    state.detail_selected = min(max(0, state.detail_selected), len(targets) - 1)
                    target = targets[state.detail_selected][1]
                    handled, event = _activate_detail_action(state, catalog, target)
                    if handled:
                        if event is not None:
                            return event
                        continue
                continue
            state.details = not state.details
            if state.details:
                state.detail_selected = 0
                reveal_detail_selection(state, catalog)
            continue
        elif key in {"page_up", "page_down"}:
            if state.details and state.key != "data":
                _page_detail(state, catalog, key)
            elif state.key == "data":
                capacity = WorkspaceLayout.measure().panel_capacity(state.key)
                state.detail_scroll = max(
                    0,
                    state.detail_scroll + (capacity if key == "page_down" else -capacity),
                )
            else:
                _page_roster(state, catalog, key)
        elif key in {"up", "down", "home", "end"}:
            if not state.details and key == "up" and not wheel:
                if ((state.key == "data" and state.detail_scroll == 0)
                        or (state.key != "data" and state.selected == 0)):
                    state.action_focus = True
                    continue
            amount = -1 if key == "up" else 1
            if wheel and state.key != "data":
                if wheel_over_details:
                    if state.details and state.detail_selected >= 0:
                        move_detail_selection(state, catalog, key)
                    else:
                        state.detail_scroll = max(0, state.detail_scroll + amount)
                    if state.details and state.detail_selected < 0:
                        select_visible_detail_target(state, catalog)
                else:
                    state.selected += amount
                    state.detail_scroll = 0
                    state.detail_selected = 0
            elif state.details and state.key != "data":
                targets = detail_targets(state, catalog)
                if (not targets
                        or (catalog.read_only and key in {"home", "end"})
                        or (state.detail_selected < 0 and key not in {"home", "end"})):
                    state.detail_scroll = max(0, state.detail_scroll + amount)
                    if key == "home":
                        state.detail_scroll = 0
                    elif key == "end":
                        state.detail_scroll = 10**6
                    select_visible_detail_target(state, catalog)
                else:
                    if key == "home":
                        state.detail_selected = 0
                    elif key == "end":
                        state.detail_selected = len(targets) - 1
                    else:
                        move_detail_selection(state, catalog, key)
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
        elif (isinstance(key, str) and key.startswith("view:")) or key in {"1", "2", "3", "4"}:
            state.action_focus = False
            index = int(key.split(":")[1]) if key.startswith("view:") else int(key) - 1
            if state.key == "data":
                state.switch(("students", "courses", "grades", "departments")[index])
            elif state.key in ACADEMICS and index < len(ACADEMICS):
                state.switch(ACADEMICS[index])
            elif state.key != "data" and index < len(COLLECTIONS[state.key].views):
                state.view, state.selected, state.roster_scroll = index, 0, 0
                state.detail_scroll, state.detail_selected = 0, 0
        elif key == "search" and "search" in {command.action for command in commands}:
            state.action_focus = False
            return "search", 0
        elif key == "reset-search":
            state.query, state.selected, state.roster_scroll = "", 0, 0
            state.detail_scroll, state.detail_selected = 0, 0
        elif key == "refresh":
            return "refresh", 0
        elif key in {"create", "delete", "reset-password", "import", "export", "seed"}:
            if key not in {command.action for command in commands}:
                continue
            state.action_focus = False
            open_form(state, catalog, key)
