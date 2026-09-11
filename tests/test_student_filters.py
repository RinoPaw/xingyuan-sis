from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

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

    def test_exact_branch_filter(self) -> None:
        output = self.run_xy("stu", "ls", "--branch", "石虎")
        self.assertIn("20260001", output)
        self.assertIn("林岚", output)
        self.assertNotIn("20260002", output)

    def test_filters_are_and_across_fields(self) -> None:
        output = self.run_xy(
            "stu", "ls",
            "--major", "ELS",
            "--year", "2026",
            "--status", "在读",
        )
        self.assertIn("20260001", output)
        self.assertNotIn("20250004", output)
        self.assertNotIn("20260002", output)

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

    def test_name_is_fuzzy_but_codes_are_exact(self) -> None:
        output = self.run_xy("stu", "ls", "--name", "林")
        self.assertIn("林岚", output)

        output = self.run_xy("stu", "ls", "--class", "ELS2601")
        self.assertIn("20260001", output)
        self.assertNotIn("20250004", output)


if __name__ == "__main__":
    unittest.main()
