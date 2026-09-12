from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.auth import (
    ADMIN_USERNAME,
    DEMO_STUDENT_PASSWORD,
    authenticate,
    has_admin,
    provision_demo_passwords,
    read_session,
)
from xingyuan_sis.database import initialize_database
from xingyuan_sis.entry import main as entry_main
from xingyuan_sis.seed_data import seed_demo


class AuthCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.old_home = os.environ.get("XINGYUAN_HOME")
        os.environ["XINGYUAN_HOME"] = str(Path(self.temp_dir.name) / "auth")
        initialize_database(self.db_path)

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("XINGYUAN_HOME", None)
        else:
            os.environ["XINGYUAN_HOME"] = self.old_home
        self.temp_dir.cleanup()

    def initialize_admin(self) -> None:
        with patch("xingyuan_sis.auth_cli.getpass.getpass", side_effect=["adminpass", "adminpass"]):
            with redirect_stdout(StringIO()):
                code = entry_main(["--db", str(self.db_path), "auth", "login"])
        self.assertEqual(code, 0)

    def test_first_login_initializes_single_admin_and_creates_session(self) -> None:
        self.assertFalse(has_admin())
        self.initialize_admin()

        self.assertTrue(has_admin())
        self.assertIsNotNone(authenticate(self.db_path, ADMIN_USERNAME, "adminpass"))
        identity = read_session(self.db_path)
        self.assertIsNotNone(identity)
        self.assertTrue(identity.is_admin)
        self.assertEqual(identity.username, ADMIN_USERNAME)

    def test_business_cli_requires_login_after_logout(self) -> None:
        self.initialize_admin()
        self.assertEqual(entry_main(["--db", str(self.db_path), "auth", "logout"]), 0)

        errors = StringIO()
        with redirect_stderr(errors):
            code = entry_main(["--db", str(self.db_path), "stu", "ls"])
        self.assertEqual(code, 1)
        self.assertIn("xy auth login", errors.getvalue())

    def test_existing_admin_can_log_in_again(self) -> None:
        self.initialize_admin()
        entry_main(["--db", str(self.db_path), "auth", "logout"])

        with patch("xingyuan_sis.auth_cli.getpass.getpass", return_value="adminpass"):
            with redirect_stdout(StringIO()):
                code = entry_main(["--db", str(self.db_path), "auth", "login", ADMIN_USERNAME])
        self.assertEqual(code, 0)
        self.assertTrue(read_session(self.db_path).is_admin)

    def test_demo_student_must_change_password_on_first_login(self) -> None:
        self.initialize_admin()
        seed_demo(self.db_path)
        provision_demo_passwords(self.db_path)
        entry_main(["--db", str(self.db_path), "auth", "logout"])

        with patch(
            "xingyuan_sis.auth_cli.getpass.getpass",
            side_effect=[DEMO_STUDENT_PASSWORD, "studentpass", "studentpass"],
        ):
            with redirect_stdout(StringIO()):
                code = entry_main(["--db", str(self.db_path), "auth", "login", "20260001"])
        self.assertEqual(code, 0)

        identity = read_session(self.db_path)
        self.assertIsNotNone(identity)
        self.assertTrue(identity.is_student)
        self.assertFalse(identity.must_change_password)
        self.assertIsNotNone(authenticate(self.db_path, "20260001", "studentpass"))
        self.assertIsNone(authenticate(self.db_path, "20260001", DEMO_STUDENT_PASSWORD))

    def test_student_cli_is_limited_to_student_queries(self) -> None:
        self.initialize_admin()
        seed_demo(self.db_path)
        provision_demo_passwords(self.db_path)
        entry_main(["--db", str(self.db_path), "auth", "logout"])
        with patch(
            "xingyuan_sis.auth_cli.getpass.getpass",
            side_effect=[DEMO_STUDENT_PASSWORD, "studentpass", "studentpass"],
        ):
            with redirect_stdout(StringIO()):
                self.assertEqual(
                    entry_main(["--db", str(self.db_path), "auth", "login", "20260001"]),
                    0,
                )

        with redirect_stdout(StringIO()):
            self.assertEqual(entry_main(["--db", str(self.db_path), "stu", "ls"]), 0)

        errors = StringIO()
        with redirect_stderr(errors):
            code = entry_main(["--db", str(self.db_path), "data", "stats"])
        self.assertEqual(code, 1)
        self.assertIn("无权", errors.getvalue())

    def test_auth_without_subcommand_reports_status(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = entry_main(["--db", str(self.db_path), "auth"])
        self.assertEqual(code, 0)
        self.assertIn("管理员：未初始化", output.getvalue())
        self.assertIn("login", output.getvalue())


if __name__ == "__main__":
    unittest.main()
