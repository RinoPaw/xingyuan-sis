from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from xingyuan_sis.database import connect, initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.service import XingyuanService


class SpeciesCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "species.db"
        initialize_database(self.db_path)
        seed_demo(self.db_path)
        self.service = XingyuanService(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_species_are_first_class_database_entities(self) -> None:
        families = self.service.list_species_families()
        branches = self.service.list_species_branches()
        students = self.service.list_students()

        self.assertTrue(families)
        self.assertTrue(branches)
        family_names = {row["name"] for row in families}
        branch_pairs = {(row["family_name"], row["name"]) for row in branches}
        self.assertTrue(all(row["family_name"] in family_names for row in branches))
        self.assertTrue(
            {(row["family"], row["branch"]) for row in students}.issubset(branch_pairs)
        )

        with connect(self.db_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(students)")}
            self.assertIn("species_branch_id", columns)
            self.assertNotIn("family", columns)
            self.assertNotIn("branch", columns)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_student_species_is_resolved_through_branch(self) -> None:
        expected = self.service.list_students()[0]
        student = self.service.student_by_no(expected["student_no"])
        branch = self.service.species_branch_by_name(expected["branch"], expected["family"])

        self.assertIsNotNone(student)
        self.assertIsNotNone(branch)
        self.assertEqual(student["family"], expected["family"])
        self.assertEqual(student["branch"], expected["branch"])
        self.assertEqual(branch["family_name"], expected["family"])

        other_family = next(
            row["name"] for row in self.service.list_species_families()
            if row["name"] != expected["family"]
        )
        with self.assertRaisesRegex(ValueError, "找不到种族支系"):
            self.service.create_student(
                student_no="20990001",
                name="错误组合",
                family=other_family,
                branch=expected["branch"],
                enrollment_year=2099,
            )

    def test_branch_cannot_be_deleted_while_students_reference_it(self) -> None:
        student = self.service.list_students()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.delete_species_branch_by_name(
                student["branch"], family=student["family"]
            )

    def test_species_catalog_supports_crud(self) -> None:
        self.service.create_species_family(name="测试族系")
        self.service.create_species_branch(name="测试支系", family="测试族系")
        self.assertIsNotNone(self.service.species_branch_by_name("测试支系", "测试族系"))

        self.service.update_species_branch_by_name(
            "测试支系",
            family="测试族系",
            new_name="新测试支系",
        )
        self.assertIsNotNone(self.service.species_branch_by_name("新测试支系", "测试族系"))

        self.service.delete_species_branch_by_name("新测试支系", family="测试族系")
        self.service.delete_species_family_by_name("测试族系")
        self.assertIsNone(self.service.species_family_by_name("测试族系"))


if __name__ == "__main__":
    unittest.main()
