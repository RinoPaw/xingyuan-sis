"""CSV serialization and row-wise import, with writes delegated to the service."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import csv
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from typing import Any

from .schema import FIELDS

STUDENT_FIELDS = [
    "student_no", "name", "family", "branch", "gender", "birth_date", "age",
    "enrollment_year", "class_code", "status", "primary_element",
    "primary_affinity", "contact", "dormitory", "notes",
]


@dataclass(slots=True)
class ImportResult:
    imported: int
    errors: list[str]
    credentials: list[tuple[str, str]] = field(default_factory=list)


def export_students_csv(path: Path | str, rows: Iterable[Mapping[str, Any]]) -> int:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with target.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=STUDENT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in STUDENT_FIELDS})
            count += 1
    return count


def import_students_csv(
    path: Path | str,
    register_student: Callable[..., tuple[int, str]],
) -> ImportResult:
    errors: list[str] = []
    credentials: list[tuple[str, str]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"student_no", "name", "family", "branch", "enrollment_year"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV 缺少字段：{', '.join(sorted(missing))}")
        for row in reader:
            try:
                values = {field.key: row.get(field.key) or field.default for field in FIELDS["students"]}
                _, password = register_student(**values)
                credentials.append((str(values["student_no"]).strip(), password))
            except (ValueError, sqlite3.Error) as error:
                errors.append(f"第 {reader.line_num} 行：{error}")
    return ImportResult(imported=len(credentials), errors=errors, credentials=credentials)
