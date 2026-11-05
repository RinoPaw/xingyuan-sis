"""Independent QA regression tests for the Web UI/UX optimization round.

Covers areas not exercised by ``tests/test_web.py``:
- grade / notice form-failure drafts (auto-reopen, values, cleanup)
- invalid selected-record URLs render an empty detail pane
- pagination links keep search filters and drop the selection
- one-shot draft semantics and signed-cookie size safety
- zero scores render as ``0`` instead of ``-``
- draft values are HTML-escaped and exclude identity/CSRF/hidden fields
"""

from __future__ import annotations

import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.service import XingyuanService
from xingyuan_sis.web import create_app


class WebUIRegressionTests(unittest.TestCase):
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

    # -- helpers ---------------------------------------------------------

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

    def record_links(self, body: bytes, path: str, key: str) -> list[bytes]:
        return [
            href
            for href in re.findall(rb'href="([^"]+)"', body)
            if path.encode() in href and key.encode() in href
        ]

    # -- grade form drafts ------------------------------------------------

    def test_grade_create_failure_reopens_dialog_with_sanitized_draft(self) -> None:
        self.login_admin()
        response = self.post(
            "/grades/create",
            {
                "student_no": "20260001",
                "course_code": "ELS101",
                "semester": "2026-2027-1",
                "score": "150",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("create=1", response.headers["Location"])
        with self.client.session_transaction() as session:
            drafts = session["_form_drafts"]
        values = drafts["new-grade"]["values"]
        self.assertEqual(values["semester"], "2026-2027-1")
        self.assertEqual(values["score"], "150")
        # Only whitelisted fields: no CSRF, no hidden routing fields.
        self.assertEqual(set(values), {"student_no", "course_code", "semester", "score"})

        rendered = self.client.get(response.headers["Location"])
        self.assertEqual(rendered.status_code, 200)
        self.assertIn(b"data-auto-open", rendered.data)
        self.assertIn(b"data-form-error", rendered.data)
        self.assertIn('value="2026-2027-1"'.encode(), rendered.data)
        self.assertIn(b'name="score" type="number" min="0" max="100"', rendered.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("_form_drafts", session)

    def test_grade_edit_failure_keeps_editable_draft_only(self) -> None:
        self.login_admin()
        svc = XingyuanService(self.db_path)
        enrollment = svc.list_enrollments()[0]
        response = self.post(
            f"/grades/{enrollment['id']}/edit",
            {
                "student_no": enrollment["student_no"],
                "course_code": enrollment["course_code"],
                "original_semester": enrollment["semester"],
                "semester": enrollment["semester"],
                "score": "250",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("edit=1", response.headers["Location"])
        with self.client.session_transaction() as session:
            drafts = session["_form_drafts"]
        values = drafts["edit-grade"]["values"]
        # Hidden routing fields must never be part of the draft.
        self.assertEqual(set(values), {"semester", "score"})
        self.assertEqual(values["score"], "250")

        rendered = self.client.get(response.headers["Location"])
        self.assertEqual(rendered.status_code, 200)
        self.assertIn(b"data-auto-open", rendered.data)
        self.assertIn(b'data-form-error', rendered.data)
        self.assertIn('value="250"'.encode(), rendered.data)

    # -- notice form drafts ------------------------------------------------

    def test_notice_create_failure_reopens_dialog_with_draft(self) -> None:
        self.login_admin()
        response = self.post(
            "/notices/create",
            {"title": "失败公告", "body": "正文草稿", "class_code": "NOPE"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("create=1", response.headers["Location"])
        with self.client.session_transaction() as session:
            drafts = session["_form_drafts"]
        values = drafts["new-notice"]["values"]
        self.assertEqual(values["title"], "失败公告")
        self.assertEqual(values["body"], "正文草稿")
        self.assertNotIn("_csrf_token", values)

        rendered = self.client.get(response.headers["Location"])
        self.assertEqual(rendered.status_code, 200)
        self.assertIn(b"data-auto-open", rendered.data)
        self.assertIn(b"data-form-error", rendered.data)
        self.assertIn('value="失败公告"'.encode(), rendered.data)
        self.assertIn("正文草稿".encode(), rendered.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("_form_drafts", session)

    def test_notice_create_success_clears_draft(self) -> None:
        self.login_admin()
        # Seed a failing draft, then complete the realistic retry flow:
        # the failure redirect renders the form (consuming the draft) and a
        # corrected submission succeeds.
        failed = self.post("/notices/create", {"title": "x", "body": "y", "class_code": "NOPE"})
        self.assertIn("create=1", failed.headers["Location"])
        rendered = self.client.get(failed.headers["Location"])  # consume draft
        self.assertIn(b"data-form-error", rendered.data)
        response = self.post(
            "/notices/create",
            {"title": "回归公告", "body": "正文", "class_code": "ELS2601"},
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn("_form_drafts", session)
        final = self.client.get("/notices")
        self.assertIn("回归公告".encode(), final.data)
        self.assertNotIn(b"data-form-error", final.data)

    def test_student_edit_draft_excludes_identity_fields(self) -> None:
        self.login_admin()
        response = self.post(
            "/students/20260001/edit",
            {
                "student_no": "20260001",
                "name": "改名尝试",
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
                "contact": "13700000000",
                "dormitory": "",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            values = session["_form_drafts"]["edit-student"]["values"]
        self.assertNotIn("student_no", values)
        self.assertNotIn("name", values)
        self.assertNotIn("_csrf_token", values)
        self.assertIn("family", values)

    # -- draft escaping and cookie safety ----------------------------------

    def test_draft_values_are_html_escaped(self) -> None:
        self.login_admin()
        response = self.post(
            "/students/create",
            {
                "student_no": "20260001",  # duplicate -> failure
                "name": 'a"b><script>alert(1)</script>',
                "family": "犬科",
                "branch": "",
                "enrollment_year": "2026",
                "class_code": "",
                "gender": "",
                "birth_date": "",
                "age": "",
                "status": "在读",
                "primary_element": "",
                "primary_affinity": "",
                "contact": "",
                "dormitory": "",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        rendered = self.client.get(response.headers["Location"])
        self.assertEqual(rendered.status_code, 200)
        self.assertNotIn(b"<script>alert(1)</script>", rendered.data)
        self.assertIn("script&gt;".encode(), rendered.data)

    def test_max_size_draft_stays_within_signed_cookie_budget(self) -> None:
        self.login_admin()
        filler = "测" * 250
        data = {
            "student_no": "20260001",  # duplicate -> failure, draft is saved
            "name": filler,
            "family": filler,
            "branch": filler,
            "enrollment_year": "2026",
            "class_code": filler,
            "gender": filler,
            "birth_date": filler,
            "age": "19",
            "status": filler,
            "primary_element": filler,
            "primary_affinity": filler,
            "contact": filler,
            "dormitory": filler,
            "notes": filler,
        }
        response = self.post("/students/create", data)
        self.assertEqual(response.status_code, 302)
        cookie_headers = [
            header
            for header in response.headers.getlist("Set-Cookie")
            if header.startswith("session")
        ]
        self.assertTrue(cookie_headers)
        worst = max(len(header) for header in cookie_headers)
        # Browsers reject Set-Cookie headers larger than ~4096 bytes.
        self.assertLess(worst, 4096, f"signed session cookie too large: {worst} bytes")

    # -- invalid selected record URLs ---------------------------------------

    def test_invalid_selections_render_empty_detail(self) -> None:
        self.login_admin()
        cases = (
            ("/students?student_no=NOT_EXISTS", "选择一份档案"),
            ("/courses?course_code=NOPE999", "选择一门课程"),
            ("/grades?id=999999", "选择一条记录"),
            ("/grades?id=abc", "选择一条记录"),
            ("/grades?id=-1", "选择一条记录"),
            ("/notices?id=999999", "选择一条公告"),
            ("/notices?id=abc", "选择一条公告"),
        )
        for url, empty_text in cases:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn(empty_text.encode(), response.data)
                self.assertNotIn(b"grade-row is-selected", response.data)
                self.assertNotIn(b"roster-item is-selected", response.data)
                self.assertNotIn(b"course-tile is-selected", response.data)
                self.assertNotIn(b"notice-catalog-item is-selected", response.data)

    def test_invalid_selected_grade_does_not_fall_back_to_first_row(self) -> None:
        self.login_admin()
        svc = XingyuanService(self.db_path)
        first = svc.list_enrollments()[0]
        response = self.client.get("/grades?id=999999")
        self.assertEqual(response.status_code, 200)
        # The inspector pane must stay empty: no first-row content leaks in.
        inspector = re.search(
            rb'<aside class="grade-inspector".*?</aside>', response.data, re.S
        )
        self.assertIsNotNone(inspector)
        self.assertIn("选择一条记录".encode(), inspector.group(0))
        self.assertNotIn(first["student_name"].encode(), inspector.group(0))
        self.assertNotIn(b'grade-row is-selected', response.data)

    # -- pagination keeps filters and clears selection ----------------------

    def test_grade_record_links_on_page3_and_filter_preservation(self) -> None:
        self.login_admin()
        svc = XingyuanService(self.db_path)
        rows = svc.list_enrollments()
        self.assertGreater(len(rows), 28)
        target = rows[28]  # page 3 with 14 per page
        response = self.client.get(f"/grades?id={target['id']}")
        self.assertEqual(response.status_code, 200)
        links = self.record_links(response.data, "/grades?", "id=")
        self.assertTrue(links)
        self.assertTrue(all(b"page=3" in href for href in links))

        # "ELS" matches many enrollments, so the filter yields multiple pages
        # and a real pagination nav is rendered.
        response = self.client.get("/grades?q=ELS")
        self.assertEqual(response.status_code, 200)
        links = self.record_links(response.data, "/grades?", "id=")
        self.assertTrue(links)
        self.assertTrue(all(b"q=ELS" in href for href in links))
        pagination_links = [
            href
            for href in re.findall(rb'href="([^"]+)"', response.data)
            if b"/grades?" in href and b"page=" in href and b"id=" not in href
        ]
        self.assertTrue(pagination_links)
        self.assertTrue(all(b"q=ELS" in href for href in pagination_links))

    def test_student_record_and_pagination_links_keep_filters(self) -> None:
        self.login_admin()
        # Record links keep every active filter (single page is fine here).
        response = self.client.get(
            "/students?class=ELS2601&status=%E5%9C%A8%E8%AF%BB&element=%E9%A3%8E"
        )
        self.assertEqual(response.status_code, 200)
        record_links = self.record_links(response.data, "/students?", "student_no=")
        self.assertTrue(record_links)
        for href in record_links:
            self.assertIn(b"class=ELS2601", href)
            self.assertIn(b"status=%E5%9C%A8%E8%AF%BB", href)
            self.assertIn(b"element=%E9%A3%8E", href)

        # Pagination links keep the filter and drop the selection. "在读" has
        # enough students to produce several pages.
        response = self.client.get("/students?status=%E5%9C%A8%E8%AF%BB&page=2")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<strong>02</strong> /", response.data)
        pagination_links = [
            href
            for href in re.findall(rb'href="([^"]+)"', response.data)
            if b"/students?" in href and b"page=" in href and b"student_no=" not in href
        ]
        self.assertTrue(pagination_links)
        self.assertTrue(all(b"status=%E5%9C%A8%E8%AF%BB" in href for href in pagination_links))

    # -- zero score rendering ------------------------------------------------

    def test_zero_score_renders_as_zero_not_dash(self) -> None:
        self.login_admin()
        svc = XingyuanService(self.db_path)
        enrollment_id = svc.add_grade(
            student_no="20260002", course_code="ELS101", semester="2029-2030-1", score=0.0
        )
        response = self.client.get(f"/grades?id={enrollment_id}")
        self.assertEqual(response.status_code, 200)
        # The big score display shows a literal 0, not 待评 and not —.
        self.assertIn(b'<div class="big-score "><span>SCORE</span><strong>0</strong>', response.data)
        # The selected row shows the 0 chip (score 0 < 60 => is-low class).
        self.assertIsNotNone(
            re.search(rb'grade-row is-selected.*?score-chip is-low">0</b>', response.data, re.S)
        )
        self.assertNotIn("待评".encode() + b"</strong>", response.data)

    # -- selection state survives page 2 navigation ---------------------------

    def test_selecting_second_page_record_keeps_highlight_and_page(self) -> None:
        self.login_admin()
        svc = XingyuanService(self.db_path)
        rows = svc.list_students()
        self.assertGreater(len(rows), 24)
        target = rows[13]  # page 2 with 12 per page
        response = self.client.get(f"/students?page=2&student_no={target['student_no']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"roster-item is-selected", response.data)
        self.assertIn(b"<strong>02</strong> /", response.data)  # page indicator
        self.assertIn(target["name"].encode(), response.data)
        # The list still shows page-2 records only.
        self.assertNotIn(rows[0]["student_no"].encode(), response.data)

    def test_page_parameter_out_of_range_is_clamped(self) -> None:
        self.login_admin()
        svc = XingyuanService(self.db_path)
        pages = max(1, -(-len(svc.list_students()) // 12))
        response = self.client.get("/students?page=999")
        self.assertEqual(response.status_code, 200)
        self.assertIn(f'<strong>{pages:02d}</strong>'.encode(), response.data)
        response = self.client.get("/students?page=abc")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<strong>01</strong> /", response.data)


if __name__ == "__main__":
    unittest.main()
