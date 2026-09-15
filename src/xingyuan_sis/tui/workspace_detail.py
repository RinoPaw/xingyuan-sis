from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..terminal_ui import _wrap_line
from . import screen
from .layout import WorkspaceLayout, visible_start
from .view_common import Board, identity, metric_pair, panel_heading, safe
from .workspace_data import COLLECTIONS, Catalog

if TYPE_CHECKING:
    from .workspace import Workspace


_EditSegment = tuple[str, str, str]
_EditLine = list[_EditSegment]


def _student_summary(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    species = f"{safe(row['family'])} · {safe(row['branch'])}"
    return [
        (safe(row["name"]), screen._BOLD + screen._TEXT_ACCENT, ""),
        (screen._ansi("物种  ", screen._TEXT_SECONDARY) + screen._ansi(species, screen._TEXT_PRIMARY), "", ""),
        (screen._ansi("入学  ", screen._TEXT_SECONDARY) + screen._ansi(f"{safe(row['enrollment_year'])}级", screen._TEXT_PRIMARY), "", ""),
        (screen._ansi("亲和  ", screen._TEXT_SECONDARY) + screen._ansi(safe(row["primary_affinity"]), screen._TEXT_PRIMARY), "", ""),
        (screen._ansi("学院  ", screen._TEXT_SECONDARY) + screen._ansi(safe(row["department_name"]), screen._TEXT_PRIMARY), "", ""),
    ]


def details(key: str, row: dict[str, Any], catalog: Catalog, width: int) -> list[tuple[str, str, str]]:
    if key == "students":
        lines = _student_summary(row)
    else:
        title, identifier = identity(key, row)
        lines = [
            (title, screen._BOLD + screen._TEXT_ACCENT, ""),
            (identifier, screen._TEXT_SECONDARY, ""),
        ]

    if key == "courses":
        lines.append((
            "  /  ".join((
                metric_pair("学分", safe(row["credits"])),
                metric_pair("课时", row["hours"]),
                metric_pair("次选课", row["enrolled"]),
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
    related_title = "选课与成绩" if key == "students" else f"关联{COLLECTIONS[related_key].noun}"
    lines.extend([
        ("", "", ""),
        (f"{related_title}  {len(related):02d}", screen._BOLD + screen._TEXT_PRIMARY, ""),
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

    editable = {f.key for f in catalog.fields(key, True)}
    if key == "students":
        detail_keys = {"gender", "birth_date", "contact", "dormitory", "notes"}
        fields = [field for field in COLLECTIONS[key].fields if field.key in detail_keys]
    else:
        fields = list(COLLECTIONS[key].fields)

    lines.extend([
        ("", "", ""),
        ("详细信息", screen._BOLD + screen._TEXT_PRIMARY, ""),
    ])
    for field in fields:
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


def preferred_width(key: str, row: dict[str, Any] | None, catalog: Catalog) -> int:
    """Width needed by the current inspector before wrapping nonessential text."""
    minimum, maximum = 28, 42
    if row is None:
        return minimum
    rendered = details(key, row, catalog, maximum)
    longest = max(
        [screen._display_width("档案"), *(
            screen._display_width(screen._ANSI_RE.sub("", text))
            for text, _, _ in rendered
        )]
    )
    return min(maximum, max(minimum, longest + 2))


def detail_targets(key: str, row: dict[str, Any], catalog: Catalog, width: int) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, (_, _, action) in enumerate(details(key, row, catalog, width)):
        if action and action not in seen:
            result.append((index, action))
            seen.add(action)
    return result


def _form_value(catalog: Catalog, state: Workspace, field_key: str) -> str:
    form = state.form
    value = form.values.get(field_key)
    options = catalog.options(state.key, field_key, form.values)
    if options is not None:
        return next((label for option, label in options if option == value), safe(value))
    return safe(value)


def _student_department(catalog: Catalog, state: Workspace, row: dict[str, Any]) -> str:
    class_code = state.form.values.get("class_code")
    selected_class = next((item for item in catalog.records["classes"] if item["code"] == class_code), None)
    if selected_class is None:
        return safe(row.get("department_name"))
    major = next((item for item in catalog.records["majors"] if item["id"] == selected_class["major_id"]), None)
    if major is None:
        return safe(row.get("department_name"))
    department = next((item for item in catalog.records["departments"] if item["id"] == major["department_id"]), None)
    return safe(department["name"] if department else row.get("department_name"))


def _student_edit_lines(
    state: Workspace,
    catalog: Catalog,
    row: dict[str, Any],
) -> list[_EditLine]:
    form = state.form
    positions = {field.key: index for index, field in enumerate(form.fields)}

    def field(key: str, text: str | None = None, style: str = screen._TEXT_PRIMARY) -> _EditSegment:
        index = positions[key]
        selected = index == form.position
        return (
            _form_value(catalog, state, key) if text is None else text,
            screen._BOLD + screen._TEXT_ACCENT if selected else style,
            f"field:{index}",
        )

    def label(text: str) -> _EditSegment:
        return (text, screen._TEXT_SECONDARY, "")

    lines: list[_EditLine] = [
        [field("name", style=screen._BOLD + screen._TEXT_ACCENT)],
        [label("学号  "), field("student_no")],
        [label("物种  "), field("family"), (" · ", screen._TEXT_SECONDARY, ""), field("branch")],
        [label("入学  "), field("enrollment_year", f"{safe(form.values.get('enrollment_year'))}级")],
        [label("亲和  "), field("primary_affinity")],
        [label("学院  "), (_student_department(catalog, state, row), screen._TEXT_PRIMARY, "")],
        [label("班级  "), field("class_code")],
        [label("学籍  "), field("status"), ("    ", "", ""), label("元素  "), field("primary_element")],
    ]

    related_key, related = catalog.related("students", row)
    lines.extend([
        [],
        [(f"选课与成绩  {len(related):02d}", screen._BOLD + screen._TEXT_PRIMARY, "")],
    ])
    if not related:
        lines.append([("暂无关联记录", screen._TEXT_SECONDARY, "")])
    else:
        for item in related:
            score = safe(item["score"]) if item["score"] is not None else "待录入"
            lines.append([(f"↗ {safe(item['course_name'])}  ·  {score}", screen._TEXT_ACCENT + "\x1b[4m", "")])

    lines.extend([
        [],
        [("详细信息", screen._BOLD + screen._TEXT_PRIMARY, "")],
        [label("性别      "), field("gender")],
        [label("出生日期  "), field("birth_date")],
        [label("联系方式  "), field("contact")],
        [label("宿舍      "), field("dormitory")],
        [label("备注      "), field("notes")],
    ])

    if form.options is not None:
        target = f"field:{form.position}"
        insert_at = next(
            (index + 1 for index, line in enumerate(lines) if any(action == target for _, _, action in line)),
            len(lines),
        )
        option_lines: list[_EditLine] = []
        if form.options:
            for index, (_, option_label) in enumerate(form.options):
                style = (
                    screen._BOLD + screen._TEXT_ACCENT
                    if index == form.option_index
                    else screen._TEXT_PRIMARY
                )
                option_lines.append([("  " + safe(option_label), style, f"option:{index}")])
        else:
            option_lines.append([("  暂无可选记录", screen._TEXT_SECONDARY, "")])
        lines[insert_at:insert_at] = option_lines

    return lines


def _render_student_edit_inspector(
    board: Board,
    state: Workspace,
    catalog: Catalog,
    row: dict[str, Any],
    x: int,
    width: int,
    top: int,
) -> None:
    layout = WorkspaceLayout(board.width, board.height)
    board.put(
        x,
        layout.panel_heading_row(state.key),
        panel_heading("档案", True) + screen._ansi("  编辑中", screen._TEXT_SECONDARY),
        width=width,
    )

    lines = _student_edit_lines(state, catalog, row)
    save_row = board.height - 3
    capacity = max(1, save_row - top - 1)
    target_action = (
        f"option:{state.form.option_index}"
        if state.form.options is not None and state.form.options
        else f"field:{state.form.position}"
    )
    target_line = next(
        (index for index, line in enumerate(lines) if any(action == target_action for _, _, action in line)),
        0,
    )
    state.detail_scroll = visible_start(target_line, len(lines), capacity, state.detail_scroll)
    visible = lines[state.detail_scroll:state.detail_scroll + capacity]

    for offset, segments in enumerate(visible):
        y = top + offset
        cursor = x
        for segment_index, (text, style, action) in enumerate(segments):
            remaining = max(0, x + width - cursor)
            if remaining <= 0:
                break
            shown = screen._clip_cells(text, remaining)
            display = screen._display_width(shown)
            if action.startswith("field:"):
                field_index = int(action.split(":")[1])
                selected = field_index == state.form.position
                field_key = state.form.fields[field_index].key
                freeform = catalog.options(state.key, field_key, state.form.values) is None
                hit_width = display
                if selected and state.form.options is None and freeform and segment_index == len(segments) - 1:
                    hit_width = max(display, remaining)
                board.regions.append(screen.HitRegion(cursor + 1, y + 1, max(1, hit_width), action))
                board.put(cursor, y, shown, style, width=remaining)
            else:
                board.put(cursor, y, shown, style, action, width=remaining)
            cursor += display

    board.button(x, save_row, " 保存 ", "save")


def _render_generic_edit_inspector(
    board: Board,
    state: Workspace,
    catalog: Catalog,
    x: int,
    width: int,
    top: int,
) -> None:
    form = state.form
    board.put(
        x,
        WorkspaceLayout(board.width, board.height).panel_heading_row(state.key),
        panel_heading("档案", True) + screen._ansi("  编辑中", screen._TEXT_SECONDARY),
        width=width,
    )

    if form.options is not None:
        field = form.fields[form.position]
        label_width = min(12, max(4, width // 3))
        label = screen._pad_cells(field.label + ("*" if field.required else ""), label_width)
        value = _form_value(catalog, state, field.key)
        text = screen._pad_cells(screen._clip_cells(f"{label}  {value}", width), width)
        board.put(
            x, top, text,
            screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED,
            f"field:{form.position}", width,
        )

        option_row = top + 2
        capacity = max(1, board.height - option_row - 3)
        first = min(
            max(0, form.option_index - capacity + 1),
            max(0, len(form.options) - capacity),
        )
        for i, (_, option_label) in enumerate(form.options[first:first + capacity], start=first):
            shown = "  " + safe(option_label)
            shown = screen._pad_cells(screen._clip_cells(shown, width), width)
            style = (
                screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
                if i == form.option_index
                else screen._TEXT_PRIMARY
            )
            board.put(x, option_row + i - first, shown, style, f"option:{i}", width)
        if not form.options:
            board.put(x, option_row, "暂无可选记录。", screen._TEXT_SECONDARY, width=width)
        return

    save_row = board.height - 3
    capacity = max(1, save_row - top - 1)
    first = visible_start(form.position, len(form.fields), capacity, state.detail_scroll)
    state.detail_scroll = first
    label_width = min(12, max(4, width // 3))

    for i, field in enumerate(form.fields[first:first + capacity], start=first):
        label = screen._pad_cells(
            screen._clip_cells(field.label + ("*" if field.required else ""), label_width),
            label_width,
        )
        value = _form_value(catalog, state, field.key)
        text = screen._pad_cells(screen._clip_cells(f"{label}  {value}", width), width)
        style = (
            screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
            if i == form.position
            else screen._TEXT_PRIMARY
        )
        board.put(x, top + i - first, text, style, f"field:{i}", width)

    board.button(x, save_row, " 保存 ", "save")


def render_inspector(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    layout = WorkspaceLayout(board.width, board.height)
    heading_row = layout.panel_heading_row(state.key)
    top, bottom = layout.panel_content_row(state.key), board.height - 2
    row = state.current(catalog)
    heading = identity(state.key, row)[0] if layout.compact and row else "档案"

    if row is not None and state.form is not None and state.form.mode == "edit":
        if state.key == "students":
            _render_student_edit_inspector(board, state, catalog, row, x, width, top)
        else:
            _render_generic_edit_inspector(board, state, catalog, x, width, top)
        return

    board.put(x, heading_row, panel_heading(heading, state.details), action="focus", width=width)
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

    lines = details(state.key, row, catalog, width)[layout.detail_offset:]
    targets = [(line - layout.detail_offset, action)
               for line, action in detail_targets(state.key, row, catalog, width)]
    if targets:
        state.detail_selected = min(max(0, state.detail_selected), len(targets) - 1)
        selected_line = targets[state.detail_selected][0]
    else:
        state.detail_selected = 0
        selected_line = -1

    capacity = layout.panel_capacity(state.key)
    max_scroll = max(0, len(lines) - capacity)
    state.detail_scroll = min(max(0, state.detail_scroll), max_scroll)
    if state.details and selected_line >= 0:
        state.detail_scroll = visible_start(selected_line, len(lines), capacity, state.detail_scroll)

    visible = lines[state.detail_scroll:state.detail_scroll + capacity]
    for offset, (text, style, action) in enumerate(visible):
        line_index = state.detail_scroll + offset
        if state.details and line_index == selected_line:
            plain = screen._ANSI_RE.sub("", text)
            plain = screen._pad_cells(screen._clip_cells(plain, width), width)
            board.put(
                x, top + offset, plain,
                screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED,
                action, width,
            )
        else:
            board.put(x, top + offset, text, style, action, width)

    if len(lines) > capacity and not layout.compact:
        board.put(
            x, bottom - 1,
            f"{state.detail_scroll + 1}–{min(len(lines), state.detail_scroll + capacity)} / {len(lines)}",
            screen._TEXT_SECONDARY, action="focus", width=width,
        )
    board.regions.extend(
        screen.HitRegion(x + 1, y + 1, width, "focus-details")
        for y in range(top, bottom)
    )
