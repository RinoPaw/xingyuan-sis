import csv
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.csv_io import STUDENT_FIELDS
from xingyuan_sis.entry import main as cli_main
from xingyuan_sis.auth import Identity
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.student_query import parse_student_query
from xingyuan_sis.tui.workspace.data import Catalog


class StudentFilterCliTests(unittest.TestCase):
    def setUp(self) -> None:
        auth_patch = patch("xingyuan_sis.auth_cli.require_identity", return_value=Identity("Administrator", "admin"))
        auth_patch.start()
        self.addCleanup(auth_patch.stop)
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.db_path)
        seed_demo(self.db_path)
        self.catalog = Catalog(self.db_path)
        self.students = self.catalog.records["students"]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_xy(self, *args: str) -> str:
        output = StringIO()
        with redirect_stdout(output):
            code = cli_main(["--db", str(self.db_path), *args])
        self.assertEqual(code, 0)
        return output.getvalue()

    def listed_nos(self, output: str) -> set[str]:
        return {
            str(row["student_no"])
            for row in self.students
            if str(row["student_no"]) in output
        }

    @staticmethod
    def contains(row, term: str, *fields: str) -> bool:
        return any(term in str(row.get(field) or "") for field in fields)

    def assert_table_filter(self, args: tuple[str, ...], predicate) -> None:
        expected = {str(row["student_no"]) for row in self.students if predicate(row)}
        self.assertTrue(expected)
        output = self.run_xy("stu", "ls", *args)
        self.assertEqual(self.listed_nos(output), expected)

    def test_branch_filter_is_fuzzy(self) -> None:
        self.assert_table_filter(
            ("--branch", "牧羊"),
            lambda row: self.contains(row, "牧羊", "branch"),
        )

    def test_major_matches_code_or_name_fuzzily(self) -> None:
        for term in ("元素", "ELS"):
            with self.subTest(term=term):
                self.assert_table_filter(
                    ("--major", term),
                    lambda row, term=term: self.contains(
                        row, term, "major_code", "major_name"
                    ),
                )

    def test_class_and_college_match_code_or_name_fuzzily(self) -> None:
        self.assert_table_filter(
            ("--class", "2601"),
            lambda row: self.contains(row, "2601", "class_code", "class_name"),
        )
        self.assert_table_filter(
            ("--college", "工程"),
            lambda row: self.contains(
                row, "工程", "department_code", "department_name"
            ),
        )

    def test_filters_are_and_across_fields(self) -> None:
        self.assert_table_filter(
            ("--major", "元素", "--year", "2026", "--status", "在"),
            lambda row: (
                self.contains(row, "元素", "major_code", "major_name")
                and int(row["enrollment_year"]) == 2026
                and "在" in str(row["status"])
            ),
        )

    def test_repeated_filter_is_or_within_field(self) -> None:
        self.assert_table_filter(
            ("--element", "风", "--element", "雷"),
            lambda row: str(row.get("primary_element") or "") in {"风", "雷"},
        )

    def test_search_combines_with_structured_filter(self) -> None:
        self.assert_table_filter(
            ("--status", "在读", "-s", "赤狐"),
            lambda row: (
                "在读" in str(row["status"])
                and self.contains(row, "赤狐", "branch")
            ),
        )

    def test_student_number_and_year_remain_exact(self) -> None:
        target = self.students[0]
        other = next(
            row for row in self.students
            if row["student_no"] != target["student_no"]
        )
        output = self.run_xy("stu", "ls", "--no", str(target["student_no"]))
        self.assertEqual(self.listed_nos(output), {str(target["student_no"])})
        self.assertNotIn(str(other["student_no"]), output)

        year = int(target["enrollment_year"])
        self.assert_table_filter(
            ("--year", str(year)),
            lambda row: int(row["enrollment_year"]) == year,
        )

    def test_tui_query_uses_cli_option_names(self) -> None:
        query = parse_student_query("--major 元素 --year 2026 --status 在")
        self.assertEqual(query.major_codes, ("元素",))
        self.assertEqual(query.years, (2026,))
        self.assertEqual(query.statuses, ("在",))

        rows = self.catalog.rows(
            "students", query="--major 元素 --year 2026 --status 在"
        )
        expected = {
            str(row["student_no"])
            for row in self.students
            if self.contains(row, "元素", "major_code", "major_name")
            and int(row["enrollment_year"]) == 2026
            and "在" in str(row["status"])
        }
        self.assertEqual({str(row["student_no"]) for row in rows}, expected)

    def test_tui_query_accepts_plain_text_with_structured_filters(self) -> None:
        rows = self.catalog.rows("students", query="赤狐 --status 在读")
        expected = {
            str(row["student_no"])
            for row in self.students
            if self.contains(row, "赤狐", "branch")
            and "在读" in str(row["status"])
        }
        self.assertTrue(expected)
        self.assertEqual({str(row["student_no"]) for row in rows}, expected)

    def test_csv_format_can_be_written_to_stdout(self) -> None:
        output = self.run_xy("stu", "ls", "--major", "元素", "--format", "csv")
        reader = csv.DictReader(StringIO(output))
        self.assertEqual(reader.fieldnames, STUDENT_FIELDS)
        rows = list(reader)
        expected = {
            str(row["student_no"])
            for row in self.students
            if self.contains(row, "元素", "major_code", "major_name")
        }
        self.assertEqual({row["student_no"] for row in rows}, expected)

    def test_csv_format_can_be_written_to_file(self) -> None:
        target = Path(self.temp_dir.name) / "exports" / "element_students.csv"
        output = self.run_xy(
            "stu", "ls",
            "--major", "元素",
            "--format", "csv",
            "-o", str(target),
        )
        self.assertEqual(output, "")
        self.assertTrue(target.exists())

        with target.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            self.assertEqual(reader.fieldnames, STUDENT_FIELDS)
            rows = list(reader)
        expected = {
            str(row["student_no"])
            for row in self.students
            if self.contains(row, "元素", "major_code", "major_name")
        }
        self.assertEqual({row["student_no"] for row in rows}, expected)

    def test_default_table_can_be_written_to_file(self) -> None:
        target = Path(self.temp_dir.name) / "exports" / "element_students.txt"
        output = self.run_xy(
            "stu", "ls",
            "--major", "元素",
            "-o", str(target),
        )
        self.assertEqual(output, "")
        text = target.read_text(encoding="utf-8")
        self.assertIn("学号", text)
        expected = [
            row for row in self.students
            if self.contains(row, "元素", "major_code", "major_name")
        ]
        self.assertTrue(expected)
        for row in expected:
            self.assertIn(str(row["student_no"]), text)


if __name__ == "__main__":
    unittest.main()
