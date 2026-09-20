from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, TypeVar


@dataclass(frozen=True)
class StudentFieldRow:
    """One user-facing student archive row and its semantic fields."""

    label: str
    keys: tuple[str, ...]
    section: str = "main"


STUDENT_FIELD_ROWS: tuple[StudentFieldRow, ...] = (
    StudentFieldRow("姓名", ("name",)),
    StudentFieldRow("学号", ("student_no",)),
    StudentFieldRow("物种", ("family", "branch")),
    StudentFieldRow("性别", ("gender",)),
    StudentFieldRow("年龄", ("age",)),
    StudentFieldRow("入学", ("enrollment_year",)),
    StudentFieldRow("学院", ("department_name",)),
    StudentFieldRow("班级", ("major_code", "class_number")),
    StudentFieldRow("学籍", ("status",)),
    StudentFieldRow("元素", ("primary_element", "primary_affinity")),
    StudentFieldRow("出生日期", ("birth_date",), "personal"),
    StudentFieldRow("联系方式", ("contact",), "personal"),
    StudentFieldRow("宿舍", ("dorm_area", "dorm_building", "dorm_room"), "personal"),
    StudentFieldRow("备注", ("notes",), "personal"),
)


STUDENT_FIELD_ORDER = tuple(
    key
    for row in STUDENT_FIELD_ROWS
    for key in row.keys
)


T = TypeVar("T")


def order_fields(fields: Iterable[T]) -> tuple[T, ...]:
    """Order student form fields from the archive layout, never from schema order."""
    items = tuple(fields)
    by_key = {getattr(field, "key"): field for field in items}
    ordered = [by_key[key] for key in STUDENT_FIELD_ORDER if key in by_key]
    ordered.extend(field for field in items if getattr(field, "key") not in STUDENT_FIELD_ORDER)
    return tuple(ordered)


def rows(section: str) -> tuple[StudentFieldRow, ...]:
    return tuple(row for row in STUDENT_FIELD_ROWS if row.section == section)
