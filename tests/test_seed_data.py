from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.entry import main as cli_main
from xingyuan_sis.auth import Identity
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import (
    CLASSES,
    COURSES,
    DEPARTMENTS,
    ENROLLMENTS,
    MAJORS,
    SPECIES_BRANCHES,
    SPECIES_FAMILIES,
    STUDENTS,
    seed_demo,
)
from xingyuan_sis.service import XingyuanService


class SeedDataTests(unittest.TestCase):
    def setUp(self) -> None:
        auth_patch = patch("xingyuan_sis.auth_cli.require_identity", return_value=Identity("Administrator", "admin"))
        auth_patch.start()
        self.addCleanup(auth_patch.stop)
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "seed.db"
        initialize_database(self.db_path)
        self.service = XingyuanService(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_seed_populates_canonical_demo_data(self) -> None:
        result = seed_demo(self.db_path)

        self.assertEqual(result.departments, len(DEPARTMENTS))
        self.assertEqual(result.majors, len(MAJORS))
        self.assertEqual(result.classes, len(CLASSES))
        self.assertEqual(result.species_families, len(SPECIES_FAMILIES))
        self.assertEqual(result.species_branches, len(SPECIES_BRANCHES))
        self.assertEqual(result.students, len(STUDENTS))
        self.assertEqual(result.courses, len(COURSES))
        self.assertEqual(result.enrollments, len(ENROLLMENTS))

        expected = STUDENTS[0]
        student = self.service.student_by_no(str(expected[0]))
        self.assertIsNotNone(student)
        self.assertEqual(student["name"], expected[1])
        self.assertEqual(
            student["class_name"],
            next(row[1] for row in CLASSES if row[0] == expected[7]),
        )
        self.assertEqual(student["primary_element"], expected[9])

        referenced_seed = next(row for row in STUDENTS if row[1] == "雷格西")
        referenced_student = self.service.student_by_no(str(referenced_seed[0]))
        self.assertIsNotNone(referenced_student)
        self.assertEqual(referenced_student["name"], referenced_seed[1])
        self.assertEqual(referenced_student["branch"], referenced_seed[3])

        pending = next(row for row in ENROLLMENTS if row[3] is None)
        enrollment = self.service.enrollment(
            str(pending[0]),
            str(pending[1]),
            str(pending[2]),
        )
        self.assertIsNotNone(enrollment)
        self.assertIsNone(enrollment["score"])

    def test_seed_refuses_nonempty_database_without_reset(self) -> None:
        seed_demo(self.db_path)
        with self.assertRaisesRegex(ValueError, "已有数据"):
            seed_demo(self.db_path)

    def test_reset_rebuilds_demo_data(self) -> None:
        expected = STUDENTS[0]
        seed_demo(self.db_path)
        self.service.update_student_by_no(str(expected[0]), status="休学")

        seed_demo(self.db_path, reset=True)

        self.assertEqual(
            self.service.student_by_no(str(expected[0]))["status"],
            expected[8],
        )
        self.assertEqual(len(self.service.list_students()), len(STUDENTS))

    def test_cli_seed_command(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["--db", str(self.db_path), "data", "seed"])

        self.assertEqual(code, 0)
        self.assertIn(f"学生 {len(STUDENTS)}", output.getvalue())
        self.assertEqual(len(self.service.list_courses()), len(COURSES))

        error = StringIO()
        with redirect_stdout(StringIO()), redirect_stderr(error):
            code = cli_main(["--db", str(self.db_path), "data", "seed"])
        self.assertEqual(code, 1)
        self.assertIn("--reset", error.getvalue())


if __name__ == "__main__":
    unittest.main()
