from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..terminal_ui import _wrap_line
from . import screen
from .layout import WorkspaceLayout, visible_start
from .view_common import Board, identity, metric_pair, panel_heading, safe
from .workspace_data import COLLECTIONS, Catalog

if TYPE_CHECKING:
    from .workspace import Workspace


def _student_summary(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    title = (
        screen._ansi(safe(row["name"]), screen._BOLD + screen._TEXT_ACCENT)
        + "  "
        + screen._ansi(safe(row["student_no"]), screen._TEXT_SECONDARY)
    )
    lineage = f"{safe(row['family'])} · {safe(row['branch'])}"
    enrollment = f"{safe(row['enrollment_year'])}级 · {safe(row['status'])}"
    element = f"{safe(row['primary_element'])} · {safe(row['primary_affinity'])}"
    classroom = safe(row["class_name"])
    department = safe(row["department_name"])
    return [
        (title, "", ""),
        (lineage + "    " + enrollment, screen._TEXT_PRIMARY, ""),
        (element + "    " + classroom, screen._TEXT_PRIMARY, ""),
        (department, screen._TEXT_SECONDARY, ""),
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


def detail_targets(key: str, row: dict[str, Any], catalog: Catalog, width: int) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, (_, _, action) in enumerate(details(key, row, catalog, width)):
        if action and action not in seen:
            result.append((index, action))
            seen.add(action)
    return result


def render_inspector(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    layout = WorkspaceLayout(board.width, board.height)
    top, bottom = layout.detail_top, board.height - 2
    row = state.current(catalog)
    heading = identity(state.key, row)[0] if layout.compact and row else "档案"
    board.put(x, top - 1, panel_heading(heading, state.details), action="focus", width=width)
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

    capacity = layout.detail_capacity
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
