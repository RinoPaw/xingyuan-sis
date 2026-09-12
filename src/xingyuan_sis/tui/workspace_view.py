"""Responsive roster, record inspector, editor and campus dashboard."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import screen, theme
from .workspace_data import ACADEMICS, COLLECTIONS, Catalog
from ..terminal_ui import _wrap_line

if TYPE_CHECKING:
    from .workspace import Workspace


_TEAL = "\x1b[38;5;109m"


def safe(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return " ".join("".join(char for char in str(value) if char.isprintable() or char == "\n").split())


class Board:
    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        self.rows: list[list[tuple[int, str]]] = [[] for _ in range(height)]
        self.regions: list[screen.HitRegion] = []

    def put(self, x: int, y: int, text: str, style: str = "", action: str = "", width: int | None = None) -> None:
        if not (0 <= y < self.height and 0 <= x < self.width):
            return
        text = screen._clip_cells(text, min(width if width is not None else self.width - x, self.width - x))
        if style:
            text = screen._ansi(text, style)
        self.rows[y].append((x, text))
        if action and text:
            self.regions.append(screen.HitRegion(x + 1, y + 1, screen._display_width(text), action))

    def button(self, x: int, y: int, label: str, action: str, *, selected: bool = False) -> int:
        text = theme.button(label, selected=selected)
        self.put(x, y, text, action=action)
        return x + screen._display_width(text) + 1

    def frame(self) -> screen.ScreenFrame:
        lines = []
        for parts in self.rows:
            text = ""
            for x, part in sorted(parts, key=lambda part: part[0]):
                text = screen._pad_cells(text, x) + part
            lines.append(screen._pad_cells(screen._clip_cells(text, self.width), self.width))
        return screen.ScreenFrame(lines, self.regions)


def _identity(key: str, row: dict[str, Any]) -> tuple[str, str]:
    if key == "grades":
        return safe(row["student_name"]), f"{safe(row['course_name'])} · {safe(row['semester'])}"
    identifier = row.get("student_no", row.get("course_code", row.get("code")))
    return safe(row["name"]), safe(identifier)


def _details(key: str, row: dict[str, Any], catalog: Catalog, width: int) -> list[tuple[str, str, str]]:
    title, identifier = _identity(key, row)
    lines = [(title, screen._BOLD + screen._ACCENT, ""), (identifier, screen._DIM, ""), ("", "", "")]
    if key == "students":
        lines.append((f"{safe(row['primary_element'])} · {safe(row['primary_affinity'])}  /  {safe(row['status'])}", _TEAL, ""))
        lines.append((safe(row["class_name"]) + " · " + safe(row["department_name"]), screen._DIM, ""))
    if key == "courses":
        lines.append((f"{safe(row['credits'])} 学分  /  {row['hours']} 课时  /  {row['enrolled']} 次选课", _TEAL, ""))
    if key == "grades":
        score = row["score"]
        lines.append(("待录入成绩" if score is None else f"{score:g} / 100", screen._GOLD if score is None else _TEAL, "edit-field:score"))
        if score is not None:
            size = min(30, max(1, width - 2))
            filled = round(score / 100 * size)
            lines.append(("━" * filled + "·" * (size - filled), _TEAL, "edit-field:score"))
    related_key, related = catalog.related(key, row)
    lines.extend([("", "", ""), (f"关联{COLLECTIONS[related_key].noun}  {len(related):02d}", screen._BOLD + _TEAL, "")])
    if not related:
        lines.append(("暂无关联记录", screen._DIM, ""))
    for item in related:
        if related_key == "grades":
            label = item["course_name"] if key == "students" else item["student_name"]
            label = f"{label}  ·  {safe(item['score']) if item['score'] is not None else '待录入'}"
        else:
            label = item["name"]
        lines.append(("↗ " + safe(label), screen._ACCENT + "\x1b[4m", f"related:{related_key}:{item['id']}"))
    lines.extend([("", "", ""), ("档案字段  ·  点击编辑", screen._BOLD + _TEAL, "")])
    editable = {f.key for f in catalog.fields(key, True)}
    for field in COLLECTIONS[key].fields:
        action = f"edit-field:{field.key}" if field.key in editable else ""
        prefix = screen._pad_cells(field.label, 10)
        value = safe(row.get(field.key))
        # Wrap long fields instead of silently losing contacts or notes.
        chunks = _wrap_line(value, max(2, width - 12))
        lines.append((prefix + "  " + chunks[0], "", action))
        lines.extend((" " * 12 + part, "", action) for part in chunks[1:])
    return lines


def _inspector(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    top, bottom = 9, board.height - 2
    board.put(x, 8, "档案 / " + ("阅读中" if state.details else "即时预览"), _TEAL, action="focus", width=width)
    row = state.current(catalog)
    if row is None:
        if state.query or state.view:
            board.put(x, top + 1, "当前条件下没有记录", screen._ACCENT, width=width)
            board.put(x, top + 3, "清除搜索或切换上方视图。", screen._DIM, width=width)
            if state.query:
                board.button(x, top + 5, "清除搜索", "reset-search")
            return
        board.put(x, top + 1, "从第一份档案开始", screen._BOLD + screen._ACCENT, width=width)
        board.put(x, top + 3, "新建记录后，名册与档案会在这里展开。", screen._DIM, width=width)
        board.button(x, top + 5, "a 新建", "create")
        if not any(catalog.records.values()):
            board.button(x, top + 7, "体验演示校园", "seed")
        return
    lines = _details(state.key, row, catalog, width)
    capacity = max(1, bottom - top - 1)
    state.detail_scroll = min(state.detail_scroll, max(0, len(lines) - capacity))
    for index, (text, style, action) in enumerate(lines[state.detail_scroll:state.detail_scroll + capacity]):
        board.put(x, top + index, text, style, action, width)
    if len(lines) > capacity:
        board.put(x, bottom - 1, f"{state.detail_scroll + 1}–{min(len(lines), state.detail_scroll + capacity)} / {len(lines)}  ·  Tab 切换区域后滚动", screen._DIM, action="focus", width=width)
    # These fallback hit regions also identify the panel under the mouse wheel.
    board.regions.extend(screen.HitRegion(x + 1, y + 1, width, "focus-details") for y in range(top, bottom))


def _editor(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    form = state.form
    if form.options is not None:
        board.put(x, 8, "选择 / " + form.fields[form.position].label, screen._BOLD + screen._ACCENT, width=width)
        capacity = max(1, board.height - 13)
        first = min(max(0, form.option_index - capacity + 1), max(0, len(form.options) - capacity))
        for i, (_, label) in enumerate(form.options[first:first + capacity], start=first):
            text = screen._pad_cells(screen._clip_cells(safe(label), width), width)
            board.put(x, 10 + i - first, text, screen._SELECTED if i == form.option_index else "", f"option:{i}", width)
        if not form.options:
            board.put(x, 10, "暂无可选记录，请先创建。", screen._DIM, width=width)
        return
    titles = {"create": "新建档案", "edit": "编辑档案", "delete": "删除记录", "import": "导入学生 CSV",
              "export": "导出学生 CSV", "seed": "建立演示校园"}
    board.put(x, 8, titles[form.mode], screen._BOLD + screen._ACCENT, width=width)
    if form.mode in {"delete", "seed"}:
        messages = ["将写入一组完整的演示数据。", "仅支持空数据库，已有记录会保留。"]
        if form.mode == "delete":
            title, identifier = _identity(state.key, form.original)
            messages = [f"确认删除 {title}？", identifier, "删除后无法撤销。"]
            if state.key in {"students", "courses"}:
                _, related = catalog.related(state.key, form.original)
                messages.append(f"同时移除 {len(related)} 条关联选课。")
        for index, message in enumerate(messages):
            board.put(x, 10 + index * 2, message, screen._GOLD, width=width)
    else:
        board.put(x, 9, "* 必填  ·  更改暂存，保存后生效", screen._DIM, width=width)
        capacity = max(1, board.height - 15)
        first = min(max(0, form.position - capacity + 1), max(0, len(form.fields) - capacity))
        for i, field in enumerate(form.fields[first:first + capacity], start=first):
            mark = "›" if i == form.position else " "
            label = f"{mark} {field.label}{'*' if field.required else ''}  {safe(form.values.get(field.key))}"
            text = screen._pad_cells(screen._clip_cells(label, width), width)
            board.put(x, 11 + i - first, text, screen._SELECTED if i == form.position else "", f"field:{i}", width)
        if len(form.fields) > capacity:
            board.put(x, board.height - 4, f"字段 {form.position + 1}/{len(form.fields)}  ·  ↑↓ 切换", screen._DIM, width=width)
    board.put(x, board.height - 3, "s 保存 / 确认   ·   q 取消", _TEAL, width=width)


def _roster(board: Board, state: Workspace, catalog: Catalog, width: int) -> None:
    rows = state.rows(catalog)
    capacity = max(1, board.height - 12)
    first = min(max(0, state.selected - capacity + 1), max(0, len(rows) - capacity))
    board.put(1, 8, f"名册  {len(rows):02d}  " + (f"/  {first + 1}–{min(first + capacity, len(rows))}" if rows else ""),
              screen._ACCENT if not state.details else screen._DIM, width=width - 1)
    columns = []
    available = width - 2
    for key, label, size in COLLECTIONS[state.key].columns:
        size = min(size, available) if not columns else size
        if size > available:
            break
        columns.append((key, label, size))
        available -= size + 1
    if columns and available > 0:
        key, label, size = columns[-1]
        columns[-1] = key, label, size + available
    header = " ".join(screen._pad_cells(label, size) for _, label, size in columns)
    board.put(1, 9, header, screen._DIM, width=width - 1)
    for index, row in enumerate(rows[first:first + capacity], start=first):
        text = " ".join(screen._pad_cells(screen._clip_cells(safe(row.get(key)), size), size) for key, _, size in columns)
        text = screen._pad_cells(screen._clip_cells(text, width - 1), width - 1)
        board.put(1, 10 + index - first, text, screen._SELECTED if index == state.selected else "", f"row:{index}", width - 1)
    if not rows:
        board.put(1, 11, "没有匹配的记录" if state.query or state.view else "名册还是空白的", screen._ACCENT, width=width - 1)
        if state.query or state.view:
            board.put(1, 13, "切换视图或清除搜索条件。", screen._DIM, width=width - 1)
        else:
            board.button(1, 13, "a 新建", "create")
            if state.key == "students":
                board.button(1, 15, "导入学生 CSV", "import")
            if not any(catalog.records.values()):
                board.button(1, 17, "体验演示校园", "seed")


def _dashboard(board: Board, state: Workspace, catalog: Catalog) -> None:
    width = board.width
    split = width // 2 if width >= 76 else width
    lines: list[tuple[str, str, str]] = []
    lines.append(("校园脉络 / 学生元素分布", screen._BOLD + _TEAL, ""))
    distribution = catalog.distribution()
    maximum = max((count for _, count in distribution), default=1)
    for label, count in distribution:
        bar = "━" * max(1, round(count / maximum * max(1, split - 20)))
        lines.append((f"{safe(label):<4} {bar} {count}", screen._ACCENT, "collection:students"))
    if not distribution:
        lines.extend([("", "", ""), ("校园尚未建立第一份学生档案。", screen._DIM, ""),
                      ("[ 导入学生 CSV ]", screen._ACCENT, "import"),
                      ("[ 体验演示校园 ]", screen._ACCENT, "seed")])
    lines.extend([("", "", ""), ("班级 / 学生人数", screen._BOLD + _TEAL, "")])
    for row in catalog.records["classes"]:
        lines.append((f"{safe(row['name'])}  {row['enrolled']} 人", "", f"related:classes:{row['id']}"))
    grades = catalog.records["grades"]
    scores = [r["score"] for r in grades if r["score"] is not None]
    right = [("成绩进度", screen._BOLD + _TEAL, ""), ("", "", ""),
             (f"已录入 {len(scores)} / {len(grades)}", screen._ACCENT, "collection:grades")]
    right.extend((f"{label}  {sum(low <= score < high for score in scores)}", "", "collection:grades")
                 for label, low, high in (("90–100", 90, 101), ("80–89", 80, 90), ("60–79", 60, 80), ("60 以下", 0, 60)))
    right.extend([("", "", ""), ("导入记录", screen._BOLD + _TEAL, "")])
    report_width = max(2, width - split - 3 if width >= 76 else width - 2)
    right.extend((part, screen._GOLD, "") for line in state.report or ["本次还没有导入错误。"]
                 for part in _wrap_line(safe(line), report_width))
    if width < 76:
        lines.extend([("", "", ""), *right])
        panels = [(1, width - 2, lines)]
    else:
        panels = [(1, split - 3, lines), (split + 2, width - split - 3, right)]
    capacity = max(1, board.height - 11)
    state.detail_scroll = min(state.detail_scroll, max(0, max(len(panel[2]) for panel in panels) - capacity))
    for x, panel_width, content in panels:
        for index, (text, style, action) in enumerate(content[state.detail_scroll:state.detail_scroll + capacity]):
            board.put(x, 9 + index, text, style, action, panel_width)


def render(state: Workspace, catalog: Catalog) -> screen.ScreenFrame:
    terminal = screen._terminal_size()
    width, height = max(1, terminal.columns - 1), max(4, terminal.lines)
    board = Board(width, height)
    title = COLLECTIONS[state.key].title if state.key != "data" else "数据"
    board.put(0, 0, theme.topbar(width))
    breadcrumb, regions = screen._breadcrumb(title, width)
    board.put(0, 1, breadcrumb)
    board.regions.extend(regions)
    if height < 20 or width < 24:
        # Keep record navigation usable while an IME or resize leaves little room.
        row = state.current(catalog)
        board.put(0, 3, safe(_identity(state.key, row)[0]) if row else title, screen._ACCENT,
                  action="focus" if row else "")
        if state.form:
            form = state.form
            if form.options is not None:
                if form.options:
                    board.put(0, 4, safe(form.options[form.option_index][1]), action=f"option:{form.option_index}")
                else:
                    board.put(0, 4, "暂无可选记录，请先创建。", screen._DIM)
            elif form.fields:
                f = form.fields[form.position]
                board.put(0, 4, f.label + "  " + safe(form.values.get(f.key)), action=f"field:{form.position}")
            else:
                board.put(0, 4, "确认执行？s 确认 / q 取消", screen._GOLD)
        elif row:
            content = _details(state.key, row, catalog, width)[1:]
            capacity = max(1, height - 6)
            state.detail_scroll = min(state.detail_scroll, max(0, len(content) - capacity))
            for i, (text, style, action) in enumerate(content[state.detail_scroll:state.detail_scroll + capacity]):
                board.put(0, 4 + i, text, style, action, width)
        elif state.key == "data":
            for i, (label, key) in enumerate((("学生", "students"), ("课程", "courses"), ("选课", "grades"))):
                if 4 + i < height - 2:
                    board.put(0, 4 + i, f"{len(catalog.records[key])} {label}", _TEAL, f"collection:{key}")
        board.rows[height - 2] = []
        board.put(0, height - 2, screen._clip_cells(safe(state.notice) if state.notice else "", width), screen._DIM)
        buttons = (("s 保存", "s", "save"), ("q 取消", "q", "cancel")) if state.form else (
            ("↑↓ 浏览", "↑↓", "down"), ("a 新建", "a", "create"), ("e 编辑", "e", "edit"), ("q 返回", "q", "back"))
        if state.key == "data" and not state.form:
            buttons = (("i 导入", "i", "import"), ("o 导出", "o", "export"),
                       ("g 演示", "g", "seed"), ("q 返回", "q", "back"))
    else:
        noun = COLLECTIONS[state.key].noun if state.key != "data" else "校园概览"
        board.put(1, 3, noun, screen._BOLD + screen._ACCENT)
        metrics = catalog.metrics(state.key)
        if state.key == "data":
            metrics = [("学生", str(len(catalog.records["students"]))), ("课程", str(len(catalog.records["courses"]))),
                       ("选课", str(len(catalog.records["grades"])))]
        board.put(1, 4, "    ".join(value + " " + label for label, value in metrics), _TEAL)
        x = 1
        choices = [(COLLECTIONS[k].noun, f"collection:{k}", k == state.key) for k in ACADEMICS] if state.key in ACADEMICS else (
            [(label, f"collection:{key}", False) for label, key in (("学生", "students"), ("课程", "courses"), ("成绩", "grades"), ("教务", "departments"))]
            if state.key == "data" else [(label, f"view:{i}", i == state.view) for i, label in enumerate(COLLECTIONS[state.key].views)])
        for i, (label, action, selected) in enumerate(choices):
            shown = f"{i + 1} {label}" if width >= 48 else label
            if x + screen._display_width(shown) + 4 <= width:
                x = board.button(x, 5, shown, action, selected=selected)
        if state.key != "data":
            text = f"/ {safe(state.query)}" if state.query else "/ 搜索姓名、编号、班级…"
            board.put(1, 6, text, screen._DIM, "search", max(1, width - 12))
            if state.query and width >= 40:
                board.put(width - 10, 6, "[ 清除 ]", screen._ACCENT, "reset-search")
        board.put(0, 7, "─" * width, screen._DIM)
        if state.key == "data" and not state.form:
            _dashboard(board, state, catalog)
        else:
            split = width // 2 if width >= 76 else width
            if width >= 76:
                if state.key != "data":
                    _roster(board, state, catalog, split - 1)
                for y in range(8, height - 2):
                    board.put(split, y, "│", screen._DIM)
                x, panel_width = split + 3, width - split - 4
            else:
                x, panel_width = 1, width - 2
                if not state.details and not state.form:
                    _roster(board, state, catalog, width - 1)
            if state.form:
                _editor(board, state, catalog, x, panel_width)
            elif width >= 76 or state.details:
                _inspector(board, state, catalog, x, panel_width)
        board.put(0, height - 2, safe(state.notice) if state.notice else "点击记录即预览 · 点击关联记录继续浏览 · r 刷新", screen._DIM, width=width)
        if state.form:
            buttons = (("Enter 编辑字段", "↵编辑", "select"), ("s 保存 / 确认", "s保存", "save"), ("q 取消", "q取消", "cancel"))
        elif state.key == "data":
            buttons = (("i 导入 CSV", "i导入", "import"), ("o 导出 CSV", "o导出", "export"),
                       ("g 演示校园", "g演示", "seed"), ("q 返回", "q返回", "back"))
        else:
            buttons = (("↑↓ 浏览", "↑↓", "down"), ("a 新建", "a新增", "create"), ("e 编辑", "e编辑", "edit"),
                       ("d 删除", "d删除", "delete"), ("Tab 详情", "Tab", "focus"), ("q 返回", "q返回", "back"))
    if state.form and state.form.options is not None:
        buttons = (("↑↓ 选择", "↑↓", "down"), ("Enter 确定", "↵", "select"), ("q 返回编辑", "q返回", "cancel"))
    footer, regions = theme.footer(width, buttons, height)
    # Footer and status always own their rows, even in a tiny terminal.
    board.rows[-1] = [(0, footer)]
    board.regions = [r for r in board.regions if r.y < height - 1 and r.x + r.width - 1 <= width] + regions
    return board.frame()
