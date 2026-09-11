from __future__ import annotations

from pathlib import Path
import sqlite3

from .database import connect


def get_student_profile(
    student_id: int,
    db_path: Path | str | None = None,
) -> sqlite3.Row | None:
    with connect(db_path) as connection:
        return connection.execute(
            """
            SELECT s.id, s.student_no, s.name, s.family, s.branch,
                   s.gender, s.birth_date, s.enrollment_year, s.status,
                   s.primary_element, s.primary_affinity,
                   s.contact, s.dormitory, s.notes,
                   c.name AS class_name,
                   m.name AS major_name,
                   d.name AS department_name
            FROM students AS s
            LEFT JOIN classes AS c ON c.id = s.class_id
            LEFT JOIN majors AS m ON m.id = c.major_id
            LEFT JOIN departments AS d ON d.id = m.department_id
            WHERE s.id = ?
            """,
            (student_id,),
        ).fetchone()


def list_student_enrollments(
    student_id: int,
    db_path: Path | str | None = None,
) -> list[sqlite3.Row]:
    with connect(db_path) as connection:
        return list(
            connection.execute(
                """
                SELECT e.id, e.semester, e.score,
                       c.course_code, c.name AS course_name, c.credits
                FROM enrollments AS e
                JOIN courses AS c ON c.id = e.course_id
                WHERE e.student_id = ?
                ORDER BY e.semester DESC, c.course_code
                """,
                (student_id,),
            ).fetchall()
        )
