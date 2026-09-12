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

        self.assertGreater(len(families), 20)
        self.assertGreater(len(branches), 60)
        gray_wolf = self.service.species_branch_by_name("灰狼", "犬科")
        self.assertIsNotNone(gray_wolf)
        self.assertEqual(gray_wolf["family_name"], "犬科")

        with connect(self.db_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(students)")}
            self.assertIn("species_branch_id", columns)
            self.assertNotIn("family", columns)
            self.assertNotIn("branch", columns)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_student_species_is_resolved_through_branch(self) -> None:
        student = self.service.student_by_no("20260004")
        self.assertEqual(student["name"], "雷格西")
        self.assertEqual(student["family"], "犬科")
        self.assertEqual(student["branch"], "灰狼")

        with self.assertRaisesRegex(ValueError, "找不到种族支系"):
            self.service.create_student(
                student_no="20990001",
                name="错误组合",
                family="猫科",
                branch="灰狼",
                enrollment_year=2099,
            )

    def test_branch_cannot_be_deleted_while_students_reference_it(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.delete_species_branch_by_name("灰狼", family="犬科")

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


class LegacySpeciesMigrationTests(unittest.TestCase):
    def test_legacy_family_and_branch_columns_are_migrated(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "legacy.db"
            connection = sqlite3.connect(db_path)
            connection.executescript(
                """
                CREATE TABLE students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_no TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    family TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    gender TEXT,
                    birth_date TEXT,
                    enrollment_year INTEGER NOT NULL,
                    class_id INTEGER,
                    status TEXT NOT NULL DEFAULT '在读',
                    primary_element TEXT,
                    primary_affinity TEXT,
                    contact TEXT,
                    dormitory TEXT,
                    notes TEXT
                );
                INSERT INTO students(student_no, name, family, branch, enrollment_year)
                VALUES ('20250001', '旧生', '犬科', '灰狼', 2025);
                """
            )
            connection.close()

            initialize_database(db_path)
            service = XingyuanService(db_path)
            student = service.student_by_no("20250001")
            self.assertEqual(student["family"], "犬科")
            self.assertEqual(student["branch"], "灰狼")

            with connect(db_path) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(students)")}
                self.assertNotIn("family", columns)
                self.assertNotIn("branch", columns)
                self.assertIn("species_branch_id", columns)


if __name__ == "__main__":
    unittest.main()
