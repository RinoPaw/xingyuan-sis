from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..view_common import identity, safe
from .birth_date_editor import display as display_birth_date
from .data import COLLECTIONS, Catalog
from .state import FieldSession, Form
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

CONFIRMATION_MODES = frozenset({"delete", "reset-password", "seed"})


@dataclass(frozen=True)
class ConfirmationContent:
    """Semantic confirmation details independent of terminal layout."""

    heading: str
    details: tuple[tuple[str, str], ...]
    notes: tuple[str, ...]
    warning: str
    confirm_label: str


def confirmation_content(catalog: Catalog, collection: str, form: Form) -> ConfirmationContent:
    """Describe every action-only confirmation using its actual effects."""
    if form.mode == "delete":
        return ConfirmationContent(
            heading=f"删除{COLLECTIONS[collection].title}",
            details=delete_identity(collection, form.original),
            notes=delete_impacts(catalog, collection, form.original),
            warning="删除后无法撤销",
            confirm_label="确认删除",
        )
    if form.mode == "reset-password":
        return ConfirmationContent(
            heading="重置学生密码",
            details=delete_identity("students", form.original),
            notes=("新密码为学号（旧密码失效）",),
            warning="下次登录须改密",
            confirm_label="确认重置",
        )
    if form.mode == "seed":
        return ConfirmationContent(
            heading="建立演示校园",
            details=(),
            notes=("写入演示学生、课程和选课", "仅支持空数据库"),
            warning="不会覆盖已有记录",
            confirm_label="确认建立",
        )
    raise ValueError(f"未知确认操作：{form.mode}")
