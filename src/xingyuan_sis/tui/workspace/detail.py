from __future__ import annotations

from typing import Any

from ...terminal_ui import _wrap_line
from .. import screen
from ..layout import WorkspaceLayout, visible_start
from ..view_common import Board, identity, metric_pair, panel_heading, safe
from .data import COLLECTIONS, Catalog
from .state import Workspace


def _editing(state: Workspace | None) -> bool:
    return state is not None and state.form is not None and state.form.mode == "edit"


def _active_field(state: Workspace | None) -> str | None:
    if not _editing(state) or not state.form.fields:
        return None
    return state.form.fields[state.form.position].key


def _raw_value(state: Workspace | None, row: dict[str, Any], key: str) -> Any:
    if _editing(state) and key in state.form.values:
        return state.form.values.get(key)
    return row.get(key)


def _shown_value(state: Workspace | None, catalog: Catalog, key: str, field_key: str, row: dict[str, Any]) -> str:
    value = _raw_value(state, row, field_key)
    if _editing(state):
        options = catalog.options(key, field_key, state.form.values)
        if options is not None:
            return next((label for option, label in options if option == value), safe(value))
    return safe(value)


def details(
    key: str,
    row: dict[str, Any],
    catalog: Catalog,
    width: int,
    state: Workspace | None = None,
) -> list[tuple[str, str, str]]:
    editing = _editing(state)
    active = _active_field(state)
    editable = {field.key for field in catalog.fields(key, True)}

    title, identifier = identity(key, row)
    lines = [
        (title, screen._BOLD + screen._TEXT_ACCENT, ""),
        (identifier, screen._TEXT_SECONDARY, ""),
    ]

    if key == "courses":
        lines.append((
            "  /  ".join((
                metric_pair("学分", safe(_raw_value(state, row, "credits"))),
                metric_pair("课时", _raw_value(state, row, "hours")),
                metric_pair("次选课", row["enrolled"]),
            )),
            "",
            "",
        ))
    if key == "grades":
        score = _raw_value(state, row, "score")
        if score is None:
            lines.append(("待录入成绩", screen._BOLD + screen._TEXT_SECONDARY, ""))
        else:
            lines.append((f"{score:g} / 100", screen._BOLD + screen._TEXT_ACCENT, ""))
            size = min(30, max(1, width - 2))
            filled = round(score / 100 * size)
            lines.append(("━" * filled + "·" * (size - filled), screen._TEXT_ACCENT, ""))

    related_key, related = catalog.related(key, row)
    lines.extend([
        ("", "", ""),
        (f"关联{COLLECTIONS[related_key].noun}  {len(related):02d}", screen._BOLD + screen._TEXT_PRIMARY, ""),
    ])
    if not related:
        lines.append(("暂无关联记录", screen._TEXT_SECONDARY, ""))
    for item in related:
        if related_key == "grades":
            label = f"{item['student_name']}  ·  {safe(item['score']) if item['score'] is not None else '待录入'}"
        else:
            label = item["name"]
        lines.append((
            "↗ " + safe(label),
            screen._TEXT_ACCENT + "\x1b[4m",
            "" if editing else f"related:{related_key}:{item['id']}",
        ))

    lines.extend([
        ("", "", ""),
        ("详细信息", screen._BOLD + screen._TEXT_PRIMARY, ""),
    ])
    for field in COLLECTIONS[key].fields:
        if editing:
            action = f"field:{state.form.position}" if field.key == active else ""
        else:
            action = f"edit-field:{field.key}" if field.key in editable else ""
        value = _shown_value(state, catalog, key, field.key, row)
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

        if editing and field.key == active and state.form.options is not None:
            if state.form.options:
                for index, (_, option_label) in enumerate(state.form.options):
                    style = (
                        screen._BOLD + screen._TEXT_ACCENT
                        if index == state.form.option_index
                        else screen._TEXT_PRIMARY
                    )
                    lines.append(("  " + safe(option_label), style, f"option:{index}"))
            else:
                lines.append(("  暂无可选记录", screen._TEXT_SECONDARY, ""))
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


def render_inspector(board: Board, state: Workspace, catalog: Catalog, x: int, width: int) -> None:
    layout = WorkspaceLayout(board.width, board.height)
    heading_row = layout.panel_heading_row(state.key)
    top, bottom = layout.panel_content_row(state.key), board.height - 2
    row = state.current(catalog)
    editing = _editing(state)
    heading = identity(state.key, row)[0] if layout.compact and row else "档案"

    board.put(
        x,
        heading_row,
        panel_heading(heading, state.details or editing),
        action=None if editing else "focus",
        width=width,
    )
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

    rendered = details(state.key, row, catalog, width, state if editing else None)
    lines = rendered[layout.detail_offset:]

    selected_action = ""
    selected_line = -1
    if editing:
        selected_action = (
            f"option:{state.form.option_index}"
            if state.form.options is not None and state.form.options
            else f"field:{state.form.position}"
        )
        selected_line = next(
            (index for index, (_, _, action) in enumerate(lines) if action == selected_action),
            0,
        )
    else:
        targets = [(line - layout.detail_offset, action)
                   for line, action in detail_targets(state.key, row, catalog, width)]
        if targets:
            state.detail_selected = min(max(0, state.detail_selected), len(targets) - 1)
            selected_line, selected_action = targets[state.detail_selected]
        else:
            state.detail_selected = 0

    capacity = layout.panel_capacity(state.key)
    max_scroll = max(0, len(lines) - capacity)
    state.detail_scroll = min(max(0, state.detail_scroll), max_scroll)
    if (editing or state.details) and selected_line >= 0:
        state.detail_scroll = visible_start(selected_line, len(lines), capacity, state.detail_scroll)

    visible = lines[state.detail_scroll:state.detail_scroll + capacity]
    for offset, (text, style, action) in enumerate(visible):
        line_index = state.detail_scroll + offset
        selected = bool(action and action == selected_action and (editing or state.details))
        if selected:
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
            screen._TEXT_SECONDARY,
            action=None if editing else "focus",
            width=width,
        )
    if not editing:
        board.regions.extend(
            screen.HitRegion(x + 1, y + 1, width, "focus-details")
            for y in range(top, bottom)
        )
