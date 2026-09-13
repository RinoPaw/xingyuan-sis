import unittest

from xingyuan_sis.tui import screen
from xingyuan_sis.tui.view_common import Board
from xingyuan_sis.tui.workspace_data import COLLECTIONS
from xingyuan_sis.tui.workspace_roster import _fit_columns, render_roster


class _State:
    key = "students"
    selected = 0
    roster_scroll = 0
    details = False
    action_focus = False
    form = None
    query = ""
    view = 0

    def __init__(self, rows):
        self._rows = rows

    def rows(self, catalog):
        return self._rows


class _Catalog:
    records = {"students": [{}]}


class RosterColumnTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{
            "name": "Calvin McMurray",
            "student_no": "20230016",
            "class_name": "电气工程2301班",
            "primary_element": "雷",
            "status": "在读",
        }]

    def test_unused_column_padding_is_reclaimed_before_truncating_text(self):
        columns = _fit_columns(COLLECTIONS["students"].columns, self.rows, 60)
        widths = {key: width for key, _, width in columns}

        self.assertEqual(len(columns), len(COLLECTIONS["students"].columns))
        self.assertGreaterEqual(widths["name"], screen._display_width("Calvin McMurray"))
        self.assertEqual(widths["student_no"], screen._display_width("20230016"))
        self.assertEqual(widths["primary_element"], screen._display_width("元素"))

    def test_render_uses_final_cell_before_truncating_name(self):
        board = Board(80, 24)
        render_roster(board, _State(self.rows), _Catalog(), 52)
        plain = "\n".join(screen._ANSI_RE.sub("", line) for line in board.frame().lines)
        self.assertIn("Calvin McMurray", plain)

    def test_narrow_layout_never_exceeds_available_width(self):
        available = 20
        columns = _fit_columns(COLLECTIONS["students"].columns, self.rows, available)
        occupied = sum(width for _, _, width in columns) + max(0, len(columns) - 1)
        self.assertLessEqual(occupied, available)


if __name__ == "__main__":
    unittest.main()
