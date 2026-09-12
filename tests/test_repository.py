from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.repository import Repository
from xingyuan_sis.reports import summary
from xingyuan_sis.seed_data import CLASSES, COURSES, ENROLLMENTS, STUDENTS, seed_demo


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.db_path)
        seed_demo(self.db_path)
        self.repository = Repository(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_canonical_seed_supports_student_course_workflow(self) -> None:
        expected = STUDENTS[0]
        expected_class_name = next(
            row[1] for row in CLASSES if row[0] == expected[7]
        )
        student = next(
            row for row in self.repository.list_students()
            if row["student_no"] == expected[0]
        )

        self.assertEqual(student["name"], expected[1])
        self.assertEqual(student["family"], expected[2])
        self.assertEqual(student["branch"], expected[3])
        self.assertEqual(student["class_name"], expected_class_name)
        self.assertEqual(student["primary_affinity"], expected[10])

        self.repository.update_student(
            student["id"],
            status="在读",
            primary_affinity="A+",
        )
        self.assertEqual(
            self.repository.get_student(student["id"])["primary_affinity"],
            "A+",
        )

        enrollments = self.repository.list_enrollments()
        self.assertEqual(len(enrollments), len(ENROLLMENTS))
        enrollment = enrollments[0]
        self.repository.update_enrollment(
            enrollment["id"],
            enrollment["semester"],
            99,
        )
        updated = next(
            row for row in self.repository.list_enrollments()
            if row["id"] == enrollment["id"]
        )
        self.assertEqual(updated["score"], 99)

        stats = summary(self.db_path)
        self.assertEqual(stats["students"], len(STUDENTS))
        self.assertEqual(stats["courses"], len(COURSES))
        self.assertIsNotNone(stats["average_score"])

    def test_student_number_is_unique(self) -> None:
        student = self.repository.list_students()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.add_student(
                student_no=student["student_no"],
                name=student["name"],
                species_branch_id=student["species_branch_id"],
                enrollment_year=student["enrollment_year"],
            )


if __name__ == "__main__":
    unittest.main()
