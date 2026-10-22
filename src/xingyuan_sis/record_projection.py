"""Resolve stable public codes from Repository read models, without UI coupling."""
from __future__ import annotations


def project_records(service, key, sources):
    """Project one collection with at most one lookup of each related table."""
    records = [dict(source) for source in sources]
    if key in ("majors", "courses") and any("department_code" not in row for row in records):
        departments = {row["id"]: row["code"] for row in service.list_departments()}
        for row in records:
            if "department_code" not in row:
                row["department_code"] = departments.get(row.get("department_id"))
    if key == "classes" and any("major_code" not in row for row in records):
        majors = {row["id"]: row["code"] for row in service.list_majors()}
        for row in records:
            if "major_code" not in row:
                row["major_code"] = majors.get(row.get("major_id"))
    return records


def project_record(service, key, source):
    return project_records(service, key, (source,))[0]
