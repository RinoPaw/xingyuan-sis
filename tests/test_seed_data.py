from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.cli import main as cli_main
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.service import XingyuanService


class SeedDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "seed.db"
        initialize_database(self.db_path)
        self.service = XingyuanService(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_seed_populates_canonical_demo_data(self) -> None:
        result = seed_demo(self.db_path)

        self.assertEqual(result.departments, 4)
        self.assertEqual(result.majors, 10)
        self.assertEqual(result.classes, 26)
        self.assertEqual(result.students, 100)
        self.assertEqual(result.courses, 20)
        self.assertEqual(result.enrollments, 400)

        student = self.service.student_by_no("20260001")
        self.assertIsNotNone(student)
        self.assertEqual(student["name"], "林岚")
        self.assertEqual(student["class_name"], "元素学2601班")
        self.assertEqual(student["primary_element"], "风")

        referenced_student = self.service.student_by_no("20260004")
        self.assertIsNotNone(referenced_student)
        self.assertEqual(referenced_student["name"], "雷格西")
        self.assertEqual(referenced_student["branch"], "灰狼")

        enrollment = self.service.enrollment(
            "20230002",
            "EEE130",
            "2026-2027-1",
        )
        self.assertIsNotNone(enrollment)
        self.assertIsNone(enrollment["score"])

    def test_seed_refuses_nonempty_database_without_reset(self) -> None:
        seed_demo(self.db_path)
        with self.assertRaisesRegex(ValueError, "已有数据"):
            seed_demo(self.db_path)

    def test_reset_rebuilds_demo_data(self) -> None:
        seed_demo(self.db_path)
        self.service.update_student_by_no("20260001", name="临时名字")

        seed_demo(self.db_path, reset=True)

        self.assertEqual(self.service.student_by_no("20260001")["name"], "林岚")
        self.assertEqual(len(self.service.list_students()), 100)

    def test_cli_seed_command(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["--db", str(self.db_path), "data", "seed"])

        self.assertEqual(code, 0)
        self.assertIn("学生 100", output.getvalue())
        self.assertEqual(len(self.service.list_courses()), 20)

        error = StringIO()
        with redirect_stdout(StringIO()), redirect_stderr(error):
            code = cli_main(["--db", str(self.db_path), "data", "seed"])
        self.assertEqual(code, 1)
        self.assertIn("--reset", error.getvalue())


if __name__ == "__main__":
    unittest.main()
