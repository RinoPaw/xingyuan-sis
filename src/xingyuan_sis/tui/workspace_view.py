from __future__ import annotations

from . import screen, theme
from .layout import WorkspaceLayout
from .view_common import Board, metric_pair, metric_summary, safe
from .workspace_dashboard import render_dashboard
from .workspace_data import ACADEMICS, COLLECTIONS, Catalog
from .workspace_detail import detail_targets, details as _details, render_inspector as _inspector
from .workspace_editor import render_editor
from .workspace_roster import render_roster as _roster
from .workspace_state import Workspace


def _breadcrumb(state: Workspace) -> list[tuple[str, str]]:
    return [("首页", "navigate:首页"), (COLLECTIONS[state.key].title if state.key != "data" else "数据", "")]


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
    layout = WorkspaceLayout(width, height)
    board = Board(width, height)
    board.put(0, 0, theme.topbar(width, catalog.db_path))

    x = 0
    for index, (label, action) in enumerate(_breadcrumb(state)):
        if index:
            x = board.put(x, 1, " / ", screen._TEXT_SECONDARY)
        style = screen._TEXT_ACCENT + "\x1b[4m" if action else screen._TEXT_SECONDARY
        x = board.put(x, 1, label, style, action or None)

    if layout.compact:
        action_row = layout.action_row
        if state.key == "data":
            _render_actions(board, state, 0, action_row, width)
            content_row = action_row + 1
        else:
            _render_actions(board, state, 0, action_row, width)
            content_row = action_row + 1
        if state.form:
            form = state.form
            board.put(0, content_row, form.title, screen._BOLD + screen._TEXT_ACCENT)
            content_row += 1
            if form.options is not None:
                for i, (_, label) in enumerate(form.options[:max(1, height - content_row - 2)]):
                    board.button(0, content_row + i, label, f"option:{i}", current=i == form.option_index)
            elif form.fields:
                field = form.fields[form.position]
                field_line = (screen._ansi(field.label, screen._TEXT_SECONDARY) + "  "
                              + screen._ansi(safe(form.values.get(field.key)), screen._TEXT_PRIMARY))
                board.put(0, content_row, field_line, action=f"field:{form.position}")
            else:
                board.put(0, content_row, "确认执行？  Esc 取消", screen._BOLD + screen._TEXT_PRIMARY)
        elif state.current(catalog):
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
            if state.form:
                render_editor(board, state, catalog, x, panel_width)
            elif layout.split or state.details:
                _inspector(board, state, catalog, x, panel_width)

        board.put(0, height - 2,
                  theme.notice(safe(state.notice), error=state.notice.startswith("未完成：")) if state.notice else "",
                  width=width)

    board.rows[-1] = [(0, theme.footer(width))]
    board.regions = [region for region in board.regions
                     if region.y < height and region.x + region.width - 1 <= width]
    return board.frame()
