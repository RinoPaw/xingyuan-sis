from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import screen, workspace
from xingyuan_sis.tui.workspace import student_inspector
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.inspector import action_targets, directional_target


class StudentCourseGridTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)
        self.state = workspace.Workspace(
            "students",
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
        )
        self.row = self.state.current(self.catalog)

    def _grade_rows(self, lines):
        return [
            line for line in lines
            if any(action.startswith("related:grades:") for _, _, action in line)
        ]

    def test_vertical_navigation_preserves_course_or_score_column(self):
        lines = student_inspector.lines(self.row, self.catalog)
        grade_rows = self._grade_rows(lines)
        self.assertGreaterEqual(len(grade_rows), 2)

        def actions(line):
            return [action for _, _, action in line if action]

        first, second = actions(grade_rows[0]), actions(grade_rows[1])
        first_course = next(action for action in first if action.startswith("related:grades:"))
        first_score = next(action for action in first if action.startswith("field:related:grades:"))
        second_course = next(action for action in second if action.startswith("related:grades:"))
        second_score = next(action for action in second if action.startswith("field:related:grades:"))

        self.assertEqual(directional_target(lines, first_course, "down"), second_course)
        self.assertEqual(directional_target(lines, first_score, "down"), second_score)
        self.assertEqual(directional_target(lines, second_course, "up"), first_course)
        self.assertEqual(directional_target(lines, second_score, "up"), first_score)

    def test_entering_course_score_grid_defaults_to_course(self):
        lines = student_inspector.lines(self.row, self.catalog)
        grade_rows = self._grade_rows(lines)
        first_course = next(
            action for _, _, action in grade_rows[0]
            if action.startswith("related:grades:")
        )
        targets = [action for _, action in action_targets(lines)]
        first_index = targets.index(first_course)
        self.assertGreater(first_index, 0)

        self.assertEqual(
            directional_target(lines, targets[first_index - 1], "down"),
            first_course,
        )

    def test_course_rows_share_one_separator_column_and_exact_spacing(self):
        baseline = student_inspector.lines(self.row, self.catalog)
        course_action = next(
            action for _, action in action_targets(baseline)
            if action.startswith("related:grades:")
        )
        self.state.detail_selected = next(
            index for index, (_, action) in enumerate(action_targets(baseline))
            if action == course_action
        )
        lines = student_inspector.lines(self.row, self.catalog, self.state)
        grade_rows = self._grade_rows(lines)

        separator_columns = []
        for line in grade_rows:
            separator_index = next(i for i, segment in enumerate(line) if segment[0] == " · ")
            self.assertEqual(line[separator_index][0], " · ")
            before = line[:separator_index]
            column = sum(screen._display_width(text) for text, _, _ in before)
            if any(action == course_action for _, _, action in before):
                column += 2  # the renderer replaces this row's reserved focus gutter with "> "
            separator_columns.append(column)

        self.assertEqual(len(set(separator_columns)), 1)


if __name__ == "__main__":
    unittest.main()
