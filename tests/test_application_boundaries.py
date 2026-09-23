import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.auth import (
    DEMO_STUDENT_PASSWORD,
    authenticate,
    initialize_admin,
    read_session,
    write_session,
)
from xingyuan_sis.database import initialize_database
from xingyuan_sis.service import XingyuanService


class ApplicationBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.db = root / "main.db"
        self.other_db = root / "other.db"
        self.old_home = os.environ.get("XINGYUAN_HOME")
        os.environ["XINGYUAN_HOME"] = str(root / "auth")
        initialize_database(self.db)
        initialize_database(self.other_db)

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("XINGYUAN_HOME", None)
        else:
            os.environ["XINGYUAN_HOME"] = self.old_home
        self.temp_dir.cleanup()

    def service_with_species(self) -> XingyuanService:
        service = XingyuanService(self.db)
        service.create_species_family(name="犬科")
        service.create_species_branch(name="灰狼", family="犬科")
        return service

    def test_admin_session_is_scoped_to_database(self) -> None:
        identity = initialize_admin("adminpass")
        write_session(identity, self.db)

        current = read_session(self.db)
        self.assertIsNotNone(current)
        self.assertTrue(current.is_admin)
        self.assertIsNone(read_session(self.other_db))

    def test_register_student_uses_student_number_as_first_password(self) -> None:
        service = self.service_with_species()
        student_no = "20990001"

        record_id, password = service.register_student(
            student_no=student_no,
            name="测试学生",
            family="犬科",
            branch="灰狼",
            enrollment_year=2026,
        )

        self.assertGreater(record_id, 0)
        self.assertEqual(password, student_no)
        identity = authenticate(self.db, student_no, student_no)
        self.assertIsNotNone(identity)
        self.assertTrue(identity.must_change_password)

    def test_invalid_first_password_does_not_leave_student_record(self) -> None:
        service = self.service_with_species()

        with self.assertRaisesRegex(ValueError, "密码至少需要 8 个字符"):
            service.register_student(
                student_no="123",
                name="短学号",
                family="犬科",
                branch="灰狼",
                enrollment_year=2026,
            )

        self.assertIsNone(service.student_by_no("123"))

    def test_service_owns_demo_seed_lifecycle_and_credentials(self) -> None:
        service = XingyuanService(self.db)
        result = service.seed_demo()

        self.assertGreater(result.students, 0)
        first = service.list_students()[0]
        identity = authenticate(self.db, str(first["student_no"]), DEMO_STUDENT_PASSWORD)
        self.assertIsNotNone(identity)
        self.assertTrue(identity.must_change_password)

        with self.assertRaisesRegex(ValueError, "已有数据"):
            service.seed_demo()

        rebuilt = service.seed_demo(reset=True)
        self.assertEqual(rebuilt.students, result.students)
        self.assertEqual(len(service.list_students()), result.students)


if __name__ == "__main__":
    unittest.main()
