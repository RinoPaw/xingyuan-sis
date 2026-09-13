"""Records, forms and relationships shared by the terminal workspaces."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ..schema import FIELDS, Field
from ..service import XingyuanService
from ..student_filters import query_students
from ..student_query import parse_student_query


@dataclass(frozen=True)
class Collection:
    title: str
    noun: str
    columns: tuple[tuple[str, str, int], ...]
    fields: tuple[Field, ...]
    views: tuple[str, ...] = ("全部",)


COLLECTIONS = {
    "students": Collection("学生", "学生档案", (
        ("name", "姓名", 10), ("student_no", "学号", 12), ("class_name", "班级", 20),
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
        ("name", "班级", 22), ("code", "编号", 8), ("enrolled", "学生数", 8),
        ("major_name", "专业", 20),
    ), FIELDS["classes"]),
}
ACADEMICS = ("departments", "majors", "classes")


_STUDENT_ENUMS: dict[str, tuple[str, ...]] = {
    "status": ("在读", "休学", "保留学籍"),
    "gender": ("男", "女"),
    "primary_element": ("风", "水", "火", "雷", "岩", "光"),
    "primary_affinity": ("A", "B", "C"),
}


class Catalog:
    def __init__(self, db_path: Path | str | None):
        self.service = XingyuanService(db_path)
        self.refresh()

    def refresh(self) -> None:
        service = self.service
        self.records = {key: [dict(row) for row in loader()] for key, loader in (
            ("students", service.list_students), ("courses", service.list_courses),
            ("grades", service.list_enrollments), ("departments", service.list_departments),
            ("majors", service.list_majors), ("classes", service.list_classes),
        )}
        self.species_families = [dict(row) for row in service.list_species_families()]
        self.species_branches = [dict(row) for row in service.list_species_branches()]
        departments = {row["id"]: row for row in self.records["departments"]}
        majors = {row["id"]: row for row in self.records["majors"]}
        classes = {row["id"]: row for row in self.records["classes"]}
        class_counts = Counter(row["class_id"] for row in self.records["students"])
        course_counts = Counter(row["course_id"] for row in self.records["grades"])
        major_counts = Counter(row["department_id"] for row in self.records["majors"])
        for row in self.records["students"]:
            row["class_code"] = classes.get(row["class_id"], {}).get("code")
        for row in self.records["courses"] + self.records["majors"]:
            row["department_code"] = departments.get(row["department_id"], {}).get("code")
        for row in self.records["classes"]:
            row["major_code"] = majors.get(row["major_id"], {}).get("code")
            row["enrolled"] = class_counts[row["id"]]
        for row in self.records["courses"]:
            row["enrolled"] = course_counts[row["id"]]
        for row in self.records["departments"]:
            row["children"] = major_counts[row["id"]]

    def rows(self, key: str, view: int = 0, query: str = "") -> list[dict[str, Any]]:
        rows = self.records[key]
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

    def metrics(self, key: str) -> list[tuple[str, str]]:
        rows = self.records.get(key, [])
        if key == "students":
            return [("学生", str(len(rows))), ("在读", str(sum(r["status"] == "在读" for r in rows))),
                    ("未分班", str(sum(r["class_id"] is None for r in rows)))]
        if key == "courses":
            return [("课程", str(len(rows))), ("学分合计", f"{sum(r['credits'] for r in rows):g}"),
                    ("选课记录", str(len(self.records["grades"])))]
        if key == "grades":
            scores = [r["score"] for r in rows if r["score"] is not None]
            return [("选课", str(len(rows))), ("待录入", str(len(rows) - len(scores))),
                    ("平均分", f"{sum(scores) / len(scores):.1f}" if scores else "—")]
        return [(COLLECTIONS[k].noun, str(len(self.records[k]))) for k in ACADEMICS]

    def related(self, key: str, row: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
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
        # An enrollment's student/course remain attached while editing its score.
        return tuple(f for f in COLLECTIONS[key].fields if not (key == "grades" and editing and f.key in {"student_no", "course_code"}))

    def options(
        self,
        key: str,
        field_key: str,
        values: dict[str, Any] | None = None,
    ) -> list[tuple[Any, str]] | None:
        field = next(f for f in COLLECTIONS[key].fields if f.key == field_key)

        if key == "students" and field_key in _STUDENT_ENUMS:
            options = [] if field.required else [(None, "未指定")]
            return options + [(value, value) for value in _STUDENT_ENUMS[field_key]]

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
                  ("courses", "department_code"): ("departments", "code", "name"),
                  ("majors", "department_code"): ("departments", "code", "name"),
                  ("classes", "major_code"): ("majors", "code", "name"),
                  ("grades", "student_no"): ("students", "student_no", "name"),
                  ("grades", "course_code"): ("courses", "course_code", "name")}.get((key, field_key))
        if target is None:
            return None
        collection, identifier, label = target
        options = [] if field.required else [(None, "未指定")]
        return options + [(r[identifier], f"{r[label]} · {r[identifier]}") for r in self.records[collection]]

    def save(self, key: str, values: dict[str, Any], original: dict[str, Any] | None = None) -> int:
        values = {field.key: field.parse(values.get(field.key)) for field in COLLECTIONS[key].fields}
        service = self.service
        if original is None:
            create = {"students": service.create_student, "courses": service.create_course,
                      "grades": service.add_grade, "departments": service.create_department,
                      "majors": service.create_major, "classes": service.create_class}[key]
            record_id = create(**values)
        else:
            record_id = original["id"]
            if key == "students":
                service.update_student_by_no(original["student_no"], **values)
            elif key == "courses":
                service.update_course_by_code(original["course_code"], **values)
            elif key == "grades":
                service.update_grade(student_no=original["student_no"], course_code=original["course_code"],
                                     semester=original["semester"], new_semester=values["semester"], score=values["score"])
            else:
                values["new_code"] = values.pop("code")
                update = {"departments": service.update_department_by_code,
                          "majors": service.update_major_by_code, "classes": service.update_class_by_code}[key]
                update(original["code"], **values)
        self.refresh()
        return record_id

    def delete(self, key: str, row: dict[str, Any]) -> None:
        service = self.service
        if key == "grades":
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
