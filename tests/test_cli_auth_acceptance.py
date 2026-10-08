"""Real CLI authentication lifecycle, without bypassing login or authorization."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.auth import (
    INITIAL_STUDENT_PASSWORD, authenticate, has_admin, initialize_admin,
    read_session,
)
from xingyuan_sis.database import initialize_database
from xingyuan_sis.entry import main
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.service import XingyuanService


class CliAuthAcceptanceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        env = patch.dict(os.environ, {"XINGYUAN_HOME": str(self.root / "auth")})
        env.start()
        self.addCleanup(env.stop)
        self.db = self.root / "campus.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.service = XingyuanService(self.db)
        self.student = self.service.list_students()[0]["student_no"]

    def cli(self, *args, passwords=()):
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors), patch(
            "getpass.getpass", side_effect=passwords
        ):
            result = main(["--db", str(self.db), *args])
        return result, output.getvalue(), errors.getvalue()

    def test_fresh_admin_bootstraps_and_gets_signed_in(self):
        self.assertFalse(has_admin())
        code, out, err = self.cli(
            "auth", "login", passwords=("first-admin-pass", "first-admin-pass")
        )
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertTrue(has_admin())
        identity = read_session(self.db)
        self.assertIsNotNone(identity)
        self.assertTrue(identity.is_admin)
        code, out, err = self.cli("data", "stats")
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertIn("学生", out)

    def test_admin_login_logout_wrong_password_and_password_change(self):
        initialize_admin("original-admin-pass")
        code, out, err = self.cli("auth", "login", "Administrator", passwords=("wrongpass",))
        self.assertEqual(code, 1)
        self.assertIn("登录失败", err) if "登录失败" in err else self.assertIn("账号或密码错误", err)
        self.assertIsNone(read_session(self.db))
        code, out, err = self.cli(
            "auth", "login", "Administrator", passwords=("original-admin-pass",)
        )
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertTrue(read_session(self.db).is_admin)
        code, out, err = self.cli(
            "auth", "passwd",
            passwords=("original-admin-pass", "new-admin-pass-2026", "new-admin-pass-2026"),
        )
        self.assertEqual((code, err), (0, ""), out + err)
        code, out, err = self.cli("auth", "logout")
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertIsNone(read_session(self.db))
        code, out, err = self.cli(
            "auth", "login", "Administrator", passwords=("original-admin-pass",)
        )
        self.assertEqual(code, 1)
        code, out, err = self.cli(
            "auth", "login", "Administrator", passwords=("new-admin-pass-2026",)
        )
        self.assertEqual((code, err), (0, ""), out + err)

    def test_student_first_login_changes_password_and_enforces_privileges(self):
        initialize_admin("admin-pass-2026")
        code, out, err = self.cli(
            "auth", "login", self.student,
            passwords=(INITIAL_STUDENT_PASSWORD, "strong-student-pass", "strong-student-pass"),
        )
        self.assertEqual((code, err), (0, ""), out + err)
        identity = read_session(self.db)
        self.assertIsNotNone(identity)
        self.assertTrue(identity.is_student)
        self.assertEqual(identity.student_no, self.student)
        self.assertIsNone(authenticate(self.db, self.student, INITIAL_STUDENT_PASSWORD))
        code, out, err = self.cli("stu", "show", self.student)
        self.assertEqual((code, err), (0, ""), out + err)
        code, out, err = self.cli("stu", "ls")
        self.assertEqual((code, err), (0, ""), out + err)
        for command in (("data", "stats"), ("stu", "edit", self.student, "--status", "休学"), ("grade", "ls")):
            with self.subTest(command=command):
                code, out, err = self.cli(*command)
                self.assertEqual(code, 1)
                self.assertIn("无权", err)
        code, out, err = self.cli("auth", "logout")
        self.assertEqual((code, err), (0, ""), out + err)
        code, out, err = self.cli(
            "auth", "login", self.student, passwords=("strong-student-pass",)
        )
        self.assertEqual((code, err), (0, ""), out + err)

    def test_reset_password_invalidates_existing_student_session(self):
        initialize_admin("admin-pass-2026")
        code, out, err = self.cli(
            "auth", "login", self.student,
            passwords=(INITIAL_STUDENT_PASSWORD, "strong-student-pass", "strong-student-pass"),
        )
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertTrue(read_session(self.db).is_student)
        self.service.reset_student_password(self.student)
        self.assertIsNone(read_session(self.db))
        code, out, err = self.cli("stu", "ls")
        self.assertEqual(code, 1)
        self.assertIn("尚未登录", err)
        code, out, err = self.cli("auth", "login", self.student, passwords=("strong-student-pass",))
        self.assertEqual(code, 1)
        code, out, err = self.cli(
            "auth", "login", self.student,
            passwords=(INITIAL_STUDENT_PASSWORD, "new-student-pass", "new-student-pass"),
        )
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertTrue(read_session(self.db).is_student)

    def test_cli_access_without_login_is_rejected_cleanly(self):
        initialize_admin("admin-pass-2026")
        for command in (("stu", "ls"), ("data", "seed", "--reset"), ("notice", "ls")):
            with self.subTest(command=command):
                code, out, err = self.cli(*command)
                self.assertEqual(code, 1)
                self.assertIn("尚未登录", err)
                self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
