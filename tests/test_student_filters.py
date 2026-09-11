import csv
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.csv_io import STUDENT_FIELDS
from xingyuan_sis.entry import main as entry_main
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo


class StudentFilterCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.db_path)
        seed_demo(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_xy(self, *args: str) -> str:
        output = StringIO()
        with redirect_stdout(output):
            code = entry_main(["--db", str(self.db_path), *args])
        self.assertEqual(code, 0)
        return output.getvalue()

    def test_branch_filter_is_fuzzy(self) -> None:
        output = self.run_xy("stu", "ls", "--branch", "牧羊")
        self.assertIn("20250002", output)
        self.assertIn("20230001", output)
        self.assertNotIn("20260001", output)

    def test_major_matches_code_or_name_fuzzily(self) -> None:
        output = self.run_xy("stu", "ls", "--major", "元素")
        self.assertIn("20260001", output)
        self.assertIn("20250004", output)
        self.assertIn("20250001", output)
        self.assertNotIn("20260002", output)

        output = self.run_xy("stu", "ls", "--major", "ELS")
        self.assertIn("20260001", output)
        self.assertIn("20250004", output)
        self.assertNotIn("20250001", output)

    def test_class_and_college_match_code_or_name_fuzzily(self) -> None:
        output = self.run_xy("stu", "ls", "--class", "2601")
        self.assertIn("20260001", output)
        self.assertIn("20260002", output)
        self.assertIn("20260003", output)
        self.assertNotIn("20250004", output)

        output = self.run_xy("stu", "ls", "--college", "工程")
        self.assertIn("20250001", output)
        self.assertIn("20230001", output)
        self.assertNotIn("20260001", output)

    def test_filters_are_and_across_fields(self) -> None:
        output = self.run_xy(
            "stu", "ls",
            "--major", "元素",
            "--year", "2026",
            "--status", "在",
        )
        self.assertIn("20260001", output)
        self.assertNotIn("20250004", output)
        self.assertNotIn("20250001", output)

    def test_repeated_filter_is_or_within_field(self) -> None:
        output = self.run_xy(
            "stu", "ls",
            "--element", "风",
            "--element", "雷",
        )
        self.assertIn("20260001", output)
        self.assertIn("20250002", output)
        self.assertIn("20230001", output)
        self.assertNotIn("20260002", output)

    def test_search_combines_with_structured_filter(self) -> None:
        output = self.run_xy(
            "stu", "ls",
            "--status", "在读",
            "-s", "赤狐",
        )
        self.assertIn("20250004", output)
        self.assertIn("20240003", output)
        self.assertNotIn("20230002", output)

    def test_student_number_and_year_remain_exact(self) -> None:
        output = self.run_xy("stu", "ls", "--no", "20260001")
        self.assertIn("20260001", output)
        self.assertNotIn("20260002", output)

        output = self.run_xy("stu", "ls", "--year", "2026")
        self.assertIn("20260001", output)
        self.assertIn("20260002", output)
        self.assertNotIn("20250001", output)

    def test_csv_format_can_be_written_to_stdout(self) -> None:
        output = self.run_xy("stu", "ls", "--major", "元素", "--format", "csv")
        reader = csv.DictReader(StringIO(output))
        self.assertEqual(reader.fieldnames, STUDENT_FIELDS)
        rows = list(reader)
        self.assertEqual(
            {row["student_no"] for row in rows},
            {"20260001", "20250001", "20250004"},
        )
        self.assertEqual(
            {row["class_code"] for row in rows},
            {"ELS2601", "ELE2501", "ELS2501"},
        )

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
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["student_no"], "20250001")

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
        self.assertIn("20260001", text)
        self.assertIn("20250001", text)
        self.assertIn("20250004", text)


if __name__ == "__main__":
    unittest.main()
