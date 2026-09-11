from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.repository import Repository
from xingyuan_sis.reports import summary


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.db_path)
        self.repository = Repository(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_complete_student_course_workflow(self) -> None:
        department_id = self.repository.add_department("SCI", "自然科学学院")
        major_id = self.repository.add_major("ELM", "元素学", department_id)
        class_id = self.repository.add_class("ELM2601", "元素学2601班", major_id, 2026)

        student_id = self.repository.add_student(
            student_no="20260001",
            name="林岚",
            family="猫科",
            branch="石虎",
            enrollment_year=2026,
            class_id=class_id,
            primary_element="风",
            primary_affinity="A",
        )
        course_id = self.repository.add_course(
            "ELM101", "元素反应概论", department_id, 3.0, 48
        )
        enrollment_id = self.repository.add_enrollment(
            student_id, course_id, "2026-2027-1", 92
        )

        students = self.repository.list_students("林岚")
        self.assertEqual(len(students), 1)
        self.assertEqual(students[0]["major_name"], "元素学")
        self.assertEqual(students[0]["primary_affinity"], "A")

        self.repository.update_student(student_id, status="在读", primary_affinity="A+")
        self.assertEqual(self.repository.get_student(student_id)["primary_affinity"], "A+")

        enrollments = self.repository.list_enrollments()
        self.assertEqual(len(enrollments), 1)
        self.assertEqual(enrollments[0]["id"], enrollment_id)
        self.assertEqual(enrollments[0]["score"], 92)

        stats = summary(self.db_path)
        self.assertEqual(stats["students"], 1)
        self.assertEqual(stats["courses"], 1)
        self.assertEqual(stats["average_score"], 92.0)

    def test_student_number_is_unique(self) -> None:
        values = dict(
            student_no="20260001",
            name="林岚",
            family="猫科",
            branch="石虎",
            enrollment_year=2026,
        )
        self.repository.add_student(**values)
        with self.assertRaises(Exception):
            self.repository.add_student(**values)


if __name__ == "__main__":
    unittest.main()
