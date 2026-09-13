"""Responsive workspace layout composition."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from . import screen, theme
from .layout import WorkspaceLayout
from .view_common import Board, identity, metric_pair, metric_summary, safe
from .workspace_dashboard import render_dashboard
from .workspace_data import ACADEMICS, COLLECTIONS, Catalog
from .workspace_detail import detail_targets, details, render_inspector
from .workspace_editor import render_editor
from .workspace_roster import render_roster

if TYPE_CHECKING:
    from .workspace import Workspace


_details = details
_inspector = render_inspector
_roster = render_roster

_RECORD_ACTIONS = (("搜索", "search"), ("增加", "create"), ("编辑", "edit"), ("删除", "delete"))
_DATA_ACTIONS = (("导入", "import"), ("导出", "export"), ("演示", "seed"))


def _render_actions(board: Board, state: Workspace, x: int, y: int, available: int) -> None:
    if state.form or available <= 0:
        return
    actions = _DATA_ACTIONS if state.key == "data" else _RECORD_ACTIONS
    state.action_selected = min(max(0, state.action_selected), len(actions) - 1)
    right = x + available
    for index, (label, action) in enumerate(actions):
        shown = theme.button(label, selected=state.action_focus and index == state.action_selected)
        width = screen._display_width(shown)
        if x + width > right:
            break
        board.put(x, y, shown, action=action)
        x += width + 2


def render(state: Workspace, catalog: Catalog) -> screen.ScreenFrame:
    layout = WorkspaceLayout.measure()
    width, height = layout.width, layout.height
    board = Board(width, height)
    title = COLLECTIONS[state.key].title if state.key != "data" else "数据"

    database = Path(catalog.service.db_path).name if catalog.service.db_path else "xingyuan.db"
    board.put(0, 0, theme.topbar(width, database=database))
    breadcrumb, regions = screen._breadcrumb(title, width)
    board.put(0, 1, breadcrumb)
    board.regions.extend(regions)

    if layout.compact:
        if not state.form:
            _render_actions(board, state, 0, layout.action_row, width)
        row = state.current(catalog)
        heading_row = layout.panel_heading_row(state.key)
        content_row = layout.panel_content_row(state.key)
        board.put(0, heading_row, safe(identity(state.key, row)[0]) if row else title,
                  screen._BOLD + screen._TEXT_ACCENT, action="focus" if row else "")
        if state.form:
            form = state.form
            if form.options is not None:
                if form.options:
                    board.put(0, content_row, safe(form.options[form.option_index][1]), action=f"option:{form.option_index}")
                else:
                    board.put(0, content_row, "暂无可选记录，请先创建。", screen._TEXT_SECONDARY)
            elif form.fields:
                field = form.fields[form.position]
                field_line = (screen._ansi(field.label, screen._TEXT_SECONDARY) + "  "
                              + screen._ansi(safe(form.values.get(field.key)), screen._TEXT_PRIMARY))
                board.put(0, content_row, field_line, action=f"field:{form.position}")
            else:
                board.put(0, content_row, "确认执行？  Esc 取消", screen._BOLD + screen._TEXT_PRIMARY)
        elif row:
            board.rows[heading_row] = []
            board.regions = [region for region in board.regions if region.y != heading_row + 1]
            render_inspector(board, state, catalog, layout.panel_x, layout.panel_width)
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
            split = width // 2 if layout.split else width
            panel_heading_row = layout.panel_heading_row(state.key)
            if layout.split:
                if state.key != "data":
                    render_roster(board, state, catalog, split - 1)
                for y in range(panel_heading_row, height - 2):
                    board.put(split, y, "│", screen._BORDER_SUBTLE)
            elif not state.details and not state.form:
                render_roster(board, state, catalog, width - 1)
            x, panel_width = layout.panel_x, layout.panel_width
            if state.form:
                render_editor(board, state, catalog, x, panel_width)
            elif layout.split or state.details:
                render_inspector(board, state, catalog, x, panel_width)

        board.put(0, height - 2,
                  theme.notice(safe(state.notice), error=state.notice.startswith("未完成：")) if state.notice else "",
                  width=width)

    board.rows[-1] = [(0, theme.footer(width))]
    board.regions = [region for region in board.regions
                     if region.y < height and region.x + region.width - 1 <= width]
    return board.frame()
