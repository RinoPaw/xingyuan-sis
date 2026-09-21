from __future__ import annotations

from typing import Any

from ...schema import age_from_birth_date
from .. import screen
from ..view_common import safe
from .birth_date_editor import projected as projected_birth_date
from .data import Catalog
from .inspector import Line, Segment, expand_options, field_segment
from .presentation import display_semantic_fields, project_record
from .state import Workspace
from .student_layout import StudentFieldRow, rows as layout_rows


def _age(values: dict[str, Any]) -> str:
    derived = age_from_birth_date(values.get("birth_date"))
    age = derived if derived is not None else values.get("age")
    return "—" if age is None else f"{age}岁"


def _target_count(lines: list[Line]) -> int:
    """Count semantic inspector targets in display order."""
    seen: set[str] = set()
    for line in lines:
        for _, _, action in line:
            if action and not action.startswith("option:"):
                seen.add(action)
    return len(seen)


def lines(
    row: dict[str, Any],
    catalog: Catalog,
    state: Workspace | None = None,
) -> list[Line]:
    """Describe the student archive in user-facing semantic rows."""
    session = state.field_session if state else None
    student_session = session if session is not None and not session.anchor_key.startswith("related:") else None
    values = catalog.project("students", project_record(row, student_session))
    birth_editing = student_session is not None and student_session.anchor_key == "birth_date"
    if birth_editing:
        values["birth_date"] = projected_birth_date(student_session.values)

    def field(
        key: str,
        text: str | None = None,
        style: str = screen._TEXT_PRIMARY,
    ) -> Segment:
        return field_segment(catalog, "students", values, key, text, style)

    def birth_slot(key: str, width: int) -> str:
        raw = values.get(key)
        text = "" if raw is None else str(raw)
        return screen._pad_cells(screen._clip_cells(text, width), width)

    def field_row(spec: StudentFieldRow) -> Line:
        label_width = 6 if spec.section == "main" else 10
        line: Line = [(
            screen._pad_cells(screen._clip_cells(spec.label, label_width), label_width),
            screen._TEXT_SECONDARY,
            "",
        )]

        if spec.keys == ("birth_date",) and birth_editing:
            line.extend((
                field("birth_year", birth_slot("birth_year", 4)),
                ("-", screen._TEXT_SECONDARY, ""),
                field("birth_month", birth_slot("birth_month", 2)),
                ("-", screen._TEXT_SECONDARY, ""),
                field("birth_day", birth_slot("birth_day", 2)),
            ))
            return line

        if spec.keys == ("age",):
            line.append(field("age", _age(values)))
            return line

        if spec.keys == ("enrollment_year",):
            value = values.get("enrollment_year")
            line.append(field("enrollment_year", "—" if value in {None, ""} else f"{value}级"))
            return line

        parts = display_semantic_fields(catalog, "students", values, spec.keys)
        for index, (key, text) in enumerate(parts):
            if index:
                line.append((" · ", screen._TEXT_SECONDARY, ""))
            line.append(field(key, text))
        return line

    result: list[Line] = [field_row(spec) for spec in layout_rows("main")]

    related_key, related = catalog.related("students", row)
    result.extend((
        [],
        [(f"选课与成绩  {len(related):02d}", screen._BOLD + screen._TEXT_PRIMARY, "")],
    ))
    if not related:
        result.append([("暂无关联记录", screen._TEXT_SECONDARY, "")])
    else:
        first_related_target = _target_count(result)
        course_names = [safe(item["course_name"]) for item in related]
        course_width = max((screen._display_width(name) for name in course_names), default=0)
        for index, (item, course_name) in enumerate(zip(related, course_names, strict=True)):
            score_value = item["score"]
            score_action = f"field:related:{related_key}:{item['id']}:score"
            if session is not None and f"field:{session.anchor_key}" == score_action:
                score_value = session.values.get("score")
            score = safe(score_value) if score_value is not None else "待录入"
            course_action = f"related:{related_key}:{item['id']}"
            course_selected = (
                state is not None
                and session is None
                and state.detail_selected == first_related_target + index * 2
            )
            course_padding = " " * max(0, course_width - screen._display_width(course_name))
            course_row: Line = []
            if not course_selected:
                course_row.append(("  ", screen._TEXT_PRIMARY, ""))
            course_row.append((course_name, screen._TEXT_ACCENT + "\x1b[4m", course_action))
            if course_padding:
                course_row.append((course_padding, screen._TEXT_PRIMARY, ""))
            course_row.extend((
                (" · ", screen._TEXT_SECONDARY, ""),
                (score, screen._TEXT_PRIMARY, score_action),
            ))
            result.append(course_row)

    result.extend((
        [],
        [("个人信息", screen._BOLD + screen._TEXT_PRIMARY, "")],
    ))
    result.extend(field_row(spec) for spec in layout_rows("personal"))

    return expand_options(result, student_session)
