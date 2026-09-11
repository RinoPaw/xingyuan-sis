from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import connect


def summary(db_path: Path | str | None = None) -> dict[str, Any]:
    with connect(db_path) as connection:
        counts = {}
        for key, table in (
            ("students", "students"),
            ("departments", "departments"),
            ("majors", "majors"),
            ("classes", "classes"),
            ("courses", "courses"),
            ("enrollments", "enrollments"),
        ):
            counts[key] = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
        row = connection.execute(
            "SELECT ROUND(AVG(score), 2), MAX(score), MIN(score) "
            "FROM enrollments WHERE score IS NOT NULL"
        ).fetchone()
        counts["average_score"] = row[0]
        counts["max_score"] = row[1]
        counts["min_score"] = row[2]
        return counts


def class_student_counts(db_path: Path | str | None = None):
    with connect(db_path) as connection:
        return list(
            connection.execute(
                """
                SELECT c.code, c.name, m.name AS major_name, COUNT(s.id) AS student_count
                FROM classes AS c
                JOIN majors AS m ON m.id = c.major_id
                LEFT JOIN students AS s ON s.class_id = c.id
                GROUP BY c.id
                ORDER BY c.enrollment_year DESC, c.code
                """
            ).fetchall()
        )


def element_distribution(db_path: Path | str | None = None):
    with connect(db_path) as connection:
        return list(
            connection.execute(
                """
                SELECT primary_element AS element, COUNT(*) AS student_count
                FROM students
                WHERE primary_element IS NOT NULL AND TRIM(primary_element) <> ''
                GROUP BY primary_element
                ORDER BY student_count DESC, primary_element
                """
            ).fetchall()
        )


def course_score_stats(db_path: Path | str | None = None):
    with connect(db_path) as connection:
        return list(
            connection.execute(
                """
                SELECT c.course_code, c.name,
                       COUNT(e.score) AS graded_count,
                       ROUND(AVG(e.score), 2) AS average_score,
                       MAX(e.score) AS max_score,
                       MIN(e.score) AS min_score
                FROM courses AS c
                LEFT JOIN enrollments AS e ON e.course_id = c.id
                GROUP BY c.id
                ORDER BY c.course_code
                """
            ).fetchall()
        )
