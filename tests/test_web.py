from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis import entry
from xingyuan_sis.service import XingyuanService
from xingyuan_sis.web import create_app


class WebInterfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.old_home = os.environ.get("XINGYUAN_HOME")
        os.environ["XINGYUAN_HOME"] = str(Path(self.temp_dir.name) / "auth")
        self.db_path = Path(self.temp_dir.name) / "web.db"
        self.app = create_app(self.db_path, demo=True)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("XINGYUAN_HOME", None)
        else:
            os.environ["XINGYUAN_HOME"] = self.old_home
        self.temp_dir.cleanup()

    def csrf(self) -> str:
        with self.client.session_transaction() as session:
            token = session.get("_csrf_token")
        self.assertIsNotNone(token)
        return str(token)

    def login_admin(self) -> None:
        self.client.get("/login")
        response = self.client.post("/demo", data={"_csrf_token": self.csrf()})
        self.assertEqual(response.status_code, 302)

    def post(self, path: str, data: dict[str, str] | None = None):
        return self.client.post(path, data={"_csrf_token": self.csrf(), **(data or {})})

    def test_default_admin_can_log_in_without_manual_setup(self) -> None:
        self.client.get("/login")
        response = self.post(
            "/login",
            {"username": "Administrator", "password": "12345678"},
        )
        self.assertEqual(response.headers["Location"], "/")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_demo_login_renders_all_real_data_pages(self) -> None:
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn("星轨之间".encode(), response.data)
        self.login_admin()
        for path, text in (
            ("/", "元素能量分布"),
            ("/students", "学生名册"),
            ("/courses", "课程矩阵"),
            ("/grades", "成绩记录"),
            ("/notices", "班级公告"),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(text.encode(), response.data)
        with self.client.get("/static/app.js") as response:
            self.assertEqual(response.status_code, 200)
        with self.client.get("/static/favicon.svg") as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "image/svg+xml")
        with self.client.get("/assets/fonts/BarlowCondensed-Black.ttf") as response:
            self.assertEqual(response.status_code, 200)

    def test_admin_student_create_uses_shared_service_and_csrf(self) -> None:
        self.login_admin()
        values = {
            "student_no": "20269999",
            "name": "测试学生",
            "family": "犬科",
            "branch": "灰狼",
            "enrollment_year": "2026",
            "class_code": "ELS2601",
            "gender": "女",
            "birth_date": "",
            "age": "19",
            "status": "在读",
            "primary_element": "风",
            "primary_affinity": "A",
            "contact": "",
            "dormitory": "",
            "notes": "Web 测试",
        }
        rejected = self.client.post("/students/create", data=values)
        self.assertEqual(rejected.status_code, 400)
        self.assertIsNone(XingyuanService(self.db_path).student_by_no("20269999"))

        response = self.post("/students/create", values)
        self.assertEqual(response.status_code, 302)
        student = XingyuanService(self.db_path).student_by_no("20269999")
        self.assertIsNotNone(student)
        self.assertEqual(student["name"], "测试学生")
        self.assertEqual(student["class_code"], "ELS2601")

    def test_student_first_login_and_scope_are_enforced(self) -> None:
        self.client.get("/login")
        response = self.post(
            "/login",
            {"username": "20260001", "password": "123456"},
        )
        self.assertEqual(response.headers["Location"], "/password")
        self.assertEqual(self.client.get("/students").headers["Location"], "/password")
        response = self.post(
            "/password",
            {
                "current_password": "123456",
                "new_password": "student-pass-2026",
                "confirm_password": "student-pass-2026",
            },
        )
        self.assertEqual(response.headers["Location"], "/")
        response = self.client.get("/students")
        self.assertEqual(response.status_code, 200)
        self.assertIn("雷格西".encode(), response.data)
        self.assertNotIn("新建学生".encode(), response.data)
        self.assertEqual(self.post("/students/create").status_code, 403)
        self.assertEqual(self.post("/notices/create").status_code, 403)

    def test_notice_and_grade_routes_reject_anonymous_users(self) -> None:
        response = self.client.get("/notices")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        self.client.get("/login")
        self.assertEqual(self.post("/notices/1/delete").status_code, 302)


class WebEntryTests(unittest.TestCase):
    def test_web_flag_routes_to_flask_runner(self) -> None:
        with patch.object(entry, "ensure_default_state"), patch("xingyuan_sis.web.run") as run:
            code = entry.main(["--web", "--host", "0.0.0.0", "--port", "3100"])
        self.assertEqual(code, 0)
        run.assert_called_once_with(None, host="0.0.0.0", port=3100)


if __name__ == "__main__":
    unittest.main()
