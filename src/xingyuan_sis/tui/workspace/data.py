"""Records, forms and relationships shared by the terminal workspaces."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ...auth import Identity
from ...schema import FIELDS, Field, validate_values
from ...service import XingyuanService
from ...student_filters import query_students
from ...student_query import parse_student_query


@dataclass(frozen=True)
class Collection:
    title: str
    noun: str
    columns: tuple[tuple[str, str, int], ...]
    fields: tuple[Field, ...]
    views: tuple[str, ...] = ("全部",)


COLLECTIONS = {
    "students": Collection("学生", "学生档案", (
        ("name", "姓名", 10), ("student_no", "学号", 12), ("class_label", "班级", 20),
        ("primary_element", "元素", 6), ("status", "学籍", 8),
    ), FIELDS["students"], ()),
    "courses": Collection("课程", "课程目录", (
        ("name", "课程", 20), ("course_code", "编号", 10), ("credits", "学分", 6),
        ("hours", "课时", 6), ("enrolled", "选课", 6),
    ), FIELDS["courses"], ("全部课程", "已有选课", "暂无选课")),
    "grades": Collection("成绩", "选课与成绩", (
        ("student_name", "学生", 10), ("course_name", "课程", 20),
        ("score", "成绩", 8), ("semester", "学期", 16),
    ), FIELDS["grades"], ("全部选课", "待录入", "已评分")),
    "departments": Collection("学院", "学院", (
        ("name", "学院", 24), ("code", "编号", 10), ("children", "专业数", 8),
    ), FIELDS["departments"]),
    "majors": Collection("专业", "专业", (
        ("name", "专业", 22), ("code", "编号", 10), ("department_name", "学院", 24),
    ), FIELDS["majors"]),
    "classes": Collection("班级", "班级", (
        ("class_label", "班级", 22), ("code", "编号", 8), ("enrolled", "学生数", 8),
        ("department_name", "学院", 20),
    ), FIELDS["classes"]),
    "announcements": Collection("公告", "班级公告", (
        ("title", "标题", 24), ("class_label", "班级", 20), ("created_at", "发布时间", 20),
    ), FIELDS["announcements"], ()),
}
ACADEMICS = ("departments", "majors", "classes")


_STUDENT_ENUMS: dict[str, tuple[str, ...]] = {
    "status": ("在读", "休学", "保留学籍"),
    "gender": ("男", "女"),
    "primary_element": ("风", "水", "火", "雷", "岩", "光"),
    "primary_affinity": ("A", "B", "C"),
}


def _class_number(code: object | None, major_code: object | None) -> str | None:
    """Return the local class number from the canonical major-prefixed class code."""
    if code is None or code == "":
        return None
    text = str(code)
    prefix = "" if major_code is None else str(major_code)
    if prefix and text.startswith(prefix) and len(text) > len(prefix):
        return text[len(prefix):]
    return text


def _class_label(major_name: object | None, class_number: object | None) -> str | None:
    """Build the one user-facing class identity used throughout the TUI."""
    if major_name in {None, ""} and class_number in {None, ""}:
        return None
    if major_name in {None, ""}:
        return str(class_number)
    if class_number in {None, ""}:
        return str(major_name)
    return f"{major_name} · {class_number}"


class Catalog:
    def __init__(self, db_path: Path | str | None, identity: Identity | None = None):
        self.service = XingyuanService(db_path)
        self.identity = identity
        self.initial_password: str | None = None
        self.refresh()

    @property
    def read_only(self) -> bool:
        return self.identity is not None and not self.identity.is_admin

    def require_write(self) -> None:
        if self.read_only:
            raise ValueError("学生账户只能查询资料，个人信息仅允许修改自己的密码")

    def can_browse(self, key: str) -> bool:
        return not self.read_only or key in {"students", "grades", "announcements"}

    def refresh(self) -> None:
        service = self.service
        self.records = {key: [dict(row) for row in loader()] for key, loader in (
            ("students", service.list_students), ("courses", service.list_courses),
            ("grades", service.list_enrollments), ("departments", service.list_departments),
            ("majors", service.list_majors), ("classes", service.list_classes),
        )}
        self.records["announcements"] = [dict(row) for row in service.list_announcements(
            self.identity.student_no or "" if self.read_only else None
        )]
        self.species_families = [dict(row) for row in service.list_species_families()]
        self.species_branches = [dict(row) for row in service.list_species_branches()]
        departments = {row["id"]: row for row in self.records["departments"]}
        majors = {row["id"]: row for row in self.records["majors"]}
        classes = {row["id"]: row for row in self.records["classes"]}
        class_counts = Counter(row["class_id"] for row in self.records["students"])
        course_counts = Counter(row["course_id"] for row in self.records["grades"])
        major_counts = Counter(row["department_id"] for row in self.records["majors"])

        for row in self.records["classes"]:
            row["major_code"] = majors.get(row["major_id"], {}).get("code")
            row["enrolled"] = class_counts[row["id"]]

        self.class_numbers = {
            row["id"]: _class_number(row.get("code"), row.get("major_code"))
            for row in self.records["classes"]
        }
        self.class_labels = {
            row["id"]: _class_label(row.get("major_name"), self.class_numbers[row["id"]])
            for row in self.records["classes"]
        }

        for row in self.records["students"]:
            row["class_code"] = classes.get(row["class_id"], {}).get("code")
        for row in self.records["courses"] + self.records["majors"]:
            row["department_code"] = departments.get(row["department_id"], {}).get("code")
        for row in self.records["courses"]:
            row["enrolled"] = course_counts[row["id"]]
        for row in self.records["departments"]:
            row["children"] = major_counts[row["id"]]

    def _display_row(self, key: str, row: dict[str, Any]) -> dict[str, Any]:
        if key not in {"students", "classes", "announcements"}:
            return row
        class_id = row["id"] if key == "classes" else row.get("class_id")
        return row | {
            "class_number": self.class_numbers.get(class_id),
            "class_label": self.class_labels.get(class_id),
        }

    def rows(self, key: str, view: int = 0, query: str = "") -> list[dict[str, Any]]:
        rows = [self._display_row(key, row) for row in self.records[key]]
        if view:
            if key == "courses":
                rows = [row for row in rows if (row["enrolled"] > 0 if view == 1 else row["enrolled"] == 0)]
            elif key == "grades":
                rows = [row for row in rows if (row["score"] is None if view == 1 else row["score"] is not None)]

        if key == "students" and query.strip():
            parsed = parse_student_query(query)
            matched = {
                record.student_no
                for record in query_students(self.service, **parsed.as_kwargs())
            }
            return [row for row in rows if str(row["student_no"]) in matched]

        terms = query.casefold().split()
        return [row for row in rows if all(term in " ".join(
            str(value) for name, value in row.items() if name != "id" and not name.endswith("_id") and value is not None
        ).casefold() for term in terms)]

    def related(self, key: str, row: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        if key == "announcements":
            return "classes", [] if self.read_only else [
                r for r in self.records["classes"] if r["id"] == row["class_id"]
            ]
        if key in {"students", "courses"}:
            field = "student_id" if key == "students" else "course_id"
            return "grades", [r for r in self.records["grades"] if r[field] == row["id"]]
        if key == "grades":
            return "students", [r for r in self.records["students"] if r["id"] == row["student_id"]]
        child, field = {"departments": ("majors", "department_id"),
                        "majors": ("classes", "major_id"), "classes": ("students", "class_id")}[key]
        return child, [r for r in self.records[child] if r[field] == row["id"]]

    def distribution(self) -> list[tuple[str, int]]:
        return Counter(row["primary_element"] or "未登记" for row in self.records["students"]).most_common()

    def defaults(self, key: str, row: dict[str, Any] | None = None) -> dict[str, Any]:
        values = {field.key: (row.get(field.key) if row else field.default) for field in COLLECTIONS[key].fields}
        if not row and "enrollment_year" in values:
            values["enrollment_year"] = date.today().year
        return values

    def fields(self, key: str, editing: bool = False) -> tuple[Field, ...]:
        if editing and (self.read_only or key == "announcements"):
            return ()
        return tuple(f for f in COLLECTIONS[key].fields if not editing or f.editable)

    def options(
        self,
        key: str,
        field_key: str,
        values: dict[str, Any] | None = None,
    ) -> list[tuple[Any, str]] | None:
        field = next(f for f in COLLECTIONS[key].fields if f.key == field_key)

        if key == "students" and field_key in _STUDENT_ENUMS:
            options = [] if field.required else [(None, "未指定")]
            values = dict.fromkeys((*_STUDENT_ENUMS[field_key], *(
                row[field_key] for row in self.records["students"] if row.get(field_key)
            )))
            return options + [(value, value) for value in values]

        if key == "students" and field_key == "family":
            return [(row["name"], row["name"]) for row in self.species_families]

        if key == "students" and field_key == "branch":
            family = (values or {}).get("family")
            rows = self.species_branches
            if family:
                rows = [row for row in rows if row["family_name"] == family]
            return [
                (row["name"], row["name"] if family else f"{row['family_name']} · {row['name']}")
                for row in rows
            ]

        target = {("students", "class_code"): ("classes", "code", "name"),
                  ("announcements", "class_code"): ("classes", "code", "name"),
                  ("courses", "department_code"): ("departments", "code", "name"),
                  ("majors", "department_code"): ("departments", "code", "name"),
                  ("classes", "major_code"): ("majors", "code", "name"),
                  ("grades", "student_no"): ("students", "student_no", "name"),
                  ("grades", "course_code"): ("courses", "course_code", "name")}.get((key, field_key))
        if target is None:
            return None
        collection, identifier, label = target
        options = [] if field.required else [(None, "未指定")]
        return options + [(
            r[identifier],
            self.class_labels.get(r["id"]) if collection == "classes" else f"{r[label]} · {r[identifier]}",
        ) for r in self.records[collection]]

    def save(self, key: str, values: dict[str, Any], original: dict[str, Any] | None = None) -> int:
        self.require_write()
        self.initial_password = None
        changes = validate_values(key, values, partial=original is not None)
        values = self.defaults(key, original) | changes if original is not None else changes
        service = self.service
        if original is None and key == "students":
            record_id, self.initial_password = service.register_student(**values)
        elif original is None:
            create = {"courses": service.create_course,
                      "grades": service.add_grade, "departments": service.create_department,
                      "majors": service.create_major, "classes": service.create_class,
                      "announcements": service.create_announcement}[key]
            record_id = create(**values)
        else:
            record_id = original["id"]
            if key == "students":
                service.update_student_by_no(original["student_no"], **changes)
            elif key == "courses":
                service.update_course_by_code(original["course_code"], **values)
            elif key == "grades":
                service.update_grade(student_no=original["student_no"], course_code=original["course_code"],
                                     semester=original["semester"], new_semester=values["semester"], score=values["score"])
            elif key == "announcements":
                raise ValueError("公告发布后不能编辑；可删除后重新发布")
            else:
                values["new_code"] = values.pop("code")
                update = {"departments": service.update_department_by_code,
                          "majors": service.update_major_by_code, "classes": service.update_class_by_code}[key]
                update(original["code"], **values)
        self.refresh()
        return record_id

    def delete(self, key: str, row: dict[str, Any]) -> None:
        self.require_write()
        service = self.service
        if key == "announcements":
            service.delete_announcement(row["id"])
        elif key == "grades":
            service.delete_grade(**{name: row[name] for name in ("student_no", "course_code", "semester")})
        else:
            delete, identifier = {
                "students": (service.delete_student_by_no, "student_no"),
                "courses": (service.delete_course_by_code, "course_code"),
                "departments": (service.delete_department_by_code, "code"),
                "majors": (service.delete_major_by_code, "code"),
                "classes": (service.delete_class_by_code, "code"),
            }[key]
            delete(str(row[identifier]))
        self.refresh()
