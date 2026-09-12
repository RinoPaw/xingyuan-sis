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

    def test_direct_lookups_return_full_business_rows(self) -> None:
        department = self.repository.list_departments()[0]
        major = self.repository.list_majors()[0]
        class_ = self.repository.list_classes()[0]
        family = self.repository.list_species_families()[0]
        branch = self.repository.list_species_branches()[0]
        student = self.repository.list_students()[0]
        course = self.repository.list_courses()[0]
        enrollment = self.repository.list_enrollments()[0]

        self.assertEqual(dict(self.repository.find_department_by_code(department["code"])), dict(department))
        self.assertEqual(dict(self.repository.find_major_by_code(major["code"])), dict(major))
        self.assertEqual(dict(self.repository.find_class_by_code(class_["code"])), dict(class_))
        self.assertEqual(dict(self.repository.find_species_family_by_name(family["name"])), dict(family))
        self.assertEqual(
            dict(self.repository.find_species_branch_by_name(branch["name"], branch["family_name"])),
            dict(branch),
        )
        self.assertEqual(dict(self.repository.find_student_by_no(student["student_no"])), dict(student))
        self.assertEqual(dict(self.repository.find_course_by_code(course["course_code"])), dict(course))
        self.assertEqual(
            dict(self.repository.find_enrollment(
                enrollment["student_no"], enrollment["course_code"], enrollment["semester"]
            )),
            dict(enrollment),
        )
        self.assertIsNone(self.repository.find_student_by_no("missing"))

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
