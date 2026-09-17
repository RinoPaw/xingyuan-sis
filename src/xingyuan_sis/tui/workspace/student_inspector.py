from __future__ import annotations

from typing import Any

from ...schema import age_from_birth_date, is_complete_birth_date
from .. import screen
from ..layout import WorkspaceLayout, visible_start
from ..view_common import Board, panel_heading, safe
from .data import Catalog
from .presentation import display_value, project_record
from .state import Workspace


_Segment = tuple[str, str, str]
_Line = list[_Segment]
_COMPOSITE_TARGETS = (
    ("edit-field:family", "edit-field:branch"),
    ("edit-field:primary_element", "edit-field:primary_affinity"),
)


def directional_target(actions: list[str], selected: int, direction: str) -> int | None:
    """Return the next student-inspector target for a spatial arrow move.

    The right member of a composite row lives on the main vertical spine. The
    left member is reached horizontally; moving left from a left member exits
    the inspector and therefore returns None.
    """
    if not actions:
        return None
    selected = min(max(0, selected), len(actions) - 1)
    current = actions[selected]
    pairs = {
        left: right
        for left, right in _COMPOSITE_TARGETS
        if left in actions and right in actions
    }
    reverse = {right: left for left, right in pairs.items()}

    if direction == "left":
        return actions.index(reverse[current]) if current in reverse else None
    if direction == "right":
        return actions.index(pairs[current]) if current in pairs else selected
    if direction not in {"up", "down"}:
        return selected

    spine = [action for action in actions if action not in pairs]
    anchor = pairs.get(current, current)
    if anchor not in spine:
        return selected
    position = spine.index(anchor) + (-1 if direction == "up" else 1)
    position = min(max(0, position), len(spine) - 1)
    return actions.index(spine[position])


def _editing(state: Workspace | None) -> bool:
    return state is not None and state.form is not None and state.form.mode == "edit"


def _positions(state: Workspace | None) -> dict[str, int]:
    if not _editing(state):
        return {}
    return {field.key: index for index, field in enumerate(state.form.fields)}


def _age(values: dict[str, Any]) -> str:
    derived = age_from_birth_date(values.get("birth_date"))
    if derived is not None:
        return f"{derived}岁"
    manual = values.get("age")
    return "—" if manual is None else f"{manual}岁"


def _lines(
    row: dict[str, Any],
    catalog: Catalog,
    state: Workspace | None = None,
) -> list[_Line]:
    editing = _editing(state)
    positions = _positions(state)
    editable = {field.key for field in catalog.fields("students", True)}
    values = project_record(row, state.form if state is not None else None)

    def label(text: str) -> _Segment:
        return text, screen._TEXT_SECONDARY, ""

    def field(
        key: str,
        text: str | None = None,
        style: str = screen._TEXT_PRIMARY,
    ) -> _Segment:
        if editing:
            index = positions.get(key)
            action = f"field:{index}" if index is not None else ""
            selected = index == state.form.position
        else:
            action = f"edit-field:{key}" if key in editable else ""
            selected = False
        shown = display_value(catalog, "students", values, key) if text is None else text
        return shown, screen._BOLD + screen._TEXT_ACCENT if selected else style, action

    def age_field() -> _Segment:
        shown = _age(values)
        if is_complete_birth_date(values.get("birth_date")):
            return shown, screen._TEXT_PRIMARY, ""
        return field("age", shown)

    year = values.get("enrollment_year")
    lines: list[_Line] = [
        [field("name", style=screen._BOLD + screen._TEXT_PRIMARY)],
        [label("学号  "), field("student_no")],
        [label("物种  "), field("family"), (" · ", screen._TEXT_SECONDARY, ""), field("branch")],
        [label("性别  "), field("gender")],
        [label("年龄  "), age_field()],
        [label("入学  "), field("enrollment_year", f"{safe(year)}级")],
        [label("学院  "), (safe(row.get("department_name")), screen._TEXT_PRIMARY, "")],
        [label("班级  "), field("class_code")],
        [label("学籍  "), field("status")],
        [label("元素  "), field("primary_element"), (" · ", screen._TEXT_SECONDARY, ""), field("primary_affinity")],
    ]

    related_key, related = catalog.related("students", row)
    lines.extend((
        [],
        [(f"选课与成绩  {len(related):02d}", screen._BOLD + screen._TEXT_PRIMARY, "")],
    ))
    if not related:
        lines.append([("暂无关联记录", screen._TEXT_SECONDARY, "")])
    else:
        for item in related:
            score = safe(item["score"]) if item["score"] is not None else "待录入"
            action = "" if editing else f"related:{related_key}:{item['id']}"
            lines.append([(
                f"↗ {safe(item['course_name'])}  ·  {score}",
                screen._TEXT_ACCENT + "\x1b[4m",
                action,
            )])

    lines.extend((
        [],
        [("个人信息", screen._BOLD + screen._TEXT_PRIMARY, "")],
        [label("出生日期  "), field("birth_date")],
        [label("联系方式  "), field("contact")],
        [label("宿舍      "), field("dormitory")],
        [label("备注      "), field("notes")],
    ))

    if editing and state.form.options is not None:
        target = f"field:{state.form.position}"
        insert_at = next(
            (line_index + 1 for line_index, line in enumerate(lines)
             if any(action == target for _, _, action in line)),
            len(lines),
        )
        option_lines: list[_Line] = []
        if state.form.options:
            for index, (_, option_label) in enumerate(state.form.options):
                style = (
                    screen._BOLD + screen._TEXT_ACCENT
                    if index == state.form.option_index
                    else screen._TEXT_PRIMARY
                )
                option_lines.append([("  " + safe(option_label), style, f"option:{index}")])
        else:
            option_lines.append([("  暂无可选记录", screen._TEXT_SECONDARY, "")])
        lines[insert_at:insert_at] = option_lines

    return lines


