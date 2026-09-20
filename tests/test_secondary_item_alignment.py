import os
import unittest
from unittest.mock import patch

from xingyuan_sis.tui import screen, theme


class SecondaryItemAlignmentTests(unittest.TestCase):
    def test_secondary_labels_are_centered_and_selection_does_not_move_them(self) -> None:
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ) as environment:
            environment.pop("NO_COLOR", None)
            for label in ("学生", "个人数据"):
                with self.subTest(label=label):
                    plain = screen._ANSI_RE.sub("", theme.secondary_item(label, width=10))
                    selected = screen._ANSI_RE.sub(
                        "", theme.secondary_item(label, selected=True, width=10)
                    )

                    self.assertEqual(screen._display_width(plain), 10)
                    self.assertEqual(screen._display_width(selected), 10)

                    plain_start = plain.index(label)
                    selected_start = selected.index(label)
                    self.assertEqual(selected_start, plain_start)

                    label_width = screen._display_width(label)
                    left = screen._display_width(plain[:plain_start])
                    right = 10 - left - label_width
                    self.assertLessEqual(abs(left - right), 1)
                    self.assertLess(selected.index(">"), selected_start)


if __name__ == "__main__":
    unittest.main()
