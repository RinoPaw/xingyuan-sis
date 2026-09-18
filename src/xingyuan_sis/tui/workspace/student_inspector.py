from __future__ import annotations

from typing import Any

from ...schema import age_from_birth_date
from .. import screen
from ..view_common import safe
from .data import Catalog
from .inspector import Line, Segment, is_editing, field_segment, expand_options
from .presentation import project_record
from .state import Workspace


def _age(values: dict[str, Any]) -> str:
    derived = age_from_birth_date(values.get("birth_date"))
    age = derived if derived is not None else values.get("age")
    return "—" if age is None else f"{age}岁"


def lines(
    row: dict[str, Any],
    catalog: Catalog,
    state: Workspace | None = None,
) -> list[Line]:
    editing = is_editing(state)
    values = project_record(row, state.form if state else None)

    def label(text: str) -> Segment:
        return text, screen._TEXT_SECONDARY, ""

    def field(
        key: str,
        text: str | None = None,
        style: str = screen._TEXT_PRIMARY,
    ) -> Segment:
        return field_segment(state, catalog, "students", values, key, text, style)

    year = values.get("enrollment_year")
    lines: list[Line] = [
        [field("name", style=screen._BOLD + screen._TEXT_PRIMARY)],
        [label("学号  "), field("student_no")],
        [label("物种  "), field("family"), (" · ", screen._TEXT_SECONDARY, ""), field("branch")],
        [label("性别  "), field("gender")],
        [label("年龄  "), field("age", _age(values))],
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

    return expand_options(lines, state)
