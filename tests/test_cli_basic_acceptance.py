"""Black-box first-stage acceptance tests for CLI and numbered basic menus.

These invoke the real entrypoint, parser, service, SQLite and basic menu
dispatcher. Only the terminal capabilities, screen clear and input stream are
replaced; TUI code is deliberately excluded.
"""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import csv
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis import basic_ui
from xingyuan_sis.auth import Identity
from xingyuan_sis.database import connect, initialize_database
from xingyuan_sis.entry import main
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.service import XingyuanService
from xingyuan_sis.terminal_capabilities import TerminalCapabilities


class CliBasicAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._source = TemporaryDirectory()
        cls.source_db = Path(cls._source.name) / "original.db"
        initialize_database(cls.source_db)
        seed_demo(cls.source_db)

    @classmethod
    def tearDownClass(cls):
        cls._source.cleanup()

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.db = self.root / "test.db"
        shutil.copy2(self.source_db, self.db)
        self.service = XingyuanService(self.db)
        self.sample = self.service.list_students()[0]
        self.family = self.sample["family"]
        self.branch = self.sample["branch"]
        auth = patch(
            "xingyuan_sis.auth_cli.require_identity",
            return_value=Identity("Administrator", "admin"),
        )
        auth.start()
        self.addCleanup(auth.stop)

    def cli(self, *args, answers=None):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            if answers is None:
                code = main(["--db", str(self.db), *args])
            else:
                with patch("builtins.input", side_effect=answers):
                    code = main(["--db", str(self.db), *args])
        return code, out.getvalue(), err.getvalue()

    def basic(self, inputs, *, identity=None):
        identity = identity or Identity("Administrator", "admin")
        out, err = StringIO(), StringIO()
        with (
            patch("xingyuan_sis.entry.detect_terminal", return_value=TerminalCapabilities(True, False, False)),
            patch.object(basic_ui, "_clear"),
            patch.object(basic_ui, "read_session", return_value=identity),
            patch("xingyuan_sis.auth_cli.require_identity", return_value=identity),
            patch("builtins.input", side_effect=inputs),
            redirect_stdout(out), redirect_stderr(err),
        ):
            result = main(["--db", str(self.db), "--basic"])
        return result, out.getvalue(), err.getvalue()

    def test_cli_list_show_filters_and_output_formats(self):
        code, listed, error = self.cli("stu", "ls")
        self.assertEqual((code, error), (0, ""))
        self.assertIn(self.sample["student_no"], listed)
        code, shown, error = self.cli("stu", "show", self.sample["student_no"])
        self.assertEqual((code, error), (0, ""))
        self.assertIn(self.sample["name"], shown)
        code, exact, _ = self.cli("stu", "ls", "--no", self.sample["student_no"], "--format", "csv")
        self.assertEqual(code, 0)
        rows = list(csv.DictReader(StringIO(exact)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["student_no"], self.sample["student_no"])
        self.assertNotIn("password_hash", exact)
        code, missing, _ = self.cli("stu", "ls", "--name", "此名字不存在")
        self.assertEqual(code, 0)
        self.assertIn("无数据", missing)

    def test_cli_output_files_utf8_csv_and_table(self):
        export_csv = self.root / "result" / "list.csv"
        code, _, error = self.cli("stu", "ls", "--format", "csv", "--output", str(export_csv))
        self.assertEqual((code, error), (0, ""))
        with export_csv.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), len(self.service.list_students()))
        self.assertNotIn("password", export_csv.read_text(encoding="utf-8").casefold())
        table = self.root / "result" / "list.txt"
        code, _, error = self.cli("stu", "ls", "-o", str(table))
        self.assertEqual((code, error), (0, ""))
        self.assertIn(self.sample["student_no"], table.read_text(encoding="utf-8"))

    def test_cli_add_student_without_branch_uses_database_null(self):
        code, out, error = self.cli(
            "stu", "add", "--no", "29990191", "--name", "空支系学生",
            "--family", self.family, "--year", "2026", answers=[],
        )
        self.assertEqual((code, error), (0, ""), out + error)
        row = self.service.student_by_no("29990191")
        self.assertIsNotNone(row)
        self.assertIsNone(row["branch"])
        self.assertEqual(row["family"], self.family)

    def test_cli_shows_null_branch_without_literal_none(self):
        self.service.register_student(
            student_no="29990192", name="未定支系学生",
            family=self.family, branch=None, enrollment_year=2026,
        )
        code, out, error = self.cli("stu", "show", "29990192")
        self.assertEqual((code, error), (0, ""))
        self.assertIn(self.family, out)
        self.assertNotIn("None", out)

    def test_cli_branch_can_be_cleared_with_empty_flag(self):
        code, out, error = self.cli(
            "stu", "edit", self.sample["student_no"], "--branch", "",
        )
        self.assertEqual((code, error), (0, ""), out + error)
        self.assertIsNone(self.service.student_by_no(self.sample["student_no"])["branch"])
        code, out, error = self.cli("stu", "show", self.sample["student_no"])
        self.assertEqual((code, error), (0, ""))
        self.assertNotIn("None", out)

    def test_cli_invalid_student_number_or_year_cannot_write(self):
        for student_no, year in (("12x", "2026"), ("abc", "2026"), ("29990193", "1888")):
            with self.subTest(student_no=student_no, year=year):
                code, out, error = self.cli(
                    "stu", "add", "--no", student_no, "--name", "无效",
                    "--family", self.family, "--branch", self.branch,
                    "--year", year,
                )
                self.assertNotEqual(code, 0)
                self.assertIn("操作失败", error)
                self.assertIsNone(self.service.student_by_no(student_no))

    def test_cli_explicit_no_branch_flag_and_family_change(self):
        no = self.sample["student_no"]
        old_family = self.sample["family"]
        old_domain = {
            row["name"] for row in self.service.list_species_branches()
            if row["family_name"] == old_family
        }
        next_family = next(
            row["name"] for row in self.service.list_species_families()
            if row["name"] != old_family and {
                branch["name"] for branch in self.service.list_species_branches()
                if branch["family_name"] == row["name"]
            } != old_domain
        )
        code, out, error = self.cli("stu", "edit", no, "--family", next_family)
        self.assertEqual((code, error), (0, ""), out + error)
        changed = self.service.student_by_no(no)
        self.assertEqual(changed["family"], next_family)
        self.assertIsNone(changed["branch"])
        code, out, error = self.cli("stu", "edit", no, "--no-branch")
        self.assertEqual((code, error), (0, ""), out + error)
        self.assertIsNone(self.service.student_by_no(no)["branch"])

    def test_cli_branch_clear_flag_is_exclusive_with_branch_choice(self):
        from xingyuan_sis.cli.parser import build_parser
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
            build_parser().parse_args(
                ["stu", "edit", "20000001", "--branch", "灰狼", "--no-branch"]
            )
        self.assertEqual(caught.exception.code, 2)

    def test_cli_identity_fields_immutable_and_failed_update_atomic(self):
        no = self.sample["student_no"]
        before = dict(self.service.student_by_no(no))
        code, _, error = self.cli("stu", "edit", no, "--year", "1888", "--status", "休学")
        self.assertNotEqual(code, 0)
        self.assertIn("操作失败", error)
        self.assertEqual(dict(self.service.student_by_no(no)), before)

    def test_cli_delete_requires_confirmation_and_cascades_only_after_yes(self):
        no = self.sample["student_no"]
        grade_count = len(self.service.enrollments_for_student(no))
        code, out, error = self.cli("stu", "rm", no, answers=["n"])
        self.assertEqual((code, error), (0, ""))
        self.assertIn("取消", out)
        self.assertIsNotNone(self.service.student_by_no(no))
        self.assertEqual(len(self.service.enrollments_for_student(no)), grade_count)
        code, out, error = self.cli("stu", "rm", no, "--yes")
        self.assertEqual((code, error), (0, ""), out + error)
        self.assertIsNone(self.service.student_by_no(no))
        self.assertFalse(self.service.enrollments_for_student(no))
        with connect(self.db) as conn:
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_cli_missing_student_returns_error_not_traceback(self):
        for command in (("stu", "show", "00000000"), ("stu", "edit", "00000000", "--status", "休学"),
                        ("stu", "rm", "00000000", "--yes"), ("stu", "reset-password", "00000000")):
            with self.subTest(command=command):
                code, out, error = self.cli(*command)
                self.assertEqual(code, 1)
                self.assertIn("找不到学生", error)
                self.assertNotIn("Traceback", error)

    def test_cli_grade_add_edit_clear_delete_roundtrip(self):
        no = self.sample["student_no"]
        course = self.service.list_courses()[0]["course_code"]
        semester = "2033-2034-2"
        for args in (
            ("grade", "add", no, course, "--semester", semester, "--score", "89.5"),
            ("grade", "edit", no, course, semester, "--score", "98"),
            ("grade", "edit", no, course, semester, "--clear-score"),
        ):
            code, out, err = self.cli(*args)
            self.assertEqual((code, err), (0, ""), out + err)
        self.assertIsNone(self.service.enrollment(no, course, semester)["score"])
        code, out, err = self.cli("grade", "rm", no, course, semester, "--yes")
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertIsNone(self.service.enrollment(no, course, semester))

    def test_cli_rejects_nonfinite_and_out_of_range_scores(self):
        no = self.sample["student_no"]
        course = self.service.list_courses()[0]["course_code"]
        for raw in ("nan", "inf", "-0.1", "100.1", "1e1000"):
            with self.subTest(value=raw):
                code, out, error = self.cli(
                    "grade", "add", no, course, "--semester", "2033-2034-1", "--score", raw,
                )
                self.assertNotEqual(code, 0, out)
                self.assertIn("操作失败", error)
                self.assertIsNone(self.service.enrollment(no, course, "2033-2034-1"))

    def test_cli_academic_and_course_crud_and_dependency_restriction(self):
        commands = (
            ("college", "add", "NEW99", "测试学院"),
            ("major", "add", "MA99", "测试专业", "--college", "NEW99"),
            ("class", "add", "CL99", "测试班级", "--major", "MA99", "--year", "2026"),
            ("course", "add", "--code", "CO99", "--name", "测试课程", "--credits", "0", "--hours", "0", "--department", "NEW99"),
            ("college", "edit", "NEW99", "--name", "改名学院"),
        )
        for command in commands:
            with self.subTest(command=command):
                code, out, err = self.cli(*command)
                self.assertEqual((code, err), (0, ""), out + err)
        self.assertEqual(self.service.department_by_code("NEW99")["name"], "改名学院")
        self.assertEqual(self.service.course_by_code("CO99")["credits"], 0)
        self.assertEqual(self.service.course_by_code("CO99")["hours"], 0)
        code, _, err = self.cli("college", "rm", "NEW99", "--yes")
        self.assertNotEqual(code, 0)
        self.assertIsNotNone(self.service.department_by_code("NEW99"))
        for command in (
            ("class", "rm", "CL99", "--yes"),
            ("major", "rm", "MA99", "--yes"),
            ("course", "rm", "CO99", "--yes"),
            ("college", "rm", "NEW99", "--yes"),
        ):
            code, out, err = self.cli(*command)
            self.assertEqual((code, err), (0, ""), out + err)
        self.assertIsNone(self.service.department_by_code("NEW99"))

    def test_cli_announcements_are_class_scoped_for_students(self):
        class_code = self.sample["class_code"]
        self.assertTrue(class_code)
        code, out, err = self.cli(
            "notice", "add", "--title", "成绩公示", "--class", class_code,
            "--body", "周末开放教室",
        )
        self.assertEqual((code, err), (0, ""), out + err)
        notice = next(n for n in self.service.list_announcements() if n["title"] == "成绩公示")
        role = Identity(self.sample["student_no"], "student", self.sample["student_no"])
        with patch("xingyuan_sis.auth_cli.require_identity", return_value=role), \
             patch("xingyuan_sis.cli.notice.read_session", return_value=role):
            code, out, err = self.cli("notice", "show", str(notice["id"]))
            self.assertEqual((code, err), (0, ""), out + err)
            self.assertIn("周末开放教室", out)
            code, out, err = self.cli("notice", "add", "--title", "越权", "--class", class_code, "--body", "无")
            self.assertEqual(code, 1)
            self.assertIn("无权", err)

    def test_cli_students_cannot_mutate_or_read_admin_data(self):
        role = Identity(self.sample["student_no"], "student", self.sample["student_no"])
        with patch("xingyuan_sis.auth_cli.require_identity", return_value=role):
            for command in (
                ("stu", "add", "--no", "29990194", "--name", "未授权", "--family", self.family, "--year", "2026"),
                ("stu", "rm", self.sample["student_no"], "--yes"),
                ("stu", "edit", self.sample["student_no"], "--status", "休学"),
                ("data", "stats"),
                ("college", "ls"),
                ("course", "ls"),
                ("grade", "ls"),
            ):
                with self.subTest(command=command):
                    code, out, error = self.cli(*command)
                    self.assertEqual(code, 1, out)
                    self.assertIn("无权", error)
            code, out, error = self.cli("stu", "ls", "--no", self.sample["student_no"])
            self.assertEqual((code, error), (0, ""))
            self.assertIn(self.sample["student_no"], out)
        self.assertIsNotNone(self.service.student_by_no(self.sample["student_no"]))
        self.assertIsNone(self.service.student_by_no("29990194"))

    def test_cli_csv_export_import_partial_failures_preserve_good_rows(self):
        export = self.root / "export.csv"
        code, out, error = self.cli("data", "export", str(export))
        self.assertEqual((code, error), (0, ""), out + error)
        self.assertTrue(export.read_bytes().startswith(b"\xef\xbb\xbf"))
        text = export.read_text(encoding="utf-8-sig")
        self.assertNotIn("password_hash", text)
        import_file = self.root / "import.csv"
        import_file.write_text(
            "student_no,name,family,branch,enrollment_year\n"
            f"29990195,合法学生,{self.family},,2026\n"
            f"abc,非法学生,{self.family},,2026\n"
            f"29990195,重复学生,{self.family},,2026\n",
            encoding="utf-8",
        )
        code, out, err = self.cli("data", "import", str(import_file))
        self.assertEqual(code, 1)
        self.assertIn("失败 2 条", err)
        self.assertIn("已导入 1 条", out)
        self.assertIn("29990195", out)
        self.assertIsNone(self.service.student_by_no("abc"))
        self.assertIsNotNone(self.service.student_by_no("29990195"))

    def test_basic_menu_can_browse_and_return_to_main(self):
        code, out, err = self.basic(["1", "2", self.sample["student_no"], "q", "0", "0"])
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertIn(self.sample["name"], out)
        self.assertIn("首页 / 学生", out)
        self.assertIn("首页", out)

    def test_basic_search_one_student_and_return(self):
        code, out, err = self.basic(["1", "6", self.sample["student_no"], "", "0", "0"])
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertIn(self.sample["student_no"], out)

    def test_basic_can_add_student_without_branch_and_return(self):
        answers = [
            "1", "3", "29990196", "基础菜单学生", self.family, "", "2026",
            "", "", "", "", "", "", "", "", "", "", "",
            "", "0", "0",
        ]
        code, out, err = self.basic(answers)
        self.assertEqual((code, err), (0, ""), out + err)
        row = self.service.student_by_no("29990196")
        self.assertIsNotNone(row)
        self.assertIsNone(row["branch"])
        self.assertIn("已创建", out)

    def test_basic_delete_cancel_keeps_record(self):
        code, out, err = self.basic(["1", "5", self.sample["student_no"], "n", "", "0", "0"])
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertIn("取消", out)
        self.assertIsNotNone(self.service.student_by_no(self.sample["student_no"]))

    def test_basic_student_role_hides_management_commands(self):
        role = Identity(self.sample["student_no"], "student", self.sample["student_no"])
        code, out, err = self.basic(["1", "5", "0", "0"], identity=role)
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertIn("没有这个选项", out)
        self.assertNotIn("3. 新建学生", out)
        self.assertNotIn("5. 删除学生", out)
        self.assertNotIn("7. 重置登录密码", out)

    def test_basic_invalid_menu_selection_does_not_abort(self):
        code, out, err = self.basic(["???", "-9", "0"])
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertGreaterEqual(out.count("没有这个选项"), 2)

    def test_basic_cancelling_nested_menu_returns_to_home(self):
        code, out, err = self.basic(["1", KeyboardInterrupt(), "0"])
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertIn("首页 / 学生", out)
        self.assertIn("首页", out)

    def test_basic_noninteractive_terminal_is_rejected_cleanly(self):
        with patch("xingyuan_sis.entry.detect_terminal",
                   return_value=TerminalCapabilities(False, False, False)):
            code, out, err = self.cli("--basic")
        self.assertEqual(code, 2)
        self.assertIn("不是交互终端", err)
        self.assertNotIn("Traceback", err)

    def test_basic_menu_eof_exits_cleanly(self):
        code, out, err = self.basic([EOFError()])
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertIn("已退出星原", out)


if __name__ == "__main__":
    unittest.main()
