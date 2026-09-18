from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.entry import main as cli_main
from xingyuan_sis.auth import Identity
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import CLASSES, COURSES, DEPARTMENTS, STUDENTS, seed_demo
from xingyuan_sis.service import XingyuanService


class ServiceAndCliTests(unittest.TestCase):
    def setUp(self) -> None:
        auth_patch = patch("xingyuan_sis.auth_cli.require_identity", return_value=Identity("Administrator", "admin"))
        auth_patch.start()
        self.addCleanup(auth_patch.stop)
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.db_path)
        seed_demo(self.db_path)
        self.service = XingyuanService(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_service_exposes_read_models_without_repository_passthrough(self) -> None:
        self.assertTrue(self.service.list_students())
        self.assertTrue(self.service.list_courses())
        self.assertTrue(self.service.list_departments())
        self.assertTrue(self.service.enrollments_for_student(self.service.list_students()[0]["student_no"]))
        self.assertFalse(hasattr(self.service, "add_department"))
        self.assertFalse(hasattr(self.service, "update_student"))

    def test_lookup_helpers_do_not_scan_list_models(self) -> None:
        department = self.service.list_departments()[0]
        major = self.service.list_majors()[0]
        class_ = self.service.list_classes()[0]
        family = self.service.list_species_families()[0]
        branch = self.service.list_species_branches()[0]
        student = self.service.list_students()[0]
        course = self.service.list_courses()[0]
        enrollment = self.service.list_enrollments()[0]
        repository = self.service.repository

        cases = (
            ("list_departments", lambda: self.service.department_by_code(department["code"])),
            ("list_majors", lambda: self.service.major_by_code(major["code"])),
            ("list_classes", lambda: self.service.class_by_code(class_["code"])),
            ("list_species_families", lambda: self.service.species_family_by_name(family["name"])),
            (
                "list_species_branches",
                lambda: self.service.species_branch_by_name(branch["name"], branch["family_name"]),
            ),
            ("list_students", lambda: self.service.student_by_no(student["student_no"])),
            ("list_courses", lambda: self.service.course_by_code(course["course_code"])),
            (
                "list_enrollments",
                lambda: self.service.enrollment(
                    enrollment["student_no"], enrollment["course_code"], enrollment["semester"]
                ),
            ),
        )
        for list_method, lookup in cases:
            with self.subTest(list_method=list_method), patch.object(
                repository,
                list_method,
                side_effect=AssertionError("lookup must not scan a list model"),
            ):
                self.assertIsNotNone(lookup())

    def test_precise_enrollment_reads_do_not_scan_general_list(self) -> None:
        enrollment = self.service.list_enrollments()[0]
        with patch.object(
            self.service.repository,
            "list_enrollments",
            side_effect=AssertionError("precise read must not scan all enrollments"),
        ):
            self.assertTrue(self.service.enrollments_for_student(enrollment["student_no"]))
            self.assertTrue(self.service.enrollments_for_course(enrollment["course_code"]))

    def test_cli_read_commands_do_not_use_service_private_require(self) -> None:
        student_no = str(STUDENTS[0][0])
        course_code = str(COURSES[0][0])
        with patch.object(
            XingyuanService,
            "_require",
            side_effect=AssertionError("CLI must not call private service helpers"),
        ):
            for command in (("stu", "show", student_no), ("course", "show", course_code)):
                with self.subTest(command=command), redirect_stdout(StringIO()):
                    code = cli_main(["--db", str(self.db_path), *command])
                self.assertEqual(code, 0)

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
