from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.csv_io import export_students_csv, import_students_csv
from xingyuan_sis.database import initialize_database
from xingyuan_sis.repository import Repository


class CsvTests(unittest.TestCase):
    def test_export_and_import_students(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source_db = root / "source.db"
            target_db = root / "target.db"
            csv_path = root / "students.csv"

            initialize_database(source_db)
            source = Repository(source_db)
            department_id = source.add_department("SCI", "自然科学学院")
            major_id = source.add_major("ELM", "元素学", department_id)
            class_id = source.add_class("ELM2601", "元素学2601班", major_id, 2026)
            source.add_student(
                student_no="20260001",
                name="林岚",
                family="猫科",
                branch="石虎",
                enrollment_year=2026,
                class_id=class_id,
                primary_element="风",
                primary_affinity="A",
            )

            self.assertEqual(export_students_csv(csv_path, source_db), 1)

            initialize_database(target_db)
            target = Repository(target_db)
            target_department_id = target.add_department("SCI", "自然科学学院")
            target_major_id = target.add_major("ELM", "元素学", target_department_id)
            target.add_class("ELM2601", "元素学2601班", target_major_id, 2026)

            result = import_students_csv(csv_path, target_db)
            self.assertEqual(result.imported, 1)
            self.assertEqual(result.errors, [])
            self.assertEqual(target.list_students()[0]["student_no"], "20260001")


if __name__ == "__main__":
    unittest.main()