def preferred_width(row: dict[str, Any] | None, catalog: Catalog) -> int:
    minimum, maximum = 28, 42
    if row is None:
        return minimum
    longest = max(
        screen._display_width("".join(text for text, _, _ in line))
        for line in _lines(row, catalog)
    )
    return min(maximum, max(minimum, longest + 2))


def detail_targets(row: dict[str, Any], catalog: Catalog, width: int) -> list[tuple[int, str]]:
    del width
    result: list[tuple[int, str]] = []
    seen: set[str] = set()
    for line_index, line in enumerate(_lines(row, catalog)):
        for _, _, action in line:
            if action and action not in seen:
                result.append((line_index, action))
                seen.add(action)
    return result


def render_inspector(
    board: Board,
    state: Workspace,
    catalog: Catalog,
    x: int,
    width: int,
) -> None:
    layout = WorkspaceLayout(board.width, board.height)
    top = layout.panel_content_row(state.key)
    bottom = board.height - 2
    row = state.current(catalog)
    if row is None:
        board.put(x, layout.panel_heading_row(state.key), panel_heading("档案", state.details), width=width)
        return

    editing = _editing(state)
    heading = safe(row["name"]) if layout.compact else "档案"
    board.put(
        x,
        layout.panel_heading_row(state.key),
        panel_heading(heading, state.details or editing),
        action="focus" if not editing else None,
        width=width,
    )

    offset = layout.detail_offset
    raw_lines = _lines(row, catalog, state)
    lines = raw_lines[offset:]
    capacity = layout.panel_capacity(state.key)

    selected_action = ""
    target_line = 0
    if editing:
        selected_action = (
            f"option:{state.form.option_index}"
            if state.form.options is not None and state.form.options
            else f"field:{state.form.position}"
        )
        target_line = next(
            (index for index, line in enumerate(lines)
             if any(action == selected_action for _, _, action in line)),
            0,
        )
    else:
        targets = [
            (line - offset, action)
            for line, action in detail_targets(row, catalog, width)
            if line >= offset
        ]
        if targets:
            state.detail_selected = min(max(0, state.detail_selected), len(targets) - 1)
            target_line, selected_action = targets[state.detail_selected]
        else:
            state.detail_selected = 0

    max_scroll = max(0, len(lines) - capacity)
    state.detail_scroll = min(max(0, state.detail_scroll), max_scroll)
    if editing or state.details:
        state.detail_scroll = visible_start(target_line, len(lines), capacity, state.detail_scroll)

    visible = lines[state.detail_scroll:state.detail_scroll + capacity]
    values = project_record(row, state.form)
    for offset_in_view, segments in enumerate(visible):
        y = top + offset_in_view
        cursor = x
        for segment_index, (text, style, action) in enumerate(segments):
            remaining = max(0, x + width - cursor)
            if remaining <= 0:
                break
            shown = screen._clip_cells(text, remaining)
            display = screen._display_width(shown)
            selected = bool(action and action == selected_action and (editing or state.details))
            drawn_style = (
                screen._SURFACE_SELECTED + screen._TEXT_ON_SELECTED
                if selected
                else style
            )

            if action:
                hit_width = max(1, display)
                if editing and action.startswith("field:"):
                    field_index = int(action.split(":")[1])
                    field_key = state.form.fields[field_index].key
                    freeform = catalog.options("students", field_key, values) is None
                    if selected and state.form.options is None and freeform and segment_index == len(segments) - 1:
                        hit_width = max(hit_width, remaining)
                board.regions.append(screen.HitRegion(cursor + 1, y + 1, hit_width, action))
            board.put(cursor, y, shown, drawn_style, width=remaining)
            cursor += display

    if len(lines) > capacity and not layout.compact:
        board.put(
            x,
            bottom - 1,
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
