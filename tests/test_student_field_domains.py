from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.service import XingyuanService
from xingyuan_sis.tui.workspace.data import Catalog


class StudentFieldDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        self.service = XingyuanService(self.db)
        self.service.create_species_family(name="测试族系")
        self.service.create_species_branch(name="测试支系", family="测试族系")

    def test_student_picker_vocabulary_is_not_a_domain_enum(self) -> None:
        custom_values = {
            "status": "交换培养",
            "gender": "未说明",
            "primary_element": "冰",
            "primary_affinity": "S",
        }
        self.service.register_student(
            student_no="20999999",
            name="自定义字段学生",
            family="测试族系",
            branch="测试支系",
            enrollment_year=2026,
            **custom_values,
        )

        row = self.service.student_by_no("20999999")
        self.assertIsNotNone(row)
        for field, value in custom_values.items():
            with self.subTest(field=field):
                self.assertEqual(row[field], value)

        catalog = Catalog(self.db)
        defaults = {
            "status": "在读",
            "gender": "男",
            "primary_element": "风",
            "primary_affinity": "A",
        }
        for field, custom_value in custom_values.items():
            with self.subTest(field=field):
                options = catalog.options("students", field)
                self.assertIsNotNone(options)
                values = [value for value, _ in options]
                self.assertIn(defaults[field], values)
                self.assertIn(custom_value, values)


if __name__ == "__main__":
    unittest.main()
