from __future__ import annotations

from typing import Any

from ...schema import age_from_birth_date
from .. import screen
from ..view_common import safe
from .birth_date_editor import projected as projected_birth_date
from .data import Catalog
from .inspector import Line, Segment, expand_options, field_segment
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
    """Describe the student archive once; editing never changes its target graph."""
    session = state.field_session if state else None
    student_session = session if session is not None and not session.anchor_key.startswith("related:") else None
    values = catalog.project("students", project_record(row, student_session))
    birth_editing = student_session is not None and student_session.anchor_key == "birth_date"
    if birth_editing:
        values["birth_date"] = projected_birth_date(student_session.values)

    def label(text: str) -> Segment:
        return text, screen._TEXT_SECONDARY, ""

    def field(
        key: str,
        text: str | None = None,
        style: str = screen._TEXT_PRIMARY,
    ) -> Segment:
        return field_segment(catalog, "students", values, key, text, style)

    year = values.get("enrollment_year")
    result: list[Line] = [
        [field("name", style=screen._BOLD + screen._TEXT_PRIMARY)],
        [label("学号  "), field("student_no")],
        [label("物种  "), field("family"), (" · ", screen._TEXT_SECONDARY, ""), field("branch")],
        [label("性别  "), field("gender")],
        [label("年龄  "), field("age", _age(values))],
        [label("入学  "), field("enrollment_year", f"{safe(year)}级")],
        [label("学院  "), field("department_name")],
        [label("班级  "), field("major_code"), (" · ", screen._TEXT_SECONDARY, ""), field("class_number")],
        [label("学籍  "), field("status")],
        [label("元素  "), field("primary_element"), (" · ", screen._TEXT_SECONDARY, ""), field("primary_affinity")],
    ]

    related_key, related = catalog.related("students", row)
    result.extend((
        [],
        [(f"选课与成绩  {len(related):02d}", screen._BOLD + screen._TEXT_PRIMARY, "")],
    ))
    if not related:
        result.append([("暂无关联记录", screen._TEXT_SECONDARY, "")])
    else:
        for item in related:
            score_value = item["score"]
            score_action = f"field:related:{related_key}:{item['id']}:score"
            if session is not None and f"field:{session.anchor_key}" == score_action:
                score_value = session.values.get("score")
            score = safe(score_value) if score_value is not None else "待录入"
            result.append([
                (
                    safe(item["course_name"]),
                    screen._TEXT_ACCENT + "\x1b[4m",
                    f"related:{related_key}:{item['id']}",
                ),
                ("  ·  ", screen._TEXT_SECONDARY, ""),
                (score, screen._TEXT_PRIMARY, score_action),
            ])

    result.extend((
        [],
        [("个人信息", screen._BOLD + screen._TEXT_PRIMARY, "")],
    ))
    if birth_editing:
        result.append([
            label("出生日期  "),
            field("birth_year", " " if values.get("birth_year") is None else str(values["birth_year"])),
            ("-", screen._TEXT_SECONDARY, ""),
            field("birth_month", " " if values.get("birth_month") is None else str(values["birth_month"])),
            ("-", screen._TEXT_SECONDARY, ""),
            field("birth_day", " " if values.get("birth_day") is None else str(values["birth_day"])),
        ])
    else:
        result.append([label("出生日期  "), field("birth_date")])
    result.extend((
        [label("联系方式  "), field("contact")],
        [label("宿舍      "), field("dormitory")],
        [label("备注      "), field("notes")],
    ))

    return expand_options(result, student_session)
