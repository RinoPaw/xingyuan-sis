from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .database import connect

STUDENT_FIELDS = [
    "student_no", "name", "family", "branch", "gender", "birth_date",
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
            SELECT s.student_no, s.name, s.family, s.branch, s.gender,
                   s.birth_date, s.enrollment_year, c.code AS class_code,
                   s.status, s.primary_element, s.primary_affinity,
                   s.contact, s.dormitory, s.notes
            FROM students AS s
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
                    class_code = (row.get("class_code") or "").strip()
                    class_id = None
                    if class_code:
                        class_row = connection.execute(
                            "SELECT id FROM classes WHERE code = ?",
                            (class_code,),
                        ).fetchone()
                        if class_row is None:
                            raise ValueError(f"班级编号不存在：{class_code}")
                        class_id = class_row[0]

                    connection.execute(
                        """
                        INSERT INTO students(
                            student_no, name, family, branch, gender, birth_date,
                            enrollment_year, class_id, status,
                            primary_element, primary_affinity,
                            contact, dormitory, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _required(row, "student_no"),
                            _required(row, "name"),
                            _required(row, "family"),
                            _required(row, "branch"),
                            _optional(row.get("gender")),
                            _optional(row.get("birth_date")),
                            int(_required(row, "enrollment_year")),
                            class_id,
                            (row.get("status") or "在读").strip() or "在读",
                            _optional(row.get("primary_element")),
                            _optional(row.get("primary_affinity")),
                            _optional(row.get("contact")),
                            _optional(row.get("dormitory")),
                            _optional(row.get("notes")),
                        ),
                    )
                    imported += 1
                except (ValueError, sqlite3.Error) as error:
                    errors.append(f"第 {line_number} 行：{error}")

    return ImportResult(imported=imported, errors=errors)


def _required(row: dict[str, str | None], key: str) -> str:
    value = (row.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} 不能为空")
    return value


def _optional(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None
