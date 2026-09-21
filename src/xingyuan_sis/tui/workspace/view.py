from __future__ import annotations

from pathlib import Path

from ...database import DB_PATH
from .. import screen, theme
from ..layout import WorkspaceLayout
from ..view_common import Board, metric_summary
from .commands import FORM_SAVE, toolbar as toolbar_commands
from .dashboard import render_dashboard
from .data import ACADEMICS, COLLECTIONS, Catalog
from .detail import lines as generic_lines
from .editor import render_editor
from .inspector import Line, action_targets, layout_lines, render_inspector
from .roster import render_roster as _roster
from .state import ContentPanel, FocusArea, Workspace
from .student_inspector import lines as student_lines


_EMPTY_INSPECTOR_WIDTH = 18
_RECORD_INSPECTOR_MIN_WIDTH = 28
_RECORD_INSPECTOR_MAX_WIDTH = 42


def content_lines(key: str, row, catalog: Catalog, state: Workspace | None = None) -> list[Line]:
    return student_lines(row, catalog, state) if key == "students" else generic_lines(key, row, catalog, state)


def detail_lines(
    key: str,
    row,
    catalog: Catalog,
    width: int,
    state: Workspace | None = None,
) -> list[Line]:
    """Return the final geometry shared by rendering, target extraction and navigation."""
    return layout_lines(
        content_lines(key, row, catalog, state),
        width,
        WorkspaceLayout.measure(),
    )


def detail_targets(key: str, row, catalog: Catalog, width: int):
    return action_targets(detail_lines(key, row, catalog, width))


def _preferred_inspector_width(state: Workspace, catalog: Catalog) -> int:
    """Own the one semantic width decision for the right-hand workspace panel."""
    if state.form is not None:
        # Transaction fields already adapt internally between inline and stacked
        # controls. Give that editor its stable working width and let its own
        # geometry handle narrower terminals.
        return _RECORD_INSPECTOR_MIN_WIDTH

    row = state.current(catalog) if state.key != "data" else None
    if row is None:
        # Empty archive states contain only a heading and one short status line.
        return _EMPTY_INSPECTOR_WIDTH

    longest = max(
        screen._display_width("".join(text for text, _, _ in line))
        for line in content_lines(state.key, row, catalog)
    )
    return min(
        _RECORD_INSPECTOR_MAX_WIDTH,
        max(_RECORD_INSPECTOR_MIN_WIDTH, longest + 2),
    )


def workspace_layout(state: Workspace, catalog: Catalog) -> WorkspaceLayout:
    """Resolve semantic panel width once, then let WorkspaceLayout place it."""
    terminal = screen._terminal_size()
    return WorkspaceLayout(
        max(1, terminal.columns - 1),
        max(4, terminal.lines),
        _preferred_inspector_width(state, catalog),
    )


