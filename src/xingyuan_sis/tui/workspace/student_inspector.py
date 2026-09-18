from __future__ import annotations

from datetime import date
from typing import Any

from .. import screen
from ..view_common import safe
from .data import Catalog
from .state import Workspace
from .inspector import Line, Segment, is_editing, raw_value, field_segment, expand_options


def _age(state: Workspace | None, row: dict[str, Any]) -> str:
    value = raw_value(state, row, "birth_date")
    try:
        born = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return "—"
    today = date.today()
    if born > today:
        return "—"
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return f"{years}岁"


def _department(state: Workspace | None, catalog: Catalog, row: dict[str, Any]) -> str:
    if not is_editing(state):
        return safe(row.get("department_name"))
    class_code = state.form.values.get("class_code")
    selected_class = next(
        (item for item in catalog.records["classes"] if item["code"] == class_code),
        None,
    )
    if selected_class is None:
        return "—"
    major = next(
        (item for item in catalog.records["majors"] if item["id"] == selected_class["major_id"]),
        None,
    )
    if major is None:
        return safe(row.get("department_name"))
    department = next(
        (item for item in catalog.records["departments"] if item["id"] == major["department_id"]),
        None,
    )
    return safe(department["name"] if department else row.get("department_name"))


def lines(
    row: dict[str, Any],
    catalog: Catalog,
    state: Workspace | None = None,
) -> list[Line]:
    editing = is_editing(state)

    def label(text: str) -> Segment:
        return text, screen._TEXT_SECONDARY, ""

    def field(
        key: str,
        text: str | None = None,
        style: str = screen._TEXT_PRIMARY,
    ) -> Segment:
        return field_segment(state, catalog, "students", row, key, text, style)

    year = raw_value(state, row, "enrollment_year")
    lines: list[Line] = [
        [field("name", style=screen._BOLD + screen._TEXT_PRIMARY)],
        [label("学号  "), field("student_no")],
        [label("物种  "), field("family"), (" · ", screen._TEXT_SECONDARY, ""), field("branch")],
        [label("性别  "), field("gender")],
        [label("年龄  "), (_age(state, row), screen._TEXT_PRIMARY, "")],
        [label("入学  "), field("enrollment_year", f"{safe(year)}级")],
        [label("学院  "), (_department(state, catalog, row), screen._TEXT_PRIMARY, "")],
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
