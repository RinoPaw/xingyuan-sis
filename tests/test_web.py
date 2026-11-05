from __future__ import annotations

import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from urllib.parse import quote
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

    def test_invalid_login_retains_username_without_password(self) -> None:
        self.client.get("/login")
        response = self.post(
            "/login",
            {"username": "Administrator", "password": "incorrect-secret-value"},
        )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('value="Administrator"', page)
        self.assertIn("\u8d26\u53f7\u6216\u5bc6\u7801\u4e0d\u6b63\u786e", page)
        self.assertNotIn("incorrect-secret-value", page)
        with self.client.session_transaction() as session:
            self.assertNotIn("identity", session)
        # Login name is HTML-escaped even when supplied by an untrusted browser.
        response = self.post("/login", {"username": '<script>alert(1)</script>',
                                         "password": "incorrect-secret-value"})
        self.assertIn('&lt;script&gt;', response.get_data(as_text=True))
        self.assertNotIn('value="<script>', response.get_data(as_text=True))

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


    def test_record_urls_keep_page_filter_and_selected_state(self) -> None:
        self.login_admin()
        student_rows = XingyuanService(self.db_path).list_students()
        self.assertGreater(len(student_rows), 24)
        target = student_rows[12]

        response = self.client.get(f"/students?student_no={target['student_no']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(target["name"].encode(), response.data)
        self.assertIn(student_rows[12]["student_no"].encode(), response.data)
        self.assertNotIn(student_rows[0]["student_no"].encode(), response.data)
        record_links = [
            href for href in re.findall(rb'href="([^"]+)"', response.data)
            if b"/students?" in href and b"student_no=" in href
        ]
        self.assertTrue(record_links)
        self.assertTrue(all(b"page=2" in href for href in record_links))
        pagination_links = [
            href for href in re.findall(rb'href="([^"]+)"', response.data)
            if b"/students?" in href and b"page=3" in href
        ]
        self.assertTrue(pagination_links)
        self.assertTrue(all(b"student_no=" not in href for href in pagination_links))

        invalid = self.client.get("/students?student_no=NOT_EXISTS")
        self.assertEqual(invalid.status_code, 200)
        self.assertIn("选择一份档案".encode(), invalid.data)
        self.assertNotIn(b"roster-item is-selected", invalid.data)

        filtered = self.client.get("/students?q=%E9%9B%B7&student_no=" + target["student_no"])
        self.assertEqual(filtered.status_code, 200)
        record_links = [
            href for href in re.findall(rb'href="([^"]+)"', filtered.data)
            if b"/students?" in href and b"student_no=" in href
        ]
        self.assertTrue(record_links)
        self.assertTrue(all(b"q=%E9%9B%B7" in href for href in record_links))

    def test_course_and_grade_record_urls_keep_page_state(self) -> None:
        self.login_admin()
        svc = XingyuanService(self.db_path)
        course_rows = svc.list_courses()
        self.assertGreater(len(course_rows), 18)
        course_target = course_rows[9]
        response = self.client.get(f"/courses?course_code={course_target['course_code']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(course_target["name"].encode(), response.data)
        self.assertIn(course_rows[9]["course_code"].encode(), response.data)
        self.assertNotIn(course_rows[0]["course_code"].encode(), response.data)
        record_links = [
            href for href in re.findall(rb'href="([^"]+)"', response.data)
            if b"/courses?" in href and b"course_code=" in href
        ]
        self.assertTrue(record_links)
        self.assertTrue(all(b"page=2" in href for href in record_links))

        grade_rows = svc.list_enrollments()
        self.assertGreater(len(grade_rows), 28)
        grade_target = grade_rows[14]
        response = self.client.get(f"/grades?id={grade_target['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(grade_target["student_name"].encode(), response.data)
        self.assertIn(grade_rows[14]["student_no"].encode(), response.data)
        record_links = [
            href for href in re.findall(rb'href="([^"]+)"', response.data)
            if b"/grades?" in href and b"id=" in href
        ]
        self.assertTrue(record_links)
        self.assertTrue(all(b"page=2" in href for href in record_links))

    def test_student_create_failure_reopens_dialog_with_draft_and_error(self) -> None:
        self.login_admin()
        values = {
            "student_no": "20260001",
            "name": "重复学生",
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
            "contact": "13800000000",
            "dormitory": "北区 1-101",
            "notes": "失败草稿",
        }
        response = self.post("/students/create", values)
        self.assertEqual(response.status_code, 302)
        self.assertIn("create=1", response.headers["Location"])
        with self.client.session_transaction() as session:
            drafts = session["_form_drafts"]
        self.assertEqual(drafts["new-student"]["values"]["name"], "重复学生")
        self.assertEqual(drafts["new-student"]["values"]["contact"], "13800000000")
        self.assertNotIn("_csrf_token", drafts["new-student"]["values"])

        rendered = self.client.get(response.headers["Location"])
        self.assertEqual(rendered.status_code, 200)
        self.assertIn(b"data-auto-open", rendered.data)
        self.assertIn(b"data-form-error", rendered.data)
        self.assertIn('value="重复学生"'.encode(), rendered.data)
        self.assertIn(b'value="13800000000"', rendered.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("_form_drafts", session)

    def test_student_edit_failure_reopens_dialog_with_editable_draft(self) -> None:
        self.login_admin()
        response = self.post(
            "/students/20260001/edit",
            {
                "family": "不存在的族系",
                "branch": "",
                "enrollment_year": "2026",
                "class_code": "ELS2601",
                "gender": "男",
                "birth_date": "",
                "age": "19",
                "status": "在读",
                "primary_element": "风",
                "primary_affinity": "A",
                "contact": "13900000000",
                "dormitory": "北区 1-102",
                "notes": "编辑失败草稿",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("edit=1", response.headers["Location"])
        rendered = self.client.get(response.headers["Location"])
        self.assertEqual(rendered.status_code, 200)
        self.assertIn(b"data-auto-open", rendered.data)
        self.assertIn(b"data-form-error", rendered.data)
        self.assertIn(b'value="13900000000"', rendered.data)
        self.assertIn("编辑失败草稿".encode(), rendered.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("_form_drafts", session)

    def test_course_create_failure_keeps_draft_and_success_clears_it(self) -> None:
        self.login_admin()
        response = self.post(
            "/courses/create",
            {
                "course_code": "ELS101",
                "name": "重复课程",
                "credits": "3.0",
                "hours": "48",
                "department_code": "SCI",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("create=1", response.headers["Location"])
        with self.client.session_transaction() as session:
            drafts = session["_form_drafts"]
        self.assertEqual(drafts["new-course"]["values"]["name"], "重复课程")
        self.assertNotIn("_csrf_token", drafts["new-course"]["values"])

        rendered = self.client.get(response.headers["Location"])
        self.assertEqual(rendered.status_code, 200)
        self.assertIn(b"data-auto-open", rendered.data)
        self.assertIn(b"data-form-error", rendered.data)
        self.assertIn('value="重复课程"'.encode(), rendered.data)

        created = self.post(
            "/courses/create",
            {
                "course_code": "WEB999",
                "name": "网页测试课程",
                "credits": "2.5",
                "hours": "32",
                "department_code": "SCI",
            },
        )
        self.assertEqual(created.status_code, 302)
        self.assertIsNotNone(XingyuanService(self.db_path).course_by_code("WEB999"))
        with self.client.session_transaction() as session:
            self.assertNotIn("_form_drafts", session)

    def test_course_edit_failure_reopens_dialog_with_draft(self) -> None:
        self.login_admin()
        response = self.post(
            "/courses/ELS101/edit",
            {
                "name": "更新失败课程",
                "credits": "3.0",
                "hours": "48",
                "department_code": "NOPE",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("edit=1", response.headers["Location"])
        rendered = self.client.get(response.headers["Location"])
        self.assertEqual(rendered.status_code, 200)
        self.assertIn(b"data-auto-open", rendered.data)
        self.assertIn(b"data-form-error", rendered.data)
        self.assertIn('value="更新失败课程"'.encode(), rendered.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("_form_drafts", session)

    def test_notice_record_links_keep_search_state(self) -> None:
        self.login_admin()
        notices = XingyuanService(self.db_path).list_announcements()
        self.assertTrue(notices)
        keyword = quote(str(notices[0]["title"][:2]))
        response = self.client.get(f"/notices?q={keyword}&id={notices[0]['id']}")
        self.assertEqual(response.status_code, 200)
        record_links = [
            href for href in re.findall(rb'href="([^"]+)"', response.data)
            if b"/notices?" in href and b"id=" in href
        ]
        self.assertTrue(record_links)
        self.assertTrue(all(keyword.encode() in href for href in record_links))
        self.assertIn(b'id="record-list"', response.data)
        self.assertIn(b'id="record-detail"', response.data)
        self.assertIn(b'class="detail-back"', response.data)


class WebEntryTests(unittest.TestCase):
    def test_web_flag_routes_to_flask_runner(self) -> None:
        with patch.object(entry, "ensure_default_state"), patch("xingyuan_sis.web.run") as run:
            code = entry.main(["--web", "--host", "0.0.0.0", "--port", "3100"])
        self.assertEqual(code, 0)
        run.assert_called_once_with(None, host="0.0.0.0", port=3100)


if __name__ == "__main__":
    unittest.main()
