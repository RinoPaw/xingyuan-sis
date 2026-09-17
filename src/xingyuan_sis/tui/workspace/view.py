from __future__ import annotations

from .. import screen, theme
from ..layout import WorkspaceLayout
from ..view_common import Board, metric_pair, metric_summary, safe
from .dashboard import render_dashboard
from .data import ACADEMICS, COLLECTIONS, Catalog
from .detail import (
    detail_targets as _generic_detail_targets,
    directional_target as _generic_directional_target,
    preferred_width as _generic_preferred_inspector_width,
    render_inspector as _generic_inspector,
)
from .editor import render_editor
from .roster import render_roster as _roster
from .state import Workspace
from .student_inspector import (
    detail_targets as _student_detail_targets,
    directional_target as _student_directional_target,
    preferred_width as _student_preferred_inspector_width,
    render_inspector as _student_inspector,
)


def detail_targets(key: str, row, catalog: Catalog, width: int):
    if key == "students":
        targets = _student_detail_targets(row, catalog, width)
        offset = WorkspaceLayout.measure().detail_offset
        return [(line, action) for line, action in targets if line >= offset]
    return _generic_detail_targets(key, row, catalog, width)


def directional_target(
    key: str,
    actions: list[str],
    selected: int,
    direction: str,
) -> int | None:
    """Delegate spatial navigation to the active inspector geometry."""
    if key == "students":
        return _student_directional_target(actions, selected, direction)
    return _generic_directional_target(actions, selected, direction)


def _preferred_inspector_width(key: str, row, catalog: Catalog) -> int:
    if key == "students":
        return _student_preferred_inspector_width(row, catalog)
    return _generic_preferred_inspector_width(key, row, catalog)


def _inspector(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    if state.key == "students":
        _student_inspector(board, state, catalog, x, width)
    else:
        _generic_inspector(board, state, catalog, x, width)


def _breadcrumb(state: Workspace) -> list[tuple[str, str]]:
    return [("首页", "navigate:"), (COLLECTIONS[state.key].title if state.key != "data" else "数据", "")]


def _render_actions(board: Board, state: Workspace, x: int, y: int, width: int) -> None:
    if state.key == "data":
        actions = (("导入", "import"), ("导出", "export"), ("演示", "seed"))
    else:
        actions = (("搜索", "search"), ("增加", "create"), ("编辑", "edit"), ("删除", "delete"))
    for index, (label, action) in enumerate(actions):
        shown = f" {label} "
        needed = screen._display_width(shown) + 4
        if needed > width:
            break
        x = board.button(x, y, shown, action, current=state.action_focus and state.action_selected == index)
        width -= needed


def render(state: Workspace, catalog: Catalog):
    terminal = screen._terminal_size()
    width, height = max(1, terminal.columns - 1), max(4, terminal.lines)
    current = state.current(catalog) if state.key != "data" else None
    inline_edit = current is not None and state.form is not None and state.form.mode == "edit"
    inspector_width = None
    if current is not None and (state.form is None or inline_edit):
        inspector_width = _preferred_inspector_width(state.key, current, catalog)
    layout = WorkspaceLayout(width, height, inspector_width)
    board = Board(width, height)
    board.put(0, 0, theme.topbar(width, database=catalog.service.db_path))

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
        _render_actions(board, state, 0, action_row, width)
        content_row = action_row + 1
        if state.form and not inline_edit:
            render_editor(board, state, catalog, layout.panel_x, layout.panel_width)
        elif current:
            _inspector(board, state, catalog, layout.panel_x, layout.panel_width)
        elif state.key == "data":
            for i, (label, key) in enumerate((("学生", "students"), ("课程", "courses"), ("选课", "grades"))):
                if content_row + i < height - 2:
                    board.put(0, content_row + i, metric_pair(label, len(catalog.records[key])), action=f"collection:{key}")

        board.rows[height - 2] = []
        board.put(0, height - 2,
                  theme.notice(safe(state.notice), error=state.notice.startswith("未完成：")) if state.notice else "",
                  width=width)
    else:
        action_row = layout.action_row
        if state.key == "data":
            noun = "校园概览"
            board.put(1, action_row, noun, screen._BOLD + screen._TEXT_ACCENT)
            action_x = max(15, screen._display_width(noun) + 5)
            _render_actions(board, state, action_x, action_row, max(0, width - action_x - 1))
        else:
            _render_actions(board, state, 1, action_row, max(0, width - 2))

        x = 1
        if state.key == "data":
            metrics = [("学生", str(len(catalog.records["students"]))),
                       ("课程", str(len(catalog.records["courses"]))),
                       ("选课", str(len(catalog.records["grades"])))]
            board.put(1, action_row + 1, metric_summary(metrics))
            choices = [(label, None, f"collection:{key}", False) for label, key in
                       (("学生", "students"), ("课程", "courses"), ("成绩", "grades"), ("教务", "departments"))]
            choice_row = action_row + 2
        elif state.key in ACADEMICS:
            choices = [(COLLECTIONS[key].noun, len(catalog.records[key]), f"collection:{key}", key == state.key)
                       for key in ACADEMICS]
            choice_row = action_row + 1
        else:
            choices = [(label, len(catalog.rows(state.key, i, state.query)), f"view:{i}", i == state.view)
                       for i, label in enumerate(COLLECTIONS[state.key].views)]
            choice_row = action_row + 1

        labels = theme.view_labels(width - 1, choices)
        for shown, (_, _, action, selected) in zip(labels, choices):
            if x + screen._display_width(shown) + 4 <= width:
                x = board.button(x, choice_row, shown, action, current=selected)

        separator_row = layout.separator_row(state.key)
        board.put(0, separator_row, "─" * width, screen._BORDER_SUBTLE)
        if state.key == "data" and not state.form:
            render_dashboard(board, state, catalog)
        else:
            split = layout.split_x if layout.split else width
            panel_heading_row = layout.panel_heading_row(state.key)
            if layout.split:
                if state.key != "data":
                    _roster(board, state, catalog, split - 1)
                for y in range(panel_heading_row, height - 2):
                    board.put(split, y, "│", screen._BORDER_SUBTLE)
            elif not state.details and not state.form:
                _roster(board, state, catalog, width - 1)
            x, panel_width = layout.panel_x, layout.panel_width
            if state.form and not inline_edit:
                render_editor(board, state, catalog, x, panel_width)
            elif layout.split or state.details or inline_edit:
                _inspector(board, state, catalog, x, panel_width)

        board.put(0, height - 2,
                  theme.notice(safe(state.notice), error=state.notice.startswith("未完成：")) if state.notice else "",
                  width=width)

    board.rows[-1] = [(0, theme.footer(width))]
    board.regions = [region for region in board.regions
                     if region.y < height and region.x + region.width - 1 <= width]
    return board.frame()
