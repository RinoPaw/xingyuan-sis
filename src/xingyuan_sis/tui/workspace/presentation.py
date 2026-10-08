from __future__ import annotations

from typing import Any, Mapping

from ..view_common import identity, safe
from .birth_date_editor import display as display_birth_date
from .data import Catalog
from .state import FieldSession
from .student_layout import STUDENT_FIELD_ROWS


_COMPOSITE_FIELDS = frozenset(
    key for row in STUDENT_FIELD_ROWS if len(row.keys) > 1 for key in row.keys
)


def project_record(
    row: Mapping[str, Any],
    session: FieldSession | None = None,
) -> dict[str, Any]:
    """Return the one record projection consumed by every inspector formatter."""
    values = dict(row)
    if session is None:
        return values
    source = session.values if session.preview_values is None else session.preview_values
    for field in session.fields:
        values[field.key] = source.get(field.key)
    return values


def display_value(
    catalog: Catalog,
    collection: str,
    values: Mapping[str, Any],
    field_key: str,
) -> str:
    """Format stored, relationship and display-only attributes through one path."""
    value = values.get(field_key)
    if collection == "students" and field_key in _COMPOSITE_FIELDS and value in (None, ""):
        return "未指定"
    if collection == "students" and field_key == "birth_date":
        return display_birth_date(value)
    options = catalog.options(collection, field_key, dict(values))
    if options is not None:
        return next((label for option, label in options if option == value), safe(value))
    return safe(value)


def display_semantic_fields(
    catalog: Catalog,
    collection: str,
    values: Mapping[str, Any],
    field_keys: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    """Retain every semantic subfield and its hit target, including unset ones.

    Composite rows have a stable shape: an unset child is still visible and
    independently focusable. Only a standalone empty field uses the compact
    em-dash placeholder.
    """
    return tuple(
        (key, display_value(catalog, collection, values, key))
        for key in field_keys
    )


def delete_identity(collection: str, row: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Return collection-specific names for the two identity values."""
    first, second = identity(collection, dict(row))
    labels = {
        "students": ("姓名", "学号"),
        "courses": ("课程", "编号"),
        "grades": ("学生", "课程 / 学期"),
        "departments": ("学院", "编号"),
        "majors": ("专业", "编号"),
        "classes": ("班级", "编号"),
        "announcements": ("标题", "班级 / 编号"),
    }[collection]
    return tuple(zip(labels, (first, second)))


def delete_impacts(
    catalog: Catalog,
    collection: str,
    row: Mapping[str, Any],
) -> tuple[str, ...]:
    """State actual cascades and relationship changes without generic filler."""
    record = dict(row)
    if collection in {"students", "courses"}:
        _, related = catalog.related(collection, record)
        return (f"同时删除 {len(related)} 条选课记录（含成绩）",) if related else ()
    if collection == "classes":
        _, students = catalog.related(collection, record)
        notices = sum(
            notice["class_id"] == record["id"]
            for notice in catalog.records["announcements"]
        )
        impacts: list[str] = []
        if students:
            impacts.append(f"{len(students)} 名学生将解除班级关联")
        if notices:
            impacts.append(f"同时删除 {notices} 条班级公告")
        return tuple(impacts)
    return ()
