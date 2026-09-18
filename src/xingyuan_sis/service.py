from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

from .auth import generate_initial_password, hash_password
from .csv_io import ImportResult, export_students_csv, import_students_csv
from .reports import summary
from .repository import Repository
from .schema import FIELDS, validate_values


class XingyuanService:
    """Application-facing operations shared by CLI, TUI and the basic UI."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.repository = Repository(db_path)

    @property
    def db_path(self) -> Path | str | None:
        return self.repository.db_path

    # ----- read models ----------------------------------------------------
    def list_departments(self) -> list[sqlite3.Row]:
        return self.repository.list_departments()

    def list_majors(self) -> list[sqlite3.Row]:
        return self.repository.list_majors()

    def list_classes(self) -> list[sqlite3.Row]:
        return self.repository.list_classes()

    def list_species_families(self) -> list[sqlite3.Row]:
        return self.repository.list_species_families()

    def list_species_branches(self) -> list[sqlite3.Row]:
        return self.repository.list_species_branches()

    def list_students(self, keyword: str = "") -> list[sqlite3.Row]:
        return self.repository.list_students(keyword)

    def list_courses(self) -> list[sqlite3.Row]:
        return self.repository.list_courses()

    def list_enrollments(self, keyword: str = "") -> list[sqlite3.Row]:
        return self.repository.list_enrollments(keyword)

    def enrollments_for_student(self, student_no: str) -> list[sqlite3.Row]:
        return self.repository.list_enrollments_for_student(student_no)

    def enrollments_for_course(self, course_code: str) -> list[sqlite3.Row]:
        return self.repository.list_enrollments_for_course(course_code)

    # ----- lookup helpers -------------------------------------------------
    def student_by_no(self, student_no: str) -> sqlite3.Row | None:
        return self.repository.find_student_by_no(student_no)

    def course_by_code(self, course_code: str) -> sqlite3.Row | None:
        return self.repository.find_course_by_code(course_code)

    def class_by_code(self, class_code: str) -> sqlite3.Row | None:
        return self.repository.find_class_by_code(class_code)

    def department_by_code(self, department_code: str) -> sqlite3.Row | None:
        return self.repository.find_department_by_code(department_code)

    def major_by_code(self, major_code: str) -> sqlite3.Row | None:
        return self.repository.find_major_by_code(major_code)

    def species_family_by_name(self, name: str) -> sqlite3.Row | None:
        return self.repository.find_species_family_by_name(name)

    def species_branch_by_name(
        self,
        branch: str,
        family: str | None = None,
    ) -> sqlite3.Row | None:
        return self.repository.find_species_branch_by_name(branch, family)

    def enrollment(
        self,
        student_no: str,
        course_code: str,
        semester: str,
    ) -> sqlite3.Row | None:
        return self.repository.find_enrollment(student_no, course_code, semester)

    @staticmethod
    def _require(row: sqlite3.Row | None, message: str) -> sqlite3.Row:
        if row is None:
            raise ValueError(message)
        return row

    # ----- academics ------------------------------------------------------
    def create_department(self, *, code: str, name: str) -> int:
        values = validate_values("departments", {"code": code, "name": name})
        return self.repository.add_department(**values)

    def update_department_by_code(
        self,
        code: str,
        *,
        new_code: str | None = None,
        name: str | None = None,
    ) -> None:
        row = self._require(self.department_by_code(code), f"找不到学院：{code}")
        values = validate_values("departments", {
            "code": new_code if new_code is not None else row["code"],
            "name": name if name is not None else row["name"],
        })
        self.repository.update_department(
            int(row["id"]),
            **values,
        )

    def delete_department_by_code(self, code: str) -> None:
        row = self._require(self.department_by_code(code), f"找不到学院：{code}")
        self.repository.delete_department(int(row["id"]))

    def create_major(self, *, code: str, name: str, department_code: str) -> int:
        values = validate_values("majors", {"code": code, "name": name, "department_code": department_code})
        department = self._require(
            self.department_by_code(department_code),
            f"找不到学院：{department_code}",
        )
        return self.repository.add_major(values["code"], values["name"], int(department["id"]))

    def update_major_by_code(
        self,
        code: str,
        *,
        new_code: str | None = None,
        name: str | None = None,
        department_code: str | None = None,
    ) -> None:
        row = self._require(self.major_by_code(code), f"找不到专业：{code}")
        values = validate_values("majors", {
            "code": new_code if new_code is not None else row["code"],
            "name": name if name is not None else row["name"],
        }, partial=True)
        department_id = int(row["department_id"])
        if department_code is not None:
            department = self._require(
                self.department_by_code(department_code),
                f"找不到学院：{department_code}",
            )
            department_id = int(department["id"])
        self.repository.update_major(
            int(row["id"]),
            values["code"],
            values["name"],
            department_id,
        )

    def delete_major_by_code(self, code: str) -> None:
        row = self._require(self.major_by_code(code), f"找不到专业：{code}")
        self.repository.delete_major(int(row["id"]))

    def create_class(
        self,
        *,
        code: str,
        name: str,
        major_code: str,
        enrollment_year: int,
    ) -> int:
        values = validate_values("classes", {
            "code": code, "name": name, "major_code": major_code, "enrollment_year": enrollment_year,
        })
        major = self._require(self.major_by_code(major_code), f"找不到专业：{major_code}")
        return self.repository.add_class(values["code"], values["name"], int(major["id"]), values["enrollment_year"])

    def update_class_by_code(
        self,
        code: str,
        *,
        new_code: str | None = None,
        name: str | None = None,
        major_code: str | None = None,
        enrollment_year: int | None = None,
    ) -> None:
        row = self._require(self.class_by_code(code), f"找不到班级：{code}")
        values = validate_values("classes", {
            "code": new_code if new_code is not None else row["code"],
            "name": name if name is not None else row["name"],
            "enrollment_year": enrollment_year if enrollment_year is not None else row["enrollment_year"],
        }, partial=True)
        major_id = int(row["major_id"])
        if major_code is not None:
            major = self._require(self.major_by_code(major_code), f"找不到专业：{major_code}")
            major_id = int(major["id"])
        self.repository.update_class(
            int(row["id"]),
            values["code"],
            values["name"],
            major_id,
            values["enrollment_year"],
        )

    def delete_class_by_code(self, code: str) -> None:
        row = self._require(self.class_by_code(code), f"找不到班级：{code}")
        self.repository.delete_class(int(row["id"]))

    # ----- species --------------------------------------------------------
    def create_species_family(self, *, name: str) -> int:
        return self.repository.add_species_family(name)

    def update_species_family_by_name(self, name: str, *, new_name: str) -> None:
        row = self._require(self.species_family_by_name(name), f"找不到族系：{name}")
        self.repository.update_species_family(int(row["id"]), new_name)

    def delete_species_family_by_name(self, name: str) -> None:
        row = self._require(self.species_family_by_name(name), f"找不到族系：{name}")
        self.repository.delete_species_family(int(row["id"]))

    def create_species_branch(self, *, name: str, family: str) -> int:
        family_row = self._require(self.species_family_by_name(family), f"找不到族系：{family}")
        return self.repository.add_species_branch(name, int(family_row["id"]))

    def update_species_branch_by_name(
        self,
        name: str,
        *,
        family: str,
        new_name: str | None = None,
        new_family: str | None = None,
    ) -> None:
        row = self._require(
            self.species_branch_by_name(name, family),
            f"找不到支系：{family} · {name}",
        )
        target_family = new_family if new_family is not None else family
        family_row = self._require(
            self.species_family_by_name(target_family),
            f"找不到族系：{target_family}",
        )
        self.repository.update_species_branch(
            int(row["id"]),
            new_name if new_name is not None else str(row["name"]),
            int(family_row["id"]),
        )

    def delete_species_branch_by_name(self, name: str, *, family: str) -> None:
        row = self._require(
            self.species_branch_by_name(name, family),
            f"找不到支系：{family} · {name}",
        )
        self.repository.delete_species_branch(int(row["id"]))

    # ----- students -------------------------------------------------------
    def register_student(self, **values: Any) -> tuple[int, str]:
        """Create a student and login credentials in the same database insert."""
        password = generate_initial_password()
        return self.create_student(**values, initial_password=password), password

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
        initial_password: str | None = None,
    ) -> int:
        values = validate_values("students", {
            "student_no": student_no, "name": name, "family": family, "branch": branch,
            "enrollment_year": enrollment_year, "class_code": class_code, "gender": gender,
            "birth_date": birth_date, "status": status, "primary_element": primary_element,
            "primary_affinity": primary_affinity, "contact": contact, "dormitory": dormitory, "notes": notes,
        })
        species = self._require(
            self.species_branch_by_name(values["branch"], values["family"]),
            f"找不到种族支系：{family} · {branch}",
        )
        class_id = None
        class_code = values["class_code"]
        if class_code:
            row = self._require(self.class_by_code(class_code), f"找不到班级：{class_code}")
            class_id = int(row["id"])
        for field in ("family", "branch", "class_code"):
            values.pop(field)
        return self.repository.add_student(
            species_branch_id=int(species["id"]), class_id=class_id,
            password_hash=hash_password(initial_password) if initial_password is not None else None,
            **values,
        )

    def update_student_by_no(self, student_no: str, /, **values: Any) -> None:
        values = validate_values("students", values, partial=True)
        row = self._require(self.student_by_no(student_no), f"找不到学生：{student_no}")

        for field in FIELDS["students"]:
            if not field.editable and field.key in values:
                if values[field.key] != row[field.key]:
                    raise ValueError(f"{field.label}不能修改")
                values.pop(field.key)

        if "family" in values or "branch" in values:
            family = str(values.pop("family", row["family"]))
            branch = str(values.pop("branch", row["branch"]))
            species = self._require(
                self.species_branch_by_name(branch, family),
                f"找不到种族支系：{family} · {branch}",
            )
            values["species_branch_id"] = int(species["id"])

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

    # ----- class announcements -------------------------------------------
    def list_announcements(self, student_no: str | None = None) -> list[sqlite3.Row]:
        return self.repository.list_announcements(student_no)

    def create_announcement(self, *, title: str, body: str, class_code: str) -> int:
        values = validate_values("announcements", {"title": title, "body": body, "class_code": class_code})
        class_row = self._require(self.class_by_code(values["class_code"]), f"找不到班级：{class_code}")
        return self.repository.add_announcement(values["title"], values["body"], int(class_row["id"]))

    def delete_announcement(self, announcement_id: int) -> None:
        if not any(row["id"] == announcement_id for row in self.list_announcements()):
            raise ValueError(f"找不到公告：{announcement_id}")
        self.repository.delete_announcement(announcement_id)

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
        values = validate_values("courses", {
            "course_code": course_code, "name": name, "credits": credits,
            "hours": hours, "department_code": department_code,
        })
        department_code = values["department_code"]
        department_id = None
        if department_code:
            row = self._require(
                self.department_by_code(department_code),
                f"找不到学院：{department_code}",
            )
            department_id = int(row["id"])
        values.pop("department_code")
        return self.repository.add_course(department_id=department_id, **values)

    def update_course_by_code(self, course_code: str, /, **values: Any) -> None:
        values = validate_values("courses", values, partial=True)
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
        values = validate_values("grades", {
            "student_no": student_no, "course_code": course_code, "semester": semester, "score": score,
        })
        student = self._require(self.student_by_no(student_no), f"找不到学生：{student_no}")
        course = self._require(self.course_by_code(course_code), f"找不到课程：{course_code}")
        return self.repository.add_enrollment(
            int(student["id"]), int(course["id"]), values["semester"], values["score"]
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
        values = validate_values("grades", {
            "semester": new_semester if new_semester is not None else semester, "score": score,
        }, partial=True)
        row = self._require(
            self.enrollment(student_no, course_code, semester),
            "找不到这条选课记录",
        )
        self.repository.update_enrollment(
            int(row["id"]), values["semester"], values["score"]
        )

    def delete_grade(self, *, student_no: str, course_code: str, semester: str) -> None:
        row = self._require(
            self.enrollment(student_no, course_code, semester),
            "找不到这条选课记录",
        )
        self.repository.delete_enrollment(int(row["id"]))

    # ----- data -----------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        return summary(self.db_path)

    def export_students(self, path: Path | str) -> int:
        return export_students_csv(path, self.list_students())

    def import_students(self, path: Path | str) -> ImportResult:
        return import_students_csv(path, self.register_student)
