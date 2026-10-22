"""Projection must avoid per-record SQL lookups when building GUI tables."""
import unittest
from unittest.mock import Mock

from xingyuan_sis.record_projection import project_record, project_records


class RecordProjectionTests(unittest.TestCase):
    def test_departments_are_looked_up_once_per_collection(self):
        service = Mock()
        service.list_departments.return_value = [
            {"id": 1, "code": "SCI"}, {"id": 2, "code": "ART"}
        ]
        rows = [{"id": 10, "department_id": 1},
                {"id": 11, "department_id": 2},
                {"id": 12, "department_id": None},
                {"id": 13, "department_id": 1, "department_code": "OVERRIDE"}]
        for key in ("majors", "courses"):
            with self.subTest(key=key):
                service.reset_mock()
                result = project_records(service, key, rows)
                self.assertEqual([r["department_code"] for r in result],
                                 ["SCI", "ART", None, "OVERRIDE"])
                self.assertNotIn("department_code", rows[0])
                service.list_departments.assert_called_once_with()

    def test_majors_are_looked_up_once_per_class_page(self):
        service = Mock()
        service.list_majors.return_value = [{"id": 3, "code": "ELS"}]
        rows = [{"major_id": 3}, {"major_id": 3}, {"major_id": 99}]
        result = project_records(service, "classes", rows)
        self.assertEqual([r["major_code"] for r in result], ["ELS", "ELS", None])
        service.list_majors.assert_called_once_with()

    def test_complete_or_empty_rows_need_no_related_queries(self):
        service = Mock()
        self.assertEqual(project_records(service, "majors", []), [])
        self.assertEqual(project_records(service, "classes", [{"major_code": "ELS"}]),
                         [{"major_code": "ELS"}])
        self.assertEqual(project_records(service, "students", [{"student_no": "0001"}]),
                         [{"student_no": "0001"}])
        service.list_departments.assert_not_called()
        service.list_majors.assert_not_called()

    def test_existing_single_record_api_remains_compatible(self):
        service = Mock()
        service.list_departments.return_value = [{"id": 1, "code": "SCI"}]
        self.assertEqual(project_record(service, "majors", {"department_id": 1}),
                         {"department_id": 1, "department_code": "SCI"})


if __name__ == "__main__":
    unittest.main()
