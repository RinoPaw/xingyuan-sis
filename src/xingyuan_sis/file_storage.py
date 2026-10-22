"""Runnable memory → JSON → SQLite stages sharing the existing Service rules.

The alternative repositories model persistence and relationships only. Portable
archives deliberately exclude password hashes; importing provisions initial
credentials using Service.register_student, just like CSV import.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .schema import FIELDS
from .record_projection import project_record

TABLES = ("departments", "majors", "classes", "species_families", "species_branches",
          "students", "courses", "enrollments", "announcements")
PORTABLE = ("departments", "majors", "classes", "families", "branches", "students", "courses", "grades", "announcements")
RELATIONS = {
    "majors": {"department_id": ("departments", "restrict", True)},
    "classes": {"major_id": ("majors", "restrict", True)},
    "species_branches": {"family_id": ("species_families", "restrict", True)},
    "students": {"species_family_id": ("species_families", "restrict", True),
        "species_branch_id": ("species_branches", "restrict", False), "class_id": ("classes", "null", False)},
    "courses": {"department_id": ("departments", "null", False)},
    "enrollments": {"student_id": ("students", "cascade", True), "course_id": ("courses", "cascade", True)},
    "announcements": {"class_id": ("classes", "cascade", True)},
}
UNIQUE = {"departments": (("code",), ("name",)), "majors": (("code",), ("name", "department_id")),
    "classes": (("code",), ("name", "major_id", "enrollment_year")), "species_families": (("name",),),
    "species_branches": (("name", "family_id"),), "students": (("student_no",),),
    "courses": (("course_code",),), "enrollments": (("student_id", "course_id", "semester"),)}


def write_json_atomic(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as handle:
            temp_name = handle.name
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name is not None and Path(temp_name).exists():
            Path(temp_name).unlink()


class MemoryRepository:
    """Plain Python records, no hidden SQLite file or SQL engine."""
    db_path = None

    def __init__(self):
        self.data = {key: [] for key in TABLES}

    def _commit(self):
        pass

    def _validate(self):
        for table, records in self.data.items():
            for keys in UNIQUE.get(table, ()):
                values = [tuple(r.get(k) for k in keys) for r in records]
                if len(values) != len(set(values)):
                    raise sqlite3.IntegrityError("UNIQUE constraint failed: " + table)
            for field, (target, _, required) in RELATIONS.get(table, {}).items():
                ids = {r["id"] for r in self.data[target]}
                if any((r.get(field) is None and required) or (r.get(field) is not None and r[field] not in ids) for r in records):
                    raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")

    def _mutate(self, action):
        previous = deepcopy(self.data)
        try:
            result = action()
            self._validate()
            self._commit()
            return result
        except Exception:
            self.data = previous
            raise

    def _add(self, table, values):
        def action():
            identity = max((r["id"] for r in self.data[table]), default=0) + 1
            row = {"id": identity, **values}
            if table == "students":
                row["must_change_password"] = 1
            if table == "announcements":
                row.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.data[table].append(row)
            return identity
        return self._mutate(action)

    def _update(self, table, identity, values):
        return self._mutate(lambda: next(r for r in self.data[table] if r["id"] == identity).update(values))

    def _remove(self, table, identity):
        def cascade(target, item_id):
            for source, fields in RELATIONS.items():
                for field, (destination, behavior, _) in fields.items():
                    if destination != target:
                        continue
                    for row in list(self.data[source]):
                        if row.get(field) != item_id:
                            continue
                        if behavior == "restrict":
                            raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")
                        if behavior == "null":
                            row[field] = None
                        else:
                            cascade(source, row["id"])
            self.data[target] = [r for r in self.data[target] if r["id"] != item_id]
        self._mutate(lambda: cascade(table, identity))

    def _row(self, table, identity):
        return next((r for r in self.data[table] if r["id"] == identity), {})

    def _list(self, table):
        rows = []
        for source in self.data[table]:
            row = dict(source)
            if table in ("majors", "courses"):
                d = self._row("departments", row.get("department_id"))
                row.update(department_code=d.get("code"), department_name=d.get("name"))
            if table == "classes":
                major = self._row("majors", row.get("major_id"))
                dept = self._row("departments", major.get("department_id"))
                row.update(major_code=major.get("code"), major_name=major.get("name"), department_code=dept.get("code"), department_name=dept.get("name"))
            if table == "species_branches":
                row["family_name"] = self._row("species_families", row["family_id"]).get("name")
            if table == "students":
                family = self._row("species_families", row["species_family_id"])
                branch = self._row("species_branches", row.get("species_branch_id"))
                cls = next((c for c in self._list("classes") if c["id"] == row.get("class_id")), {})
                row.update(family=family.get("name"), branch=branch.get("name"), class_code=cls.get("code"), class_name=cls.get("name"))
                row.update({k: cls.get(k) for k in ("major_code", "major_name", "department_code", "department_name")})
                row.pop("password_hash", None)
                row.pop("must_change_password", None)
            if table == "enrollments":
                student = self._row("students", row["student_id"])
                course = self._row("courses", row["course_id"])
                row.update(student_no=student.get("student_no"), student_name=student.get("name"), course_code=course.get("course_code"), course_name=course.get("name"))
            if table == "announcements":
                cls = self._row("classes", row["class_id"])
                row.update(class_code=cls.get("code"), class_name=cls.get("name"))
            rows.append(row)
        return rows

    def __getattr__(self, name):
        # Mechanical CRUD mapping; Service continues to own field validation.
        definitions = {
            "department": ("departments", ("code", "name")),
            "major": ("majors", ("code", "name", "department_id")),
            "class": ("classes", ("code", "name", "major_id", "enrollment_year")),
            "species_family": ("species_families", ("name",)),
            "species_branch": ("species_branches", ("name", "family_id")),
            "course": ("courses", ("course_code", "name", "department_id", "credits", "hours")),
            "enrollment": ("enrollments", ("student_id", "course_id", "semester", "score")),
            "announcement": ("announcements", ("title", "body", "class_id")),
        }
        if name.startswith("list_") and name[5:] in TABLES:
            return lambda: self._list(name[5:])
        for prefix in ("add_", "update_", "delete_"):
            kind = name.removeprefix(prefix)
            if not name.startswith(prefix) or kind not in definitions:
                continue
            table, columns = definitions[kind]
            if prefix == "add_":
                return lambda *args, **kw: self._add(table, dict(zip(columns, args)) | kw)
            if prefix == "update_":
                if kind == "enrollment":
                    columns = ("semester", "score")
                return lambda identity, *args, **kw: self._update(table, identity, dict(zip(columns, args)) | kw)
            return lambda identity: self._remove(table, identity)
        finds = {
            "find_department_by_code": ("departments", "code"), "find_major_by_code": ("majors", "code"),
            "find_class_by_code": ("classes", "code"), "find_course_by_code": ("courses", "course_code"),
            "find_student_by_no": ("students", "student_no"), "find_species_family_by_name": ("species_families", "name"),
        }
        if name in finds:
            table, key = finds[name]
            return lambda value: next((r for r in self._list(table) if r[key] == value.strip()), None)
        raise AttributeError(name)

    def list_students(self, keyword=""):
        return [r for r in self._list("students") if not keyword or keyword in str(r)]

    def add_student(self, **values):
        return self._add("students", values)

    def update_student(self, identity, **values):
        self._update("students", identity, values)

    def delete_student(self, identity):
        self._remove("students", identity)

    def find_species_branch_by_name(self, branch, family=None):
        return next((r for r in self._list("species_branches") if r["name"] == branch and (family is None or r["family_name"] == family)), None)

    def list_announcements(self, student_no=None):
        rows = self._list("announcements")
        if student_no is None:
            return rows
        student = self.find_student_by_no(student_no)
        return [r for r in rows if student and student.get("class_id") == r["class_id"]]

    def list_enrollments(self, keyword=""):
        return [r for r in self._list("enrollments") if not keyword or keyword in str(r)]

    def list_enrollments_for_student(self, no):
        return [r for r in self._list("enrollments") if r["student_no"] == no]

    def list_enrollments_for_course(self, code):
        return [r for r in self._list("enrollments") if r["course_code"] == code]

    def find_enrollment(self, no, code, semester):
        return next((r for r in self._list("enrollments") if (r["student_no"], r["course_code"], r["semester"]) == (no, code, semester)), None)

    def restore_archive(self, data):
        if any(self.data.values()):
            raise ValueError("仅允许向空库导入完整档案")
        def action():
            self.data = deepcopy(data)
        self._mutate(action)


class JsonRepository(MemoryRepository):
    def __init__(self, path):
        super().__init__()
        self.path = Path(path)
        if self.path.exists():
            self.data = read_archive(self.path)

    def _commit(self):
        from .service import XingyuanService
        export_archive(XingyuanService(repository=self), self.path)


def archive_payload(service):
    records = {}
    reads = {"families": service.list_species_families, "branches": service.list_species_branches,
             "grades": service.list_enrollments}
    for key in PORTABLE:
        reader = reads.get(key) or getattr(service, f"list_{key}")
        if key == "families":
            records[key] = [{"name": row["name"]} for row in reader()]
        elif key == "branches":
            records[key] = [{"name": row["name"], "family": row["family_name"]} for row in reader()]
        else:
            rows = [project_record(service, key, row) for row in reader()]
            records[key] = [{f.key: row[f.key] for f in FIELDS[key]} | ({"created_at": row["created_at"]} if key == "announcements" else {}) for row in rows]
    return {"format": "xingyuan-campus", "version": 1, "records": records}


def export_archive(service, path):
    write_json_atomic(path, archive_payload(service))


def read_archive(path):
    from .service import XingyuanService
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError("不是有效的 UTF-8 校园 JSON 文件") from error
    if not isinstance(payload, dict) or payload.get("format") != "xingyuan-campus" or payload.get("version") != 1:
        raise ValueError("不支持的校园档案格式或版本")
    records = payload.get("records")
    if not isinstance(records, dict) or set(records) != set(PORTABLE):
        raise ValueError("校园档案必须包含全部资料集合")
    memory = MemoryRepository()
    service = XingyuanService(repository=memory)
    methods = {"departments": service.create_department, "majors": service.create_major,
        "classes": service.create_class, "families": service.create_species_family,
        "branches": service.create_species_branch, "students": service.register_student,
        "courses": service.create_course, "grades": service.add_grade, "announcements": service.create_announcement}
    for key in PORTABLE:
        if not isinstance(records[key], list):
            raise ValueError(f"{key} 必须是记录列表")
        for row in records[key]:
            if not isinstance(row, dict):
                raise ValueError(f"{key} 包含无效记录")
            values = dict(row)
            created_at = values.pop("created_at", None) if key == "announcements" else None
            if created_at is not None:
                try:
                    datetime.fromisoformat(created_at)
                except (ValueError, TypeError):
                    raise ValueError("公告发布时间无效") from None
            try:
                identity = methods[key](**values)
            except TypeError as error:
                raise ValueError(f"{key} 的字段不完整或包含未知字段") from error
            if created_at is not None:
                memory._row("announcements", identity)["created_at"] = created_at
    return memory.data
