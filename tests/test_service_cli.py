from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.cli import main as cli_main
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import CLASSES, COURSES, DEPARTMENTS, STUDENTS, seed_demo
from xingyuan_sis.service import XingyuanService


class ServiceAndCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.db_path)
        seed_demo(self.db_path)
        self.service = XingyuanService(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_business_codes_drive_shared_service(self) -> None:
        student_seed = STUDENTS[0]
        student_no = str(student_seed[0])
        class_name = next(
            row[1] for row in CLASSES if row[0] == student_seed[7]
        )
        course_seed = COURSES[0]
        course_code = str(course_seed[0])
        department_name = next(
            row[1] for row in DEPARTMENTS if row[0] == course_seed[2]
        )
        semester = "2027-2028-2"

        self.service.add_grade(
            student_no=student_no,
            course_code=course_code,
            semester=semester,
            score=92,
        )

        student = self.service.student_by_no(student_no)
        course = self.service.course_by_code(course_code)
        enrollment = self.service.enrollment(student_no, course_code, semester)

        self.assertIsNotNone(student)
        self.assertEqual(student["class_name"], class_name)
        self.assertIsNotNone(course)
        self.assertEqual(course["department_name"], department_name)
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment["score"], 92)

        self.service.update_student_by_no(student_no, status="休学")
        self.service.update_grade(
            student_no=student_no,
            course_code=course_code,
            semester=semester,
            score=95,
        )
        self.assertEqual(self.service.student_by_no(student_no)["status"], "休学")
        self.assertEqual(
            self.service.enrollment(student_no, course_code, semester)["score"],
            95,
        )

    def test_cli_uses_selected_database(self) -> None:
        expected_no, expected_name = str(STUDENTS[0][0]), str(STUDENTS[0][1])
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["--db", str(self.db_path), "stu", "ls"])
        self.assertEqual(code, 0)
        self.assertIn(expected_no, output.getvalue())
        self.assertIn(expected_name, output.getvalue())

        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["--db", str(self.db_path), "data", "stats"])
        self.assertEqual(code, 0)
        self.assertIn("学生", output.getvalue())
        self.assertIn("课程", output.getvalue())


if __name__ == "__main__":
    unittest.main()
