from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui.workspace import field_session, forms, student_inspector
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.presentation import display_value
from xingyuan_sis.tui.workspace.student_layout import STUDENT_FIELD_ROWS
from xingyuan_sis.tui.workspace.state import FieldSessionOwner, Workspace


class StudentClassCompositeTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def test_species_class_and_element_share_the_same_two_target_shape(self):
        field_keys = [field.key for field in self.catalog.fields("students")]
        self.assertNotIn("class_code", field_keys)
        for first, second in (
            ("family", "branch"),
            ("major_code", "class_number"),
            ("primary_element", "primary_affinity"),
        ):
            with self.subTest(group=(first, second)):
                index = field_keys.index(first)
                self.assertEqual(field_keys[index:index + 2], [first, second])
                self.assertEqual(
                    [field.key for field in self.catalog.field_group("students", first)],
                    [first, second],
                )
                self.assertEqual(
                    [field.key for field in self.catalog.edit_group("students", first)],
                    [first, second],
                )

        row = self.catalog.rows("students")[0]
        lines = student_inspector.lines(row, self.catalog)
        expected = {
            "物种": ["field:family", "field:branch"],
            "班级": ["field:major_code", "field:class_number"],
            "元素": ["field:primary_element", "field:primary_affinity"],
        }
        for label, actions in expected.items():
            with self.subTest(label=label):
                line = next(line for line in lines if line and line[0][0].startswith(label))
                self.assertEqual([action for _, _, action in line if action], actions)

    def test_unset_composite_children_remain_visible_and_focusable(self):
        groups = (
            ("family", ("family", "branch"), ("branch",)),
            ("major_code", ("major_code", "class_number"), ("class_number",)),
            ("primary_element", ("primary_element", "primary_affinity"), ("primary_affinity",)),
            ("dorm_area", ("dorm_area", "dorm_building", "dorm_room"),
             ("dorm_building", "dorm_room")),
        )
        for anchor, keys, missing in groups:
            with self.subTest(group=anchor):
                state = Workspace("students")
                field_session.start(state, self.catalog, anchor)
                for key in missing:
                    state.field_session.values[key] = None
                row = next(
                    line for line in student_inspector.lines(
                        state.current(self.catalog), self.catalog, state
                    )
                    if sum(action.startswith("field:") for _, _, action in line) == len(keys)
                    and any(action == f"field:{anchor}" for _, _, action in line)
                )
                segments = [(value, action) for value, _, action in row if action]
                self.assertEqual([action for _, action in segments], [f"field:{key}" for key in keys])
                for key in missing:
                    self.assertIn(("未指定", f"field:{key}"), segments)

                # The visible placeholders must also survive when every part
                # of the semantic field is empty.
                for key in keys:
                    state.field_session.values[key] = None
                empty = next(
                    line for line in student_inspector.lines(
                        state.current(self.catalog), self.catalog, state
                    )
                    if any(action == f"field:{anchor}" for _, _, action in line)
                )
                self.assertEqual(
                    [(value, action) for value, _, action in empty if action],
                    [("未指定", f"field:{key}") for key in keys],
                )

    def test_unset_composite_fields_are_labeled_in_create_form_too(self):
        state = Workspace("students")
        forms.open_form(state, self.catalog, "create")
        values = dict(state.form.values)
        for row in STUDENT_FIELD_ROWS:
            if len(row.keys) < 2:
                continue
            for key in row.keys:
                with self.subTest(group=row.label, field=key):
                    self.assertEqual(
                        display_value(self.catalog, "students", values | {key: None}, key),
                        "未指定",
                    )

    def test_create_form_parent_choice_never_auto_advances_to_child(self):
        for first, second in (
            ("family", "branch"),
            ("major_code", "class_number"),
            ("primary_element", "primary_affinity"),
        ):
            with self.subTest(group=(first, second)):
                state = Workspace("students")
                forms.open_form(state, self.catalog, "create")
                form = state.form
                form.position = next(i for i, field in enumerate(form.fields) if field.key == first)

                field_session.start_form(state, self.catalog)
                self.assertIs(state.field_session.owner, FieldSessionOwner.FORM)
                self.assertEqual(
                    [field.key for field in state.field_session.fields],
                    [first, second],
                )
                field_session.edit_current(state, self.catalog)
                parent_index = next(
                    i for i, (value, _) in enumerate(state.field_session.options)
                    if value is not None
                )
                parent_value = state.field_session.options[parent_index][0]
                field_session.accept_option(state, self.catalog, parent_index)

                self.assertIsNone(state.field_session)
                self.assertEqual(form.values.get(first), parent_value)
                self.assertEqual(form.position, next(i for i, field in enumerate(form.fields) if field.key == first))

                form.position = next(i for i, field in enumerate(form.fields) if field.key == second)
                field_session.start_form(state, self.catalog)
                self.assertEqual([field.key for field in state.field_session.fields], [second])

    def test_invalid_dependent_child_waits_for_explicit_right_navigation(self):
        state = Workspace("students")
        original = state.current(self.catalog).copy()
        original_branch = original["branch"]
        families = self.catalog.options("students", "family", original)
        target_family = next(
            family for family, _ in families
            if family != original["family"] and original_branch not in {
                row["name"] for row in self.catalog.species_branches
                if row["family_name"] == family
            }
        )

        field_session.start(state, self.catalog, "family")
        field_session.edit_current(state, self.catalog)
        family_index = next(
            i for i, (value, _) in enumerate(state.field_session.options)
            if value == target_family
        )
        field_session.accept_option(state, self.catalog, family_index)

        self.assertIsNotNone(state.field_session)
        self.assertEqual(state.field_session.active_key, "family")
        self.assertIsNone(state.field_session.options)
        self.assertIsNone(state.field_session.values["branch"])
        self.assertEqual(
            self.catalog.service.student_by_no(original["student_no"])["family"],
            original["family"],
        )

        self.assertTrue(field_session.move_active_field(state, "right"))
        self.assertEqual(state.field_session.active_key, "branch")
        field_session.edit_current(state, self.catalog)
        branch_index = next(
            i for i, (value, _) in enumerate(state.field_session.options)
            if value is not None
        )
        target_branch = state.field_session.options[branch_index][0]
        field_session.accept_option(state, self.catalog, branch_index)

        self.assertIsNone(state.field_session)
        changed = self.catalog.service.student_by_no(original["student_no"])
        self.assertEqual((changed["family"], changed["branch"]), (target_family, target_branch))

    def test_valid_parent_change_commits_without_visiting_child(self):
        state = Workspace("students")
        original = state.current(self.catalog).copy()
        field_session.start(state, self.catalog, "primary_element")
        field_session.edit_current(state, self.catalog)
        option_index = next(
            i for i, (value, _) in enumerate(state.field_session.options)
            if value not in {None, original["primary_element"]}
        )
        selected = state.field_session.options[option_index][0]
        field_session.accept_option(state, self.catalog, option_index)

        self.assertIsNone(state.field_session)
        self.assertEqual(
            self.catalog.service.student_by_no(original["student_no"])["primary_element"],
            selected,
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
