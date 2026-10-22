"""Resolve stable public codes from Repository read models, without UI coupling."""
from __future__ import annotations


def project_record(service, key, source):
    row = dict(source)
    if key in ("majors", "courses") and "department_code" not in row:
        departments = {r["id"]: r["code"] for r in service.list_departments()}
        row["department_code"] = departments.get(row.get("department_id"))
    if key == "classes" and "major_code" not in row:
        majors = {r["id"]: r["code"] for r in service.list_majors()}
        row["major_code"] = majors.get(row.get("major_id"))
    return row
