from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Iterable

from .database import connect


class Repository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = db_path

    def _fetch_all(self, sql: str, parameters: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with connect(self.db_path) as connection:
            return list(connection.execute(sql, tuple(parameters)).fetchall())

    def _fetch_one(self, sql: str, parameters: Iterable[Any] = ()) -> sqlite3.Row | None:
        with connect(self.db_path) as connection:
            return connection.execute(sql, tuple(parameters)).fetchone()

    def _execute(self, sql: str, parameters: Iterable[Any] = ()) -> int:
        with connect(self.db_path) as connection:
            cursor = connection.execute(sql, tuple(parameters))
            return int(cursor.lastrowid or 0)

    # 学院
    def list_departments(self) -> list[sqlite3.Row]:
        return self._fetch_all("SELECT id, code, name FROM departments ORDER BY code")

    def find_department_by_code(self, code: str) -> sqlite3.Row | None:
        return self._fetch_one(
            "SELECT id, code, name FROM departments WHERE code = ?",
            (code.strip(),),
        )

    def add_department(self, code: str, name: str) -> int:
        return self._execute(
            "INSERT INTO departments(code, name) VALUES (?, ?)",
            (code.strip(), name.strip()),
        )

    def update_department(self, department_id: int, code: str, name: str) -> None:
        self._execute(
            "UPDATE departments SET code = ?, name = ? WHERE id = ?",
            (code.strip(), name.strip(), department_id),
        )

    def delete_department(self, department_id: int) -> None:
        self._execute("DELETE FROM departments WHERE id = ?", (department_id,))

    # 专业
    def list_majors(self) -> list[sqlite3.Row]:
        return self._fetch_all(
            """
            SELECT m.id, m.code, m.name, m.department_id, d.name AS department_name
            FROM majors AS m
            JOIN departments AS d ON d.id = m.department_id
            ORDER BY d.code, m.code
            """
        )

    def find_major_by_code(self, code: str) -> sqlite3.Row | None:
        return self._fetch_one(
            """
            SELECT m.id, m.code, m.name, m.department_id, d.name AS department_name
            FROM majors AS m
            JOIN departments AS d ON d.id = m.department_id
            WHERE m.code = ?
            """,
            (code.strip(),),
        )

    def add_major(self, code: str, name: str, department_id: int) -> int:
        return self._execute(
            "INSERT INTO majors(code, name, department_id) VALUES (?, ?, ?)",
            (code.strip(), name.strip(), department_id),
        )

    def update_major(self, major_id: int, code: str, name: str, department_id: int) -> None:
        self._execute(
            "UPDATE majors SET code = ?, name = ?, department_id = ? WHERE id = ?",
            (code.strip(), name.strip(), department_id, major_id),
        )

    def delete_major(self, major_id: int) -> None:
        self._execute("DELETE FROM majors WHERE id = ?", (major_id,))

    # 班级
    def list_classes(self) -> list[sqlite3.Row]:
        return self._fetch_all(
            """
            SELECT c.id, c.code, c.name, c.major_id, c.enrollment_year,
                   m.name AS major_name, d.name AS department_name
            FROM classes AS c
            JOIN majors AS m ON m.id = c.major_id
            JOIN departments AS d ON d.id = m.department_id
            ORDER BY c.enrollment_year DESC, c.code
            """
        )

    def find_class_by_code(self, code: str) -> sqlite3.Row | None:
        return self._fetch_one(
            """
            SELECT c.id, c.code, c.name, c.major_id, c.enrollment_year,
                   m.name AS major_name, d.name AS department_name
            FROM classes AS c
            JOIN majors AS m ON m.id = c.major_id
            JOIN departments AS d ON d.id = m.department_id
            WHERE c.code = ?
            """,
            (code.strip(),),
        )

    def add_class(self, code: str, name: str, major_id: int, enrollment_year: int) -> int:
        return self._execute(
            "INSERT INTO classes(code, name, major_id, enrollment_year) VALUES (?, ?, ?, ?)",
            (code.strip(), name.strip(), major_id, enrollment_year),
        )

    def update_class(
        self,
        class_id: int,
        code: str,
        name: str,
        major_id: int,
        enrollment_year: int,
    ) -> None:
        self._execute(
            """
            UPDATE classes
            SET code = ?, name = ?, major_id = ?, enrollment_year = ?
            WHERE id = ?
            """,
            (code.strip(), name.strip(), major_id, enrollment_year, class_id),
        )

    def delete_class(self, class_id: int) -> None:
        self._execute("DELETE FROM classes WHERE id = ?", (class_id,))

    # 种族族系
    def list_species_families(self) -> list[sqlite3.Row]:
        return self._fetch_all(
            "SELECT id, name FROM species_families ORDER BY name"
        )

    def find_species_family_by_name(self, name: str) -> sqlite3.Row | None:
        return self._fetch_one(
            "SELECT id, name FROM species_families WHERE name = ?",
            (name.strip(),),
        )

    def add_species_family(self, name: str) -> int:
        return self._execute(
            "INSERT INTO species_families(name) VALUES (?)",
            (name.strip(),),
        )

    def update_species_family(self, family_id: int, name: str) -> None:
        self._execute(
            "UPDATE species_families SET name = ? WHERE id = ?",
            (name.strip(), family_id),
        )

    def delete_species_family(self, family_id: int) -> None:
        self._execute("DELETE FROM species_families WHERE id = ?", (family_id,))

    # 种族支系
    def list_species_branches(self) -> list[sqlite3.Row]:
        return self._fetch_all(
            """
            SELECT b.id, b.name, b.family_id, f.name AS family_name
            FROM species_branches AS b
            JOIN species_families AS f ON f.id = b.family_id
            ORDER BY f.name, b.name
            """
        )

    def find_species_branch_by_name(
        self,
        name: str,
        family: str | None = None,
    ) -> sqlite3.Row | None:
        if family is None:
            return self._fetch_one(
                """
                SELECT b.id, b.name, b.family_id, f.name AS family_name
                FROM species_branches AS b
                JOIN species_families AS f ON f.id = b.family_id
                WHERE b.name = ?
                ORDER BY f.name
                LIMIT 1
                """,
                (name.strip(),),
            )
        return self._fetch_one(
            """
            SELECT b.id, b.name, b.family_id, f.name AS family_name
            FROM species_branches AS b
            JOIN species_families AS f ON f.id = b.family_id
            WHERE b.name = ? AND f.name = ?
            """,
            (name.strip(), family.strip()),
        )

    def add_species_branch(self, name: str, family_id: int) -> int:
        return self._execute(
            "INSERT INTO species_branches(name, family_id) VALUES (?, ?)",
            (name.strip(), family_id),
        )

    def update_species_branch(self, branch_id: int, name: str, family_id: int) -> None:
        self._execute(
            "UPDATE species_branches SET name = ?, family_id = ? WHERE id = ?",
            (name.strip(), family_id, branch_id),
        )

    def delete_species_branch(self, branch_id: int) -> None:
        self._execute("DELETE FROM species_branches WHERE id = ?", (branch_id,))

    # 学生
    def list_students(self, keyword: str = "") -> list[sqlite3.Row]:
        pattern = f"%{keyword.strip()}%"
        return self._fetch_all(
            """
            SELECT s.id, s.student_no, s.name, s.species_branch_id,
                   f.name AS family, b.name AS branch,
                   s.gender, s.birth_date, s.enrollment_year, s.status,
                   s.primary_element, s.primary_affinity,
                   s.contact, s.dormitory, s.notes, s.class_id,
                   c.name AS class_name, m.name AS major_name,
                   d.name AS department_name
            FROM students AS s
            JOIN species_branches AS b ON b.id = s.species_branch_id
            JOIN species_families AS f ON f.id = b.family_id
            LEFT JOIN classes AS c ON c.id = s.class_id
            LEFT JOIN majors AS m ON m.id = c.major_id
            LEFT JOIN departments AS d ON d.id = m.department_id
            WHERE ? = '%%'
               OR s.student_no LIKE ?
               OR s.name LIKE ?
               OR f.name LIKE ?
               OR b.name LIKE ?
               OR COALESCE(c.name, '') LIKE ?
               OR COALESCE(m.name, '') LIKE ?
               OR COALESCE(d.name, '') LIKE ?
               OR COALESCE(s.primary_element, '') LIKE ?
            ORDER BY s.student_no
            """,
            (pattern,) * 9,
        )

    def find_student_by_no(self, student_no: str) -> sqlite3.Row | None:
        return self._fetch_one(
            """
            SELECT s.id, s.student_no, s.name, s.species_branch_id,
                   f.name AS family, b.name AS branch,
                   s.gender, s.birth_date, s.enrollment_year, s.status,
                   s.primary_element, s.primary_affinity,
                   s.contact, s.dormitory, s.notes, s.class_id,
                   c.name AS class_name, m.name AS major_name,
                   d.name AS department_name
            FROM students AS s
            JOIN species_branches AS b ON b.id = s.species_branch_id
            JOIN species_families AS f ON f.id = b.family_id
            LEFT JOIN classes AS c ON c.id = s.class_id
            LEFT JOIN majors AS m ON m.id = c.major_id
            LEFT JOIN departments AS d ON d.id = m.department_id
            WHERE s.student_no = ?
            """,
            (student_no.strip(),),
        )

    def get_student(self, student_id: int) -> sqlite3.Row | None:
        return self._fetch_one("SELECT * FROM students WHERE id = ?", (student_id,))

    def add_student(
        self,
        *,
        student_no: str,
        name: str,
        species_branch_id: int,
        enrollment_year: int,
        gender: str | None = None,
        birth_date: str | None = None,
        class_id: int | None = None,
        status: str = "在读",
        primary_element: str | None = None,
        primary_affinity: str | None = None,
        contact: str | None = None,
        dormitory: str | None = None,
        notes: str | None = None,
    ) -> int:
        return self._execute(
            """
            INSERT INTO students(
                student_no, name, species_branch_id, gender, birth_date,
                enrollment_year, class_id, status,
                primary_element, primary_affinity,
                contact, dormitory, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_no.strip(), name.strip(), species_branch_id,
                _blank_to_none(gender), _blank_to_none(birth_date), enrollment_year,
                class_id, status.strip() or "在读",
                _blank_to_none(primary_element), _blank_to_none(primary_affinity),
                _blank_to_none(contact), _blank_to_none(dormitory), _blank_to_none(notes),
            ),
        )

    def update_student(self, student_id: int, **values: Any) -> None:
        allowed = {
            "student_no", "name", "species_branch_id", "gender", "birth_date",
            "enrollment_year", "class_id", "status", "primary_element",
            "primary_affinity", "contact", "dormitory", "notes",
        }
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unsupported student fields: {', '.join(sorted(unknown))}")
        if not values:
            return
        assignments = ", ".join(f"{name} = ?" for name in values)
        parameters = [values[name] for name in values]
        parameters.append(student_id)
        self._execute(
            f"UPDATE students SET {assignments} WHERE id = ?",
            parameters,
        )

    def delete_student(self, student_id: int) -> None:
        self._execute("DELETE FROM students WHERE id = ?", (student_id,))

    # 课程
    def list_courses(self) -> list[sqlite3.Row]:
        return self._fetch_all(
            """
            SELECT c.id, c.course_code, c.name, c.department_id,
                   c.credits, c.hours, d.name AS department_name
            FROM courses AS c
            LEFT JOIN departments AS d ON d.id = c.department_id
            ORDER BY c.course_code
            """
        )

    def find_course_by_code(self, course_code: str) -> sqlite3.Row | None:
        return self._fetch_one(
            """
            SELECT c.id, c.course_code, c.name, c.department_id,
                   c.credits, c.hours, d.name AS department_name
            FROM courses AS c
            LEFT JOIN departments AS d ON d.id = c.department_id
            WHERE c.course_code = ?
            """,
            (course_code.strip(),),
        )

    def add_course(
        self,
        course_code: str,
        name: str,
        department_id: int | None,
        credits: float,
        hours: int,
    ) -> int:
        return self._execute(
            """
            INSERT INTO courses(course_code, name, department_id, credits, hours)
            VALUES (?, ?, ?, ?, ?)
            """,
            (course_code.strip(), name.strip(), department_id, credits, hours),
        )

    def update_course(
        self,
        course_id: int,
        course_code: str,
        name: str,
        department_id: int | None,
        credits: float,
        hours: int,
    ) -> None:
        self._execute(
            """
            UPDATE courses
            SET course_code = ?, name = ?, department_id = ?, credits = ?, hours = ?
            WHERE id = ?
            """,
            (course_code.strip(), name.strip(), department_id, credits, hours, course_id),
        )

    def delete_course(self, course_id: int) -> None:
        self._execute("DELETE FROM courses WHERE id = ?", (course_id,))

    # 选课与成绩
    def list_enrollments(self) -> list[sqlite3.Row]:
        return self._fetch_all(
            """
            SELECT e.id, e.student_id, e.course_id, e.semester, e.score,
                   s.student_no, s.name AS student_name,
                   c.course_code, c.name AS course_name
            FROM enrollments AS e
            JOIN students AS s ON s.id = e.student_id
            JOIN courses AS c ON c.id = e.course_id
            ORDER BY e.semester DESC, s.student_no, c.course_code
            """
        )

    def find_enrollment(
        self,
        student_no: str,
        course_code: str,
        semester: str,
    ) -> sqlite3.Row | None:
        return self._fetch_one(
            """
            SELECT e.id, e.student_id, e.course_id, e.semester, e.score,
                   s.student_no, s.name AS student_name,
                   c.course_code, c.name AS course_name
            FROM enrollments AS e
            JOIN students AS s ON s.id = e.student_id
            JOIN courses AS c ON c.id = e.course_id
            WHERE s.student_no = ? AND c.course_code = ? AND e.semester = ?
            """,
            (student_no.strip(), course_code.strip(), semester.strip()),
        )

    def add_enrollment(
        self,
        student_id: int,
        course_id: int,
        semester: str,
        score: float | None = None,
    ) -> int:
        return self._execute(
            """
            INSERT INTO enrollments(student_id, course_id, semester, score)
            VALUES (?, ?, ?, ?)
            """,
            (student_id, course_id, semester.strip(), score),
        )

    def update_enrollment(self, enrollment_id: int, semester: str, score: float | None) -> None:
        self._execute(
            "UPDATE enrollments SET semester = ?, score = ? WHERE id = ?",
            (semester.strip(), score, enrollment_id),
        )

    def delete_enrollment(self, enrollment_id: int) -> None:
        self._execute("DELETE FROM enrollments WHERE id = ?", (enrollment_id,))


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
