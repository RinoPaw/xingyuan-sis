from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import workspace
from xingyuan_sis.tui.workspace import detail, field_session, student_inspector
from xingyuan_sis.tui.workspace.data import Catalog


class InlineEditIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    @staticmethod
    def _student_text(lines):
        return ["".join(text for text, _, _ in line) for line in lines]

    @staticmethod
    def _generic_text(lines):
        return ["".join(text for text, _, _ in line) for line in lines]

    def test_student_field_session_only_projects_owned_values(self):
        state = workspace.Workspace("students", details=True)
        row = state.current(self.catalog)
        baseline = self._student_text(student_inspector.lines(row, self.catalog))

        field_session.start(state, self.catalog, "enrollment_year")
        editing = self._student_text(student_inspector.lines(row, self.catalog, state))

        self.assertEqual(baseline, editing)
        baseline_class = next(line for line in baseline if line.startswith("班级"))
        editing_class = next(line for line in editing if line.startswith("班级"))
        self.assertEqual(baseline_class, editing_class)
        self.assertIn(" · ", editing_class)

    def test_generic_inspectors_do_not_reformat_unrelated_fields_during_field_session(self):
        cases = (
            ("courses", "name"),
            ("grades", "semester"),
            ("departments", "name"),
            ("majors", "name"),
            ("classes", "name"),
        )
        for collection, field_key in cases:
            with self.subTest(collection=collection):
                state = workspace.Workspace(collection, details=True)
                row = state.current(self.catalog)
                baseline = self._generic_text(detail.lines(collection, row, self.catalog))

                field_session.start(state, self.catalog, field_key)
                editing = self._generic_text(detail.lines(collection, row, self.catalog, state))

                self.assertEqual(baseline, editing)


if __name__ == "__main__":
    unittest.main()
