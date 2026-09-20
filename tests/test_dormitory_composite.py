from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import workspace
from xingyuan_sis.tui.workspace import student_inspector
from xingyuan_sis.tui.workspace.data import Catalog


class DormitoryCompositeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def test_canonical_dormitory_is_projected_as_three_fields(self):
        raw = self.catalog.records["students"][0]
        row = self.catalog.rows("students")[0]
        area, rest = raw["dormitory"].split(" ", 1)
        building, room = rest.split("-", 1)

        self.assertNotIn("dorm_area", raw)
        self.assertEqual(
            (row["dorm_area"], row["dorm_building"], row["dorm_room"]),
            (area, building, room),
        )

        line = next(
            line for line in student_inspector.lines(raw, self.catalog)
            if line and line[0][0].startswith("宿舍")
        )
        self.assertEqual(
            [action for _, _, action in line if action],
            ["field:dorm_area", "field:dorm_building", "field:dorm_room"],
        )
        self.assertEqual("".join(text for text, _, _ in line), f"宿舍      {area} · {building} · {room}")

    def test_dormitory_options_follow_area_then_building(self):
        rows = self.catalog.rows("students")
        row = rows[0]
        values = dict(row)

        area_options = self.catalog.options("students", "dorm_area", values)
        self.assertIn(row["dorm_area"], [value for value, _ in area_options])

        building_options = self.catalog.options("students", "dorm_building", values)
        expected_buildings = list(dict.fromkeys(
            student["dorm_building"]
            for student in rows
            if student.get("dorm_area") == row["dorm_area"] and student.get("dorm_building")
        ))
        self.assertEqual([value for value, _ in building_options], [None, *expected_buildings])

        room_options = self.catalog.options("students", "dorm_room", values)
        expected_rooms = list(dict.fromkeys(
            student["dorm_room"]
            for student in rows
            if student.get("dorm_area") == row["dorm_area"]
            and student.get("dorm_building") == row["dorm_building"]
            and student.get("dorm_room")
        ))
        self.assertEqual([value for value, _ in room_options], [None, *expected_rooms])

    def test_three_virtual_fields_save_back_to_one_canonical_value(self):
        state = workspace.Workspace("students")
        original = state.current(self.catalog)
        record_id = original["id"]

        self.catalog.save(
            "students",
            {"dorm_area": "西区", "dorm_building": "5", "dorm_room": "152"},
            original,
        )

        raw = next(row for row in self.catalog.records["students"] if row["id"] == record_id)
        updated = next(row for row in self.catalog.rows("students") if row["id"] == record_id)
        self.assertEqual(raw["dormitory"], "西区 5-152")
        self.assertEqual(
            (updated["dorm_area"], updated["dorm_building"], updated["dorm_room"]),
            ("西区", "5", "152"),
        )

    def test_partial_dormitory_is_rejected(self):
        original = self.catalog.records["students"][0]
        with self.assertRaisesRegex(ValueError, "区 · 楼 · 房间"):
            self.catalog.save(
                "students",
                {"dorm_area": "西区", "dorm_building": None, "dorm_room": "152"},
                original,
            )


if __name__ == "__main__":
    unittest.main()
