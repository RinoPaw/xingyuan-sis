from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

from .database import connect
from .schema import FIELDS, is_complete_birth_date, validate_values

STUDENT_FIELDS = [
    "student_no", "name", "family", "branch", "gender", "birth_date", "age",
    "enrollment_year", "class_code", "status", "primary_element",
    "primary_affinity", "contact", "dormitory", "notes",
]


@dataclass(slots=True)
class ImportResult:
    imported: int
    errors: list[str]


def export_students_csv(
    path: Path | str,
    db_path: Path | str | None = None,
) -> int:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT s.student_no, s.name,
                   f.name AS family, b.name AS branch,
                   s.gender, s.birth_date, s.age, s.enrollment_year,
                   c.code AS class_code, s.status,
                   s.primary_element, s.primary_affinity,
                   s.contact, s.dormitory, s.notes
            FROM students AS s
            JOIN species_branches AS b ON b.id = s.species_branch_id
            JOIN species_families AS f ON f.id = b.family_id
            LEFT JOIN classes AS c ON c.id = s.class_id
            ORDER BY s.student_no
            """
        ).fetchall()

    with target.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=STUDENT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in STUDENT_FIELDS})
    return len(rows)


def import_students_csv(
    path: Path | str,
    db_path: Path | str | None = None,
) -> ImportResult:
    source = Path(path)
    errors: list[str] = []
    imported = 0

    with source.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        headers = set(reader.fieldnames or ())
        required = {"student_no", "name", "family", "branch", "enrollment_year"}
        missing = required - headers
        if missing:
            raise ValueError(f"CSV 缺少字段：{', '.join(sorted(missing))}")

        with connect(db_path) as connection:
            for line_number, row in enumerate(reader, start=2):
                try:
                    values = validate_values("students", {
                        field.key: (row.get(field.key) or field.default)
                        for field in FIELDS["students"]
                    })
                    if is_complete_birth_date(values["birth_date"]):
                        values["age"] = None
                    class_code = (values.get("class_code") or "").strip()
                    class_id = None
                    if class_code:
                        class_row = connection.execute(
                            "SELECT id FROM classes WHERE code = ?",
                            (class_code,),
                        ).fetchone()
                        if class_row is None:
                            raise ValueError(f"班级编号不存在：{class_code}")
                        class_id = int(class_row[0])

                    family = _required(values, "family")
                    branch = _required(values, "branch")
                    branch_row = connection.execute(
                        """
                        SELECT b.id
                        FROM species_branches AS b
                        JOIN species_families AS f ON f.id = b.family_id
                        WHERE f.name = ? AND b.name = ?
                        """,
                        (family, branch),
                    ).fetchone()
                    if branch_row is None:
                        raise ValueError(f"种族支系不存在：{family} · {branch}")

                    connection.execute(
                        """
                        INSERT INTO students(
                            student_no, name, species_branch_id, gender, birth_date, age,
                            enrollment_year, class_id, status,
                            primary_element, primary_affinity,
                            contact, dormitory, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _required(values, "student_no"),
                            _required(values, "name"),
                            int(branch_row[0]),
                            _optional(values.get("gender")),
                            _optional(values.get("birth_date")),
                            values.get("age"),
                            values["enrollment_year"],
                            class_id,
                            (values.get("status") or "在读").strip() or "在读",
                            _optional(values.get("primary_element")),
                            _optional(values.get("primary_affinity")),
                            _optional(values.get("contact")),
                            _optional(values.get("dormitory")),
                            _optional(values.get("notes")),
                        ),
                    )
                    imported += 1
                except (ValueError, sqlite3.Error) as error:
                    errors.append(f"第 {line_number} 行：{error}")

    return ImportResult(imported=imported, errors=errors)


def _required(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{key} 不能为空")
    return text


def _optional(value: Any) -> str | None:
    text = "" if value is None else str(value).strip()
    return text or None
