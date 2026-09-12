from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import STUDENTS, seed_demo
from xingyuan_sis.service import XingyuanService
from xingyuan_sis.species import SpeciesBranch, parse_species_branch


class SpeciesBranchTests(unittest.TestCase):
    def test_seed_uses_only_declared_branches(self) -> None:
        for student in STUDENTS:
            with self.subTest(student_no=student[0], branch=student[3]):
                self.assertEqual(parse_species_branch(str(student[3])).value, student[3])

    def test_parser_accepts_enum_and_text(self) -> None:
        self.assertIs(parse_species_branch(SpeciesBranch.GRAY_WOLF), SpeciesBranch.GRAY_WOLF)
        self.assertIs(parse_species_branch(" 灰狼 "), SpeciesBranch.GRAY_WOLF)

    def test_parser_rejects_unknown_branch(self) -> None:
        with self.assertRaisesRegex(ValueError, "未知种族支系"):
            parse_species_branch("龙")

    def test_service_stores_enum_value_and_rejects_unknown_branch(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "species.db"
            initialize_database(db_path)
            service = XingyuanService(db_path)

            service.create_student(
                student_no="20990001",
                name="测试学生",
                family="犬科",
                branch=SpeciesBranch.GRAY_WOLF,
                enrollment_year=2099,
            )
            self.assertEqual(service.student_by_no("20990001")["branch"], "灰狼")

            with self.assertRaisesRegex(ValueError, "未知种族支系"):
                service.create_student(
                    student_no="20990002",
                    name="无效学生",
                    family="未知",
                    branch="龙",
                    enrollment_year=2099,
                )

    def test_student_update_rejects_unknown_branch(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "species.db"
            initialize_database(db_path)
            seed_demo(db_path)
            service = XingyuanService(db_path)

            with self.assertRaisesRegex(ValueError, "未知种族支系"):
                service.update_student_by_no("20260001", branch="龙")
            self.assertEqual(service.student_by_no("20260001")["branch"], "石虎")


if __name__ == "__main__":
    unittest.main()
