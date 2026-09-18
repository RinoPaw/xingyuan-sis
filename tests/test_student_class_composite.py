from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui.workspace import forms, student_inspector
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.state import Workspace


class StudentClassCompositeTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def test_class_has_the_same_two_target_shape_as_species_and_element(self):
        field_keys = [field.key for field in self.catalog.fields("students")]
        self.assertNotIn("class_code", field_keys)
        self.assertEqual(
            field_keys[field_keys.index("family"):field_keys.index("family") + 2],
            ["family", "branch"],
        )
        self.assertEqual(
            field_keys[field_keys.index("major_code"):field_keys.index("major_code") + 2],
            ["major_code", "class_number"],
        )
        self.assertEqual(
            field_keys[field_keys.index("primary_element"):field_keys.index("primary_element") + 2],
            ["primary_element", "primary_affinity"],
        )

        row = self.catalog.rows("students")[0]
        class_line = next(
            line for line in student_inspector.lines(row, self.catalog)
            if line and line[0][0].startswith("班级")
        )
        self.assertEqual(
            [action for _, _, action in class_line if action],
            ["field:major_code", "field:class_number"],
        )

    def test_create_form_persists_major_and_class_number_as_canonical_class(self):
        state = Workspace("students")
        forms.open_form(state, self.catalog, "create")
        target = self.catalog.records["classes"][0]
        sample = self.catalog.records["students"][0]
        state.form.values.update(
            student_no="29999999",
            name="复合班级测试",
            family=sample["family"],
            branch=sample["branch"],
            enrollment_year=target["enrollment_year"],
            major_code=target["major_code"],
            class_number=self.catalog.class_numbers[target["id"]],
        )

        forms.apply_form(state, self.catalog)

        created = self.catalog.service.student_by_no("29999999")
        self.assertIsNotNone(created)
        self.assertEqual(created["class_code"], target["code"])
        self.assertEqual(created["class_id"], target["id"])


if __name__ == "__main__":
    unittest.main()
