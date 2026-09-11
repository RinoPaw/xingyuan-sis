from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.cli import main as cli_main
from xingyuan_sis.database import initialize_database
from xingyuan_sis.service import XingyuanService


class ServiceAndCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.db_path)
        self.service = XingyuanService(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def seed(self) -> None:
        self.service.create_department(code="SCI", name="自然科学学院")
        self.service.create_major(code="ELM", name="元素学", department_code="SCI")
        self.service.create_class(
            code="ELM2601",
            name="元素学2601班",
            major_code="ELM",
            enrollment_year=2026,
        )
        self.service.create_student(
            student_no="20260001",
            name="林岚",
            family="猫科",
            branch="石虎",
            enrollment_year=2026,
            class_code="ELM2601",
            primary_element="风",
            primary_affinity="A",
        )
        self.service.create_course(
            course_code="ELM101",
            name="元素反应概论",
            department_code="SCI",
            credits=3.0,
            hours=48,
        )

    def test_business_codes_drive_shared_service(self) -> None:
        self.seed()
        self.service.add_grade(
            student_no="20260001",
            course_code="ELM101",
            semester="2026-2027-1",
            score=92,
        )

        student = self.service.student_by_no("20260001")
        course = self.service.course_by_code("ELM101")
        enrollment = self.service.enrollment("20260001", "ELM101", "2026-2027-1")

        self.assertIsNotNone(student)
        self.assertEqual(student["class_name"], "元素学2601班")
        self.assertIsNotNone(course)
        self.assertEqual(course["department_name"], "自然科学学院")
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment["score"], 92)

        self.service.update_student_by_no("20260001", status="休学")
        self.service.update_grade(
            student_no="20260001",
            course_code="ELM101",
            semester="2026-2027-1",
            score=95,
        )
        self.assertEqual(self.service.student_by_no("20260001")["status"], "休学")
        self.assertEqual(
            self.service.enrollment("20260001", "ELM101", "2026-2027-1")["score"],
            95,
        )

    def test_cli_uses_selected_database(self) -> None:
        self.seed()
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["--db", str(self.db_path), "stu", "ls"])
        self.assertEqual(code, 0)
        self.assertIn("20260001", output.getvalue())
        self.assertIn("林岚", output.getvalue())

        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["--db", str(self.db_path), "data", "stats"])
        self.assertEqual(code, 0)
        self.assertIn("学生", output.getvalue())
        self.assertIn("课程", output.getvalue())


if __name__ == "__main__":
    unittest.main()
