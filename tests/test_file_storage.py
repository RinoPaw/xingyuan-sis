from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import sqlite3
import unittest

from xingyuan_sis.auth import INITIAL_STUDENT_PASSWORD, authenticate
from xingyuan_sis.database import initialize_database
from xingyuan_sis.file_storage import JsonRepository, MemoryRepository, archive_payload
from xingyuan_sis.service import XingyuanService


class StorageStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.file = self.folder / "campus.json"
        self.repository = MemoryRepository()
        self.service = XingyuanService(repository=self.repository)
        self.populate(self.service)

    @staticmethod
    def populate(s):
        s.create_department(code="SCI", name="自然科学学院")
        s.create_major(code="ELS", name="元素学", department_code="SCI")
        s.create_class(code="ELS2601", name="元素学2601班", major_code="ELS", enrollment_year=2026)
        s.create_species_family(name="犬科")
        s.create_species_branch(name="灰狼", family="犬科")
        s.register_student(student_no="00001", name="示例同窗", family="犬科", branch="灰狼", enrollment_year=2026, class_code="ELS2601", birth_date="--04-09")
        s.create_course(course_code="EL1", name="元素学导论", department_code="SCI", credits=3, hours=48)
        s.add_grade(student_no="00001", course_code="EL1", semester="2026-秋", score=None)
        s.create_announcement(title="本班通知", body="第一段\n第二段", class_code="ELS2601")

    def test_memory_does_not_touch_disk_and_uses_service_validation(self):
        self.assertEqual(list(self.folder.iterdir()), [])
        with self.assertRaisesRegex(ValueError, "姓名不能修改"):
            self.service.update_student_by_no("00001", name="新名字")
        with self.assertRaises(ValueError):
            self.service.update_grade(student_no="00001", course_code="EL1", semester="2026-秋", score=101)

    def test_json_restart_then_edit_and_restart(self):
        repository = JsonRepository(self.file)
        repository.restore_archive(self.repository.data)
        reopened = XingyuanService(repository=JsonRepository(self.file))
        reopened.update_student_by_no("00001", notes="重启后的修改")
        again = XingyuanService(repository=JsonRepository(self.file))
        self.assertEqual(again.student_by_no("00001")["notes"], "重启后的修改")
        self.assertEqual(again.list_announcements("00001")[0]["body"], "第一段\n第二段")
        self.assertIsNone(again.enrollments_for_student("00001")[0]["score"])

    def test_failed_atomic_file_save_rolls_back_memory_and_retains_file(self):
        repository = JsonRepository(self.file)
        repository.restore_archive(self.repository.data)
        before = self.file.read_bytes()
        service = XingyuanService(repository=repository)
        with patch("xingyuan_sis.file_storage.os.replace", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                service.update_student_by_no("00001", notes="不应保存")
        self.assertIsNone(service.student_by_no("00001")["notes"])
        self.assertEqual(self.file.read_bytes(), before)
        self.assertEqual(list(self.folder.glob("*.tmp")), [])

    def test_corrupt_file_is_not_silently_overwritten(self):
        self.file.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            JsonRepository(self.file)
        self.assertEqual(self.file.read_text(), "{broken")

    def test_sqlite_json_sqlite_roundtrip_is_complete_and_credentials_are_reset(self):
        source_db = self.folder / "source.db"
        target_db = self.folder / "target.db"
        initialize_database(source_db)
        source = XingyuanService(source_db)
        self.populate(source)
        source.export_archive(self.file)
        text = self.file.read_text(encoding="utf-8")
        self.assertNotIn("password_hash", text)
        self.assertNotIn("must_change_password", text)
        initialize_database(target_db)
        target = XingyuanService(target_db)
        target.import_archive(self.file)
        self.assertEqual(archive_payload(source), archive_payload(target))
        identity = authenticate(target_db, "00001", INITIAL_STUDENT_PASSWORD)
        self.assertTrue(identity.must_change_password)

    def test_nonempty_target_refuses_archive_without_changing_existing_data(self):
        self.service.export_archive(self.file)
        db = self.folder / "target.db"
        initialize_database(db)
        target = XingyuanService(db)
        target.create_department(code="OLD", name="原学院")
        with self.assertRaisesRegex(ValueError, "空库"):
            target.import_archive(self.file)
        self.assertEqual([r["code"] for r in target.list_departments()], ["OLD"])
        self.assertEqual(target.list_students(), [])

    def test_invalid_last_record_does_not_partially_import(self):
        payload = archive_payload(self.service)
        payload["records"]["announcements"][0]["class_code"] = "MISSING"
        self.file.write_text(json.dumps(payload), encoding="utf-8")
        db = self.folder / "target.db"
        initialize_database(db)
        with self.assertRaises(ValueError):
            XingyuanService(db).import_archive(self.file)
        self.assertEqual(XingyuanService(db).list_departments(), [])

    def test_repository_rolls_back_sqlite_insertion_failure(self):
        db = self.folder / "target.db"
        initialize_database(db)
        from copy import deepcopy
        invalid = deepcopy(self.repository.data)
        invalid["announcements"][0]["class_id"] = 9999
        with self.assertRaises(sqlite3.IntegrityError):
            XingyuanService(db).repository.restore_archive(invalid)
        self.assertEqual(XingyuanService(db).list_departments(), [])

    def test_memory_delete_uses_relationship_rules(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.delete_department_by_code("SCI")
        self.service.delete_class_by_code("ELS2601")
        self.assertIsNone(self.service.student_by_no("00001")["class_code"])
        self.assertEqual(self.service.list_announcements(), [])
        self.service.delete_student_by_no("00001")
        self.assertEqual(self.service.list_enrollments(), [])


if __name__ == "__main__":
    unittest.main()