def _inspector(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    row = state.current(catalog)
    lines = content_lines(state.key, row, catalog, state) if row else []
    render_inspector(board, state, catalog, x, width, lines)


def _breadcrumb(state: Workspace) -> list[tuple[str, str]]:
    return [("首页", "navigate:"), (COLLECTIONS[state.key].title if state.key != "data" else "数据", "")]


def _render_actions(board: Board, state: Workspace, catalog: Catalog, x: int, y: int, width: int) -> None:
    commands = toolbar_commands(catalog, state.key)
    state.action_selected = min(max(0, state.action_selected), max(0, len(commands) - 1))
    first = 0
    if state.focus is FocusArea.TOOLBAR:
        while first < state.action_selected and sum(
            screen._display_width(command.label) + 6
            for command in commands[first:state.action_selected + 1]
        ) > width:
            first += 1
    for index in range(first, len(commands)):
        command = commands[index]
        shown = f" {command.label} "
        needed = screen._display_width(shown) + 4
        if needed > width:
            break
        x = board.button(
            x,
            y,
            shown,
            command.action,
            selected=state.focus is FocusArea.TOOLBAR and state.action_selected == index,
        )
        width -= needed


def _footer(state: Workspace, catalog: Catalog, width: int) -> str:
    if state.field_session is not None:
        enter = "选择" if state.field_session.options is not None else "确认"
        return theme.footer(width, enter=enter, escape="取消")
    if state.form is not None:
        if state.form.fields:
            return theme.footer(
                width,
                command_hints=("Tab 下一项", FORM_SAVE.hint),
                enter="编辑",
                escape="取消",
            )
        return theme.footer(width, enter="确认", escape="取消")
    hints = tuple(
        command.hint
        for command in toolbar_commands(catalog, state.key)
        if command.shortcut
    )
    return theme.footer(width, switch_focus=True, command_hints=hints)


def _split_divider(board: Board, state: Workspace, layout: WorkspaceLayout) -> None:
    split = layout.split_x
    panel_heading_row = layout.panel_heading_row(state.key)
    for y in range(panel_heading_row, board.height - 1):
        board.put(split, y, "│", screen._BORDER_SUBTLE)


def _render_record_body(
    board: Board,
    state: Workspace,
    catalog: Catalog,
    layout: WorkspaceLayout,
    width: int,
) -> None:
    if layout.split:
        split = layout.split_x
        _roster(board, state, catalog, split - 1)
        _split_divider(board, state, layout)
        _inspector(board, state, catalog, layout.panel_x, layout.panel_width)
        return

    if state.content_panel is ContentPanel.INSPECTOR or state.field_session is not None:
        _inspector(board, state, catalog, layout.panel_x, layout.panel_width)
    else:
        _roster(board, state, catalog, width - (0 if layout.compact else 1))


def _render_form_body(
    board: Board,
    state: Workspace,
    catalog: Catalog,
    layout: WorkspaceLayout,
    width: int,
) -> None:
    """Keep the record workspace intact while a transaction owns the inspector panel."""
    if state.key != "data" and layout.split:
        split = layout.split_x
        _roster(board, state, catalog, split - 1)
        _split_divider(board, state, layout)
        render_editor(board, state, catalog, layout.panel_x, layout.panel_width)
        return
    render_editor(board, state, catalog, layout.panel_x, layout.panel_width)


def render(state: Workspace, catalog: Catalog):
    layout = workspace_layout(state, catalog)
    width, height = layout.width, layout.height
    board = Board(width, height)
    board.put(0, 0, theme.topbar(width, database=Path(catalog.service.db_path or DB_PATH).name))

    x = 0
    for index, (label, action) in enumerate(_breadcrumb(state)):
        if index:
            separator = " / "
            board.put(x, 1, separator, screen._TEXT_SECONDARY)
            x += screen._display_width(separator)
        style = screen._TEXT_ACCENT + "\x1b[4m" if action else screen._TEXT_SECONDARY
        board.put(x, 1, label, style, action or None)
        x += screen._display_width(label)

    if layout.compact:
        action_row = layout.action_row
        _render_actions(board, state, catalog, 0, action_row, width)
        if state.form:
            _render_form_body(board, state, catalog, layout, width)
        elif state.key == "data":
            render_dashboard(board, state, catalog)
        else:
            _render_record_body(board, state, catalog, layout, width)
    else:
        action_row = layout.action_row
        if state.key == "data":
            noun = "校园概览"
            board.put(1, action_row, noun, screen._BOLD + screen._TEXT_ACCENT)
            action_x = max(15, screen._display_width(noun) + 5)
            _render_actions(board, state, catalog, action_x, action_row, max(0, width - action_x - 1))
        else:
            _render_actions(board, state, catalog, 1, action_row, max(0, width - 2))

        x = 1
        if state.key == "data":
            metrics = [
                ("学生", str(len(catalog.records["students"]))),
                ("课程", str(len(catalog.records["courses"]))),
                ("选课", str(len(catalog.records["grades"]))),
            ]
            board.put(1, action_row + 1, metric_summary(metrics))
            choices = [
                (label, None, f"collection:{key}", False)
                for label, key in (("学生", "students"), ("课程", "courses"), ("成绩", "grades"), ("教务", "departments"))
            ]
            choice_row = action_row + 2
        elif state.key in ACADEMICS:
            choices = [
                (COLLECTIONS[key].noun, len(catalog.records[key]), f"collection:{key}", key == state.key)
                for key in ACADEMICS
            ]
            choice_row = action_row + 1
        else:
            choices = [
                (label, len(catalog.rows(state.key, i, state.query)), f"view:{i}", i == state.view)
                for i, label in enumerate(COLLECTIONS[state.key].views)
            ]
            choice_row = action_row + 1

        labels = theme.view_labels(width - 1, choices)
        for shown, (_, _, action, selected) in zip(labels, choices):
            if x + screen._display_width(shown) + 4 <= width:
                x = board.button(x, choice_row, shown, action, current=selected)

        separator_row = layout.separator_row(state.key)
        board.put(0, separator_row, "─" * width, screen._BORDER_SUBTLE)
        if state.key == "data" and not state.form:
            render_dashboard(board, state, catalog)
        elif state.form:
            _render_form_body(board, state, catalog, layout, width)
        else:
            _render_record_body(board, state, catalog, layout, width)

    board.rows[-1] = [(0, _footer(state, catalog, width))]
    board.regions = [
        region for region in board.regions
        if region.y < height and region.x + region.width - 1 <= width
    ]
    return board.frame()
