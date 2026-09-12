"""Responsive roster, record inspector, editor and campus dashboard."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import screen, theme
from .workspace_data import ACADEMICS, COLLECTIONS, Catalog
from ..terminal_ui import _wrap_line

if TYPE_CHECKING:
    from .workspace import Workspace


def safe(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return " ".join("".join(char for char in str(value) if char.isprintable() or char == "\n").split())


def _metric_summary(metrics: list[tuple[str, str]]) -> str:
    """Render compact metrics as emphasized values with secondary labels."""
    return "    ".join(
        screen._ansi(value, screen._BOLD + screen._TEXT_ACCENT)
        + " "
        + screen._ansi(label, screen._TEXT_SECONDARY)
        for label, value in metrics
    )


def _metric_pair(label: str, value: object) -> str:
    return (
        screen._ansi(str(value), screen._BOLD + screen._TEXT_ACCENT)
        + " "
        + screen._ansi(label, screen._TEXT_SECONDARY)
    )


def _section_heading(text: str) -> str:
    return screen._ansi(text, screen._BOLD + screen._TEXT_PRIMARY)


def _panel_heading(text: str, focused: bool) -> str:
    marker = "▌ " if focused else "  "
    style = screen._BOLD + (screen._TEXT_ACCENT if focused else screen._TEXT_PRIMARY)
    return screen._ansi(marker + text, style)


def _roster_window(state: Workspace, row_count: int, capacity: int) -> int:
    """Keep the current selection visible without moving an already valid viewport."""
    max_first = max(0, row_count - capacity)
    first = min(max(0, state.roster_scroll), max_first)
    if state.selected < first:
        first = state.selected
    elif state.selected >= first + capacity:
        first = state.selected - capacity + 1
    state.roster_scroll = min(max(0, first), max_first)
    return state.roster_scroll


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
    lines = [
        (title, screen._BOLD + screen._TEXT_ACCENT, ""),
        (identifier, screen._TEXT_SECONDARY, ""),
        ("", "", ""),
    ]
    if key == "students":
        lines.append((
            f"{safe(row['primary_element'])} · {safe(row['primary_affinity'])}  /  {safe(row['status'])}",
            screen._TEXT_PRIMARY,
            "",
        ))
        lines.append((
            safe(row["class_name"]) + " · " + safe(row["department_name"]),
            screen._TEXT_SECONDARY,
            "",
        ))
    if key == "courses":
        lines.append((
            "  /  ".join((
                _metric_pair("学分", safe(row["credits"])),
                _metric_pair("课时", row["hours"]),
                _metric_pair("次选课", row["enrolled"]),
            )),
            "",
            "",
        ))
    if key == "grades":
        score = row["score"]
        if score is None:
            lines.append(("待录入成绩", screen._BOLD + screen._TEXT_SECONDARY, "edit-field:score"))
        else:
            lines.append((f"{score:g} / 100", screen._BOLD + screen._TEXT_ACCENT, "edit-field:score"))
            size = min(30, max(1, width - 2))
            filled = round(score / 100 * size)
            lines.append(("━" * filled + "·" * (size - filled), screen._TEXT_ACCENT, "edit-field:score"))

    related_key, related = catalog.related(key, row)
    lines.extend([
        ("", "", ""),
        (f"关联{COLLECTIONS[related_key].noun}  {len(related):02d}", screen._BOLD + screen._TEXT_PRIMARY, ""),
    ])
    if not related:
        lines.append(("暂无关联记录", screen._TEXT_SECONDARY, ""))
    for item in related:
        if related_key == "grades":
            label = item["course_name"] if key == "students" else item["student_name"]
            label = f"{label}  ·  {safe(item['score']) if item['score'] is not None else '待录入'}"
        else:
            label = item["name"]
        lines.append((
            "↗ " + safe(label),
            screen._TEXT_ACCENT + "\x1b[4m",
            f"related:{related_key}:{item['id']}",
        ))

    lines.extend([
        ("", "", ""),
        ("档案字段  ·  点击编辑", screen._BOLD + screen._TEXT_PRIMARY, ""),
    ])
    editable = {f.key for f in catalog.fields(key, True)}
    for field in COLLECTIONS[key].fields:
        action = f"edit-field:{field.key}" if field.key in editable else ""
        value = safe(row.get(field.key))
        chunks = _wrap_line(value, max(2, width - 12))
        prefix = screen._pad_cells(field.label, 10)
        first_line = (
            screen._ansi(prefix, screen._TEXT_SECONDARY)
            + "  "
            + screen._ansi(chunks[0], screen._TEXT_PRIMARY)
        )
        lines.append((first_line, "", action))
        lines.extend((
            " " * 12 + screen._ansi(part, screen._TEXT_PRIMARY),
            "",
            action,
        ) for part in chunks[1:])
    return lines


def detail_targets(
    key: str,
    row: dict[str, Any],
    catalog: Catalog,
    width: int,
) -> list[tuple[int, str]]:
    """Return each keyboard-selectable detail action once, with its first line."""
    result: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, (_, _, action) in enumerate(_details(key, row, catalog, width)):
        if action and action not in seen:
            result.append((index, action))
            seen.add(action)
    return result


def _inspector(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    top, bottom = 9, board.height - 2
    panel_title = (
        _panel_heading("档案", state.details)
        + screen._ansi(" / " + ("阅读中" if state.details else "即时预览"), screen._TEXT_SECONDARY)
    )
    board.put(x, 8, panel_title, action="focus", width=width)
    row = state.current(catalog)
    if row is None:
        if state.query or state.view:
            board.put(x, top + 1, "当前条件下没有记录", screen._BOLD + screen._TEXT_PRIMARY, width=width)
            board.put(x, top + 3, "清除搜索或切换上方视图。", screen._TEXT_SECONDARY, width=width)
            if state.query:
                board.button(x, top + 5, "清除搜索", "reset-search")
            return
        board.put(x, top + 1, "从第一份档案开始", screen._BOLD + screen._TEXT_PRIMARY, width=width)
        board.put(x, top + 3, "新建记录后，名册与档案会在这里展开。", screen._TEXT_SECONDARY, width=width)
        board.button(x, top + 5, "a 新建", "create")
        if not any(catalog.records.values()):
            board.button(x, top + 7, "体验演示校园", "seed")
        return

    lines = _details(state.key, row, catalog, width)
    targets = detail_targets(state.key, row, catalog, width)
    if targets:
        state.detail_selected = min(max(0, state.detail_selected), len(targets) - 1)
        selected_line = targets[state.detail_selected][0]
    else:
        state.detail_selected = 0
        selected_line = -1

    capacity = max(1, bottom - top - 1)
    max_scroll = max(0, len(lines) - capacity)
    state.detail_scroll = min(max(0, state.detail_scroll), max_scroll)
    if state.details and selected_line >= 0:
        if selected_line < state.detail_scroll:
            state.detail_scroll = selected_line
        elif selected_line >= state.detail_scroll + capacity:
            state.detail_scroll = selected_line - capacity + 1
        state.detail_scroll = min(max(0, state.detail_scroll), max_scroll)

    visible = lines[state.detail_scroll:state.detail_scroll + capacity]
    for offset, (text, style, action) in enumerate(visible):
        line_index = state.detail_scroll + offset
        if state.details and line_index == selected_line:
            plain = screen._ANSI_RE.sub("", text)
            plain = screen._pad_cells(screen._clip_cells(plain, width), width)
            board.put(
                x,
                top + offset,
                plain,
                screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED,
                action,
                width,
            )
        else:
            board.put(x, top + offset, text, style, action, width)

    if len(lines) > capacity:
        board.put(
            x,
            bottom - 1,
            f"{state.detail_scroll + 1}–{min(len(lines), state.detail_scroll + capacity)} / {len(lines)}"
            "  ·  Tab 切换焦点",
            screen._TEXT_SECONDARY,
            action="focus",
            width=width,
        )
    board.regions.extend(
        screen.HitRegion(x + 1, y + 1, width, "focus-details")
        for y in range(top, bottom)
    )


def _editor(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    form = state.form
    if form.options is not None:
        board.put(
            x, 8, "选择 / " + form.fields[form.position].label,
            screen._BOLD + screen._TEXT_ACCENT, width=width,
        )
        capacity = max(1, board.height - 13)
        first = min(max(0, form.option_index - capacity + 1), max(0, len(form.options) - capacity))
        for i, (_, label) in enumerate(form.options[first:first + capacity], start=first):
            text = screen._pad_cells(screen._clip_cells(safe(label), width), width)
            selected_style = screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED if i == form.option_index else ""
            board.put(x, 10 + i - first, text, selected_style, f"option:{i}", width)
        if not form.options:
            board.put(x, 10, "暂无可选记录，请先创建。", screen._TEXT_SECONDARY, width=width)
        return

    titles = {
        "create": "新建档案",
        "edit": "编辑档案",
        "delete": "删除记录",
        "import": "导入学生 CSV",
        "export": "导出学生 CSV",
        "seed": "建立演示校园",
    }
    board.put(x, 8, titles[form.mode], screen._BOLD + screen._TEXT_ACCENT, width=width)

    if form.mode in {"delete", "seed"}:
        messages: list[tuple[str, str]] = [
            ("将写入一组完整的演示数据。", screen._TEXT_PRIMARY),
            ("仅支持空数据库，已有记录会保留。", screen._TEXT_SECONDARY),
        ]
        if form.mode == "delete":
            title, identifier = _identity(state.key, form.original)
            messages = [
                (f"确认删除 {title}？", screen._BOLD + screen._TEXT_PRIMARY),
                (identifier, screen._TEXT_SECONDARY),
                ("删除后无法撤销。", screen._BOLD + screen._TEXT_PRIMARY),
            ]
            if state.key in {"students", "courses"}:
                _, related = catalog.related(state.key, form.original)
                messages.append((f"同时移除 {len(related)} 条关联选课。", screen._TEXT_PRIMARY))
        for index, (message, style) in enumerate(messages):
            board.put(x, 10 + index * 2, message, style, width=width)
    else:
        board.put(x, 9, "* 必填  ·  更改暂存，保存后生效", screen._TEXT_SECONDARY, width=width)
        capacity = max(1, board.height - 15)
        first = min(max(0, form.position - capacity + 1), max(0, len(form.fields) - capacity))
        for i, field in enumerate(form.fields[first:first + capacity], start=first):
            value = safe(form.values.get(field.key))
            if i == form.position:
                label = f"› {field.label}{'*' if field.required else ''}  {value}"
                text = screen._pad_cells(screen._clip_cells(label, width), width)
                board.put(
                    x, 11 + i - first, text,
                    screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED,
                    f"field:{i}", width,
                )
            else:
                label = f"  {field.label}{'*' if field.required else ''}"
                text = (
                    screen._ansi(label, screen._TEXT_SECONDARY)
                    + "  "
                    + screen._ansi(value, screen._TEXT_PRIMARY)
                )
                board.put(x, 11 + i - first, text, action=f"field:{i}", width=width)
        if len(form.fields) > capacity:
            board.put(
                x, board.height - 4,
                f"字段 {form.position + 1}/{len(form.fields)}  ·  ↑↓ 切换",
                screen._TEXT_SECONDARY, width=width,
            )

    board.put(
        x, board.height - 3, "Esc 取消",
        screen._TEXT_SECONDARY, width=width,
    )


def _roster(board: Board, state: Workspace, catalog: Catalog, width: int) -> None:
    rows = state.rows(catalog)
    capacity = max(1, board.height - 12)
    first = _roster_window(state, len(rows), capacity)
    heading = _panel_heading("名册", not state.details)
    range_text = f"  {len(rows):02d}" + (
        f"  /  {first + 1}–{min(first + capacity, len(rows))}" if rows else ""
    )
    board.put(1, 8, heading + screen._ansi(range_text, screen._TEXT_SECONDARY), width=width - 1)

    definitions = COLLECTIONS[state.key].columns
    available = max(1, width - 2)
    columns: list[list[Any]] = []
    remaining = available
    for key, label, base_size in definitions:
        size = min(base_size, remaining) if not columns else base_size
        if size > remaining:
            break
        columns.append([key, label, size])
        remaining -= size + 1

    if columns and remaining > 0:
        for column in columns:
            key, label, size = column
            desired = max(
                screen._display_width(label),
                *(screen._display_width(safe(row.get(key))) for row in rows),
                size,
            )
            growth = min(max(0, desired - size), remaining)
            column[2] += growth
            remaining -= growth
            if remaining <= 0:
                break

    header = " ".join(screen._pad_cells(label, size) for _, label, size in columns)
    board.put(1, 9, header, screen._TEXT_SECONDARY, width=width - 1)
    for index, row in enumerate(rows[first:first + capacity], start=first):
        text = " ".join(
            screen._pad_cells(screen._clip_cells(safe(row.get(key)), size), size)
            for key, _, size in columns
        )
        text = screen._pad_cells(screen._clip_cells(text, width - 1), width - 1)
        if index == state.selected:
            selected_style = (
                screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
                if not state.details
                else screen._SURFACE_INTERACTIVE + screen._TEXT_PRIMARY
            )
        else:
            selected_style = screen._TEXT_PRIMARY
        board.put(1, 10 + index - first, text, selected_style, f"row:{index}", width - 1)

    if not rows:
        board.put(
            1, 11,
            "没有匹配的记录" if state.query or state.view else "名册还是空白的",
            screen._BOLD + screen._TEXT_PRIMARY, width=width - 1,
        )
        if state.query or state.view:
            board.put(1, 13, "切换视图或清除搜索条件。", screen._TEXT_SECONDARY, width=width - 1)
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

    lines.append(("校园脉络 / 学生元素分布", screen._BOLD + screen._TEXT_PRIMARY, ""))
    distribution = catalog.distribution()
    maximum = max((count for _, count in distribution), default=1)
    for label, count in distribution:
        bar = "━" * max(1, round(count / maximum * max(1, split - 20)))
        text = (
            screen._ansi(f"{safe(label):<4}", screen._TEXT_SECONDARY)
            + " "
            + screen._ansi(bar, screen._TEXT_ACCENT)
            + " "
            + screen._ansi(str(count), screen._BOLD + screen._TEXT_ACCENT)
        )
        lines.append((text, "", "collection:students"))
    if not distribution:
        lines.extend([
            ("", "", ""),
            ("校园尚未建立第一份学生档案。", screen._TEXT_SECONDARY, ""),
            ("[ 导入学生 CSV ]", screen._TEXT_ACCENT, "import"),
            ("[ 体验演示校园 ]", screen._TEXT_ACCENT, "seed"),
        ])

    lines.extend([("", "", ""), ("班级 / 学生人数", screen._BOLD + screen._TEXT_PRIMARY, "")])
    for row in catalog.records["classes"]:
        text = (
            screen._ansi(safe(row["name"]), screen._TEXT_PRIMARY)
            + "  "
            + screen._ansi(str(row["enrolled"]), screen._BOLD + screen._TEXT_ACCENT)
            + screen._ansi(" 人", screen._TEXT_SECONDARY)
        )
        lines.append((text, "", f"related:classes:{row['id']}"))

    grades = catalog.records["grades"]
    scores = [r["score"] for r in grades if r["score"] is not None]
    right = [
        ("成绩进度", screen._BOLD + screen._TEXT_PRIMARY, ""),
        ("", "", ""),
        (
            screen._ansi("已录入 ", screen._TEXT_SECONDARY)
            + screen._ansi(f"{len(scores)} / {len(grades)}", screen._BOLD + screen._TEXT_ACCENT),
            "",
            "collection:grades",
        ),
    ]
    for label, low, high in (
        ("90–100", 90, 101),
        ("80–89", 80, 90),
        ("60–79", 60, 80),
        ("60 以下", 0, 60),
    ):
        count = sum(low <= score < high for score in scores)
        right.append((
            screen._ansi(label, screen._TEXT_SECONDARY)
            + "  "
            + screen._ansi(str(count), screen._TEXT_PRIMARY),
            "",
            "collection:grades",
        ))

    right.extend([("", "", ""), ("导入记录", screen._BOLD + screen._TEXT_PRIMARY, "")])
    report_width = max(2, width - split - 3 if width >= 76 else width - 2)
    report_lines = state.report or ["本次还没有导入错误。"]
    report_style = screen._TEXT_PRIMARY if state.report else screen._TEXT_SECONDARY
    right.extend(
        (part, report_style, "")
        for line in report_lines
        for part in _wrap_line(safe(line), report_width)
    )

    if width < 76:
        lines.extend([("", "", ""), *right])
        panels = [(1, width - 2, lines)]
    else:
        panels = [(1, split - 3, lines), (split + 2, width - split - 3, right)]

    capacity = max(1, board.height - 11)
    state.detail_scroll = min(
        state.detail_scroll,
        max(0, max(len(panel[2]) for panel in panels) - capacity),
    )
    for x, panel_width, content in panels:
        for index, (text, style, action) in enumerate(
            content[state.detail_scroll:state.detail_scroll + capacity]
        ):
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
        row = state.current(catalog)
        board.put(
            0, 3, safe(_identity(state.key, row)[0]) if row else title,
            screen._BOLD + screen._TEXT_ACCENT,
            action="focus" if row else "",
        )
        if state.form:
            form = state.form
            if form.options is not None:
                if form.options:
                    board.put(
                        0, 4, safe(form.options[form.option_index][1]),
                        action=f"option:{form.option_index}",
                    )
                else:
                    board.put(0, 4, "暂无可选记录，请先创建。", screen._TEXT_SECONDARY)
            elif form.fields:
                f = form.fields[form.position]
                field_line = (
                    screen._ansi(f.label, screen._TEXT_SECONDARY)
                    + "  "
                    + screen._ansi(safe(form.values.get(f.key)), screen._TEXT_PRIMARY)
                )
                board.put(0, 4, field_line, action=f"field:{form.position}")
            else:
                board.put(0, 4, "确认执行？  Esc 取消", screen._BOLD + screen._TEXT_PRIMARY)
        elif row:
            content = _details(state.key, row, catalog, width)[1:]
            capacity = max(1, height - 6)
            state.detail_scroll = min(state.detail_scroll, max(0, len(content) - capacity))
            for i, (text, style, action) in enumerate(
                content[state.detail_scroll:state.detail_scroll + capacity]
            ):
                board.put(0, 4 + i, text, style, action, width)
        elif state.key == "data":
            for i, (label, key) in enumerate((
                ("学生", "students"),
                ("课程", "courses"),
                ("选课", "grades"),
            )):
                if 4 + i < height - 2:
                    board.put(
                        0, 4 + i,
                        _metric_pair(label, len(catalog.records[key])),
                        action=f"collection:{key}",
                    )

        board.rows[height - 2] = []
        board.put(
            0, height - 2,
            screen._clip_cells(safe(state.notice) if state.notice else "", width),
            screen._TEXT_SECONDARY,
        )
        buttons = (
            (("s 保存", "s", "save"), ("Esc", "Esc", "cancel"))
            if state.form else
            (("↑↓ 浏览", "↑↓", "down"), ("a 新建", "a", "create"),
             ("e 编辑", "e", "edit"), ("Esc", "Esc", "back"))
        )
        if state.key == "data" and not state.form:
            buttons = (
                ("i 导入", "i", "import"),
                ("o 导出", "o", "export"),
                ("g 演示", "g", "seed"),
                ("Esc", "Esc", "back"),
            )
    else:
        noun = COLLECTIONS[state.key].noun if state.key != "data" else "校园概览"
        board.put(1, 3, noun, screen._BOLD + screen._TEXT_ACCENT)

        x = 1
        if state.key == "data":
            metrics = [
                ("学生", str(len(catalog.records["students"]))),
                ("课程", str(len(catalog.records["courses"]))),
                ("选课", str(len(catalog.records["grades"]))),
            ]
            board.put(1, 4, _metric_summary(metrics))
            choices = [
                (label, None, f"collection:{key}", False)
                for label, key in (
                    ("学生", "students"), ("课程", "courses"),
                    ("成绩", "grades"), ("教务", "departments"),
                )
            ]
            choice_row = 5
        elif state.key in ACADEMICS:
            choices = [
                (COLLECTIONS[key].noun, len(catalog.records[key]), f"collection:{key}", key == state.key)
                for key in ACADEMICS
            ]
            choice_row = 4
        else:
            choices = [
                (
                    label,
                    len(catalog.rows(state.key, i, state.query)),
                    f"view:{i}",
                    i == state.view,
                )
                for i, label in enumerate(COLLECTIONS[state.key].views)
            ]
            choice_row = 4

        for i, (label, count, action, selected) in enumerate(choices):
            count_text = f" · {count}" if count is not None else ""
            shown = (
                f"{i + 1} {label}{count_text}"
                if width >= 48 else f"{label}{count_text}"
            )
            if x + screen._display_width(shown) + 4 <= width:
                x = board.button(x, choice_row, shown, action, selected=selected)

        if state.key != "data":
            text = f"/ {safe(state.query)}" if state.query else "/ 搜索姓名、编号、班级…"
            board.put(1, 5, text, screen._TEXT_SECONDARY, "search", max(1, width - 12))
            if state.query and width >= 40:
                clear = theme.button("清除")
                board.put(width - 10, 5, clear, action="reset-search")

        separator_row = 7 if state.key == "data" else 6
        board.put(0, separator_row, "─" * width, screen._BORDER_SUBTLE)

        if state.key == "data" and not state.form:
            _dashboard(board, state, catalog)
        else:
            split = width // 2 if width >= 76 else width
            if width >= 76:
                if state.key != "data":
                    _roster(board, state, catalog, split - 1)
                for y in range(8, height - 2):
                    board.put(split, y, "│", screen._BORDER_SUBTLE)
                x, panel_width = split + 3, width - split - 4
            else:
                x, panel_width = 1, width - 2
                if not state.details and not state.form:
                    _roster(board, state, catalog, width - 1)

            if state.form:
                _editor(board, state, catalog, x, panel_width)
            elif width >= 76 or state.details:
                _inspector(board, state, catalog, x, panel_width)

        board.put(
            0, height - 2,
            safe(state.notice) if state.notice else "点击记录即预览 · 点击关联记录继续浏览 · r 刷新",
            screen._TEXT_SECONDARY, width=width,
        )

        if state.form:
            buttons = (
                ("Enter 编辑字段", "↵编辑", "select"),
                ("s 保存 / 确认", "s保存", "save"),
                ("Esc", "Esc", "cancel"),
            )
        elif state.key == "data":
            buttons = (
                ("i 导入 CSV", "i导入", "import"),
                ("o 导出 CSV", "o导出", "export"),
                ("g 演示校园", "g演示", "seed"),
                ("Esc", "Esc", "back"),
            )
        else:
            buttons = (
                ("↑↓ 浏览", "↑↓", "down"),
                ("a 新建", "a新增", "create"),
                ("e 编辑", "e编辑", "edit"),
                ("d 删除", "d删除", "delete"),
                ("Tab 切换", "Tab", "focus"),
                ("Esc", "Esc", "back"),
            )

    if state.form and state.form.options is not None:
        buttons = (
            ("↑↓ 选择", "↑↓", "down"),
            ("Enter 确定", "↵", "select"),
            ("Esc", "Esc", "cancel"),
        )

    footer, regions = theme.footer(width, buttons, height)
    board.rows[-1] = [(0, footer)]
    board.regions = [
        r for r in board.regions
        if r.y < height - 1 and r.x + r.width - 1 <= width
    ] + regions
    return board.frame()
