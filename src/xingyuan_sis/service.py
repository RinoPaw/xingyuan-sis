from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

from .repository import Repository


class XingyuanService:
    """Application-facing operations shared by CLI, TUI and the basic UI.

    Existing TUI code may still call repository-style methods through this
    facade. New frontends should prefer the higher-level methods below so
    user-facing identifiers (student number, course code, class code) are
    resolved here rather than exposing database ids.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.repository = Repository(db_path)

    @property
    def db_path(self) -> Path | str | None:
        return self.repository.db_path

    def __getattr__(self, name: str) -> Any:
        return getattr(self.repository, name)

    # ----- lookup helpers -------------------------------------------------
    def student_by_no(self, student_no: str) -> sqlite3.Row | None:
        key = student_no.strip()
        return next(
            (row for row in self.repository.list_students(key) if row["student_no"] == key),
            None,
        )

    def course_by_code(self, course_code: str) -> sqlite3.Row | None:
        key = course_code.strip()
        return next(
            (row for row in self.repository.list_courses() if row["course_code"] == key),
            None,
        )

    def class_by_code(self, class_code: str) -> sqlite3.Row | None:
        key = class_code.strip()
        return next(
            (row for row in self.repository.list_classes() if row["code"] == key),
            None,
        )

    def department_by_code(self, department_code: str) -> sqlite3.Row | None:
        key = department_code.strip()
        return next(
            (row for row in self.repository.list_departments() if row["code"] == key),
            None,
        )

    def major_by_code(self, major_code: str) -> sqlite3.Row | None:
        key = major_code.strip()
        return next(
            (row for row in self.repository.list_majors() if row["code"] == key),
            None,
        )

    def enrollment(
        self,
        student_no: str,
        course_code: str,
        semester: str,
    ) -> sqlite3.Row | None:
        student_no = student_no.strip()
        course_code = course_code.strip()
        semester = semester.strip()
        return next(
            (
                row
                for row in self.repository.list_enrollments()
                if row["student_no"] == student_no
                and row["course_code"] == course_code
                and row["semester"] == semester
            ),
            None,
        )

    @staticmethod
    def _require(row: sqlite3.Row | None, message: str) -> sqlite3.Row:
        if row is None:
            raise ValueError(message)
        return row

    # ----- students -------------------------------------------------------
    def create_student(
        self,
        *,
        student_no: str,
        name: str,
        family: str,
        branch: str,
        enrollment_year: int,
        class_code: str | None = None,
        gender: str | None = None,
        birth_date: str | None = None,
        status: str = "在读",
        primary_element: str | None = None,
        primary_affinity: str | None = None,
        contact: str | None = None,
        dormitory: str | None = None,
        notes: str | None = None,
    ) -> int:
        class_id = None
        if class_code:
            row = self._require(
                self.class_by_code(class_code),
                f"找不到班级：{class_code}",
            )
            class_id = int(row["id"])
        return self.repository.add_student(
            student_no=student_no,
            name=name,
            family=family,
            branch=branch,
            enrollment_year=enrollment_year,
            gender=gender,
            birth_date=birth_date,
            class_id=class_id,
            status=status,
            primary_element=primary_element,
            primary_affinity=primary_affinity,
            contact=contact,
            dormitory=dormitory,
            notes=notes,
        )

    def update_student_by_no(self, student_no: str, **values: Any) -> None:
        row = self._require(self.student_by_no(student_no), f"找不到学生：{student_no}")
        if "class_code" in values:
            class_code = values.pop("class_code")
            if class_code:
                class_row = self._require(
                    self.class_by_code(str(class_code)),
                    f"找不到班级：{class_code}",
                )
                values["class_id"] = int(class_row["id"])
            else:
                values["class_id"] = None
        self.repository.update_student(int(row["id"]), **values)

    def delete_student_by_no(self, student_no: str) -> None:
        row = self._require(self.student_by_no(student_no), f"找不到学生：{student_no}")
        self.repository.delete_student(int(row["id"]))

    # ----- courses --------------------------------------------------------
    def create_course(
        self,
        *,
        course_code: str,
        name: str,
        credits: float,
        hours: int,
        department_code: str | None = None,
    ) -> int:
        department_id = None
        if department_code:
            row = self._require(
                self.department_by_code(department_code),
                f"找不到学院：{department_code}",
            )
            department_id = int(row["id"])
        return self.repository.add_course(
            course_code,
            name,
            department_id,
            credits,
            hours,
        )

    def update_course_by_code(self, course_code: str, **values: Any) -> None:
        row = self._require(self.course_by_code(course_code), f"找不到课程：{course_code}")
        current = dict(row)
        if "department_code" in values:
            department_code = values.pop("department_code")
            if department_code:
                department = self._require(
                    self.department_by_code(str(department_code)),
                    f"找不到学院：{department_code}",
                )
                current["department_id"] = int(department["id"])
            else:
                current["department_id"] = None
        current.update(values)
        self.repository.update_course(
            int(row["id"]),
            str(current["course_code"]),
            str(current["name"]),
            current.get("department_id"),
            float(current["credits"]),
            int(current["hours"]),
        )

    def delete_course_by_code(self, course_code: str) -> None:
        row = self._require(self.course_by_code(course_code), f"找不到课程：{course_code}")
        self.repository.delete_course(int(row["id"]))

    # ----- grades / enrollments ------------------------------------------
    def add_grade(
        self,
        *,
        student_no: str,
        course_code: str,
        semester: str,
        score: float | None = None,
    ) -> int:
        student = self._require(self.student_by_no(student_no), f"找不到学生：{student_no}")
        course = self._require(self.course_by_code(course_code), f"找不到课程：{course_code}")
        return self.repository.add_enrollment(
            int(student["id"]),
            int(course["id"]),
            semester,
            score,
        )

    def update_grade(
        self,
        *,
        student_no: str,
        course_code: str,
        semester: str,
        score: float | None,
        new_semester: str | None = None,
    ) -> None:
        row = self._require(
            self.enrollment(student_no, course_code, semester),
            "找不到这条选课记录",
        )
        self.repository.update_enrollment(
            int(row["id"]),
            (new_semester or semester).strip(),
            score,
        )

    def delete_grade(self, *, student_no: str, course_code: str, semester: str) -> None:
        row = self._require(
            self.enrollment(student_no, course_code, semester),
            "找不到这条选课记录",
        )
        self.repository.delete_enrollment(int(row["id"]))
