from __future__ import annotations

from pathlib import Path

from ...database import DB_PATH
from .. import screen, theme
from ..layout import WorkspaceLayout
from ..view_common import Board, metric_summary
from .commands import FORM_SAVE, available as available_commands
from .dashboard import render_dashboard
from .data import ACADEMICS, COLLECTIONS, Catalog
from .detail import lines as generic_lines
from .editor import render_editor
from .inspector import (
    Line,
    action_targets,
    empty_inspector_width,
    layout_lines,
    render_inspector,
)
from .roster import render_roster as _roster
from .state import ContentPanel, FocusArea, Workspace
from .student_inspector import lines as student_lines


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
        # Transaction fields adapt internally between inline and stacked controls.
        return _RECORD_INSPECTOR_MIN_WIDTH

    row = state.current(catalog) if state.key != "data" else None
    if row is None:
        return empty_inspector_width(state, catalog)

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


def _footer(state: Workspace, catalog: Catalog, width: int) -> str:
    if state.field_session is not None:
        enter = "选择" if state.field_session.options is not None else "确认"
        return theme.footer(width, enter=enter, escape="取消")
    if state.form is not None:
        if state.form.mode == "delete":
            return theme.footer(width, enter="选择", escape="取消")
        if state.form.fields:
            return theme.footer(
                width,
                command_hints=("Tab 下一项", FORM_SAVE.hint),
                enter="编辑",
                escape="取消",
            )
        return theme.footer(width, enter="确认", escape="取消")
    hints = tuple(
        command.hint for command in available_commands(catalog, state.key)
        if command.shortcut
    )
    return theme.footer(width, items=hints)


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
        if state.form:
            _render_form_body(board, state, catalog, layout, width)
        elif state.key == "data":
            render_dashboard(board, state, catalog)
        else:
            _render_record_body(board, state, catalog, layout, width)
    else:
        x = 1
        if state.key == "data":
            metrics = [
                ("学生", str(len(catalog.records["students"]))),
                ("课程", str(len(catalog.records["courses"]))),
                ("选课", str(len(catalog.records["grades"]))),
            ]
            board.put(1, 2, metric_summary(metrics))
            choices = [
                (label, None, f"collection:{key}", False)
                for label, key in (("学生", "students"), ("课程", "courses"), ("成绩", "grades"), ("教务", "departments"))
            ]
            choice_row = 3
        elif state.key in ACADEMICS:
            choices = [
                (COLLECTIONS[key].noun, len(catalog.records[key]), f"collection:{key}", key == state.key)
                for key in ACADEMICS
            ]
            choice_row = 2
        else:
            choices = [
                (label, len(catalog.rows(state.key, i, state.query)), f"view:{i}", i == state.view)
                for i, label in enumerate(COLLECTIONS[state.key].views)
            ]
            choice_row = 2

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
