from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.csv_io import export_students_csv, import_students_csv
from xingyuan_sis.database import connect, initialize_database
from xingyuan_sis.repository import Repository
from xingyuan_sis.seed_data import STUDENTS, seed_demo


class CsvTests(unittest.TestCase):
    def test_export_and_import_students(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source_db = root / "source.db"
            target_db = root / "target.db"
            csv_path = root / "students.csv"

            initialize_database(source_db)
            seed_demo(source_db)
            self.assertEqual(export_students_csv(csv_path, source_db), len(STUDENTS))

            # Reuse the canonical catalog from seed_data, then clear only the
            # student-owned rows so the CSV import gets a clean target roster.
            initialize_database(target_db)
            seed_demo(target_db)
            with connect(target_db) as connection:
                connection.execute("DELETE FROM enrollments")
                connection.execute("DELETE FROM students")

            result = import_students_csv(csv_path, target_db)
            self.assertEqual(result.imported, len(STUDENTS))
            self.assertEqual(result.errors, [])

            target = Repository(target_db)
            expected = STUDENTS[0]
            student = next(
                row for row in target.list_students()
                if row["student_no"] == expected[0]
            )
            self.assertEqual(student["name"], expected[1])
            self.assertEqual(student["family"], expected[2])
            self.assertEqual(student["branch"], expected[3])


if __name__ == "__main__":
    unittest.main()
