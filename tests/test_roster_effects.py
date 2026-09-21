import unittest

from xingyuan_sis.tui import screen
from xingyuan_sis.tui.workspace import roster_effects


_HEAVY_BLOCKS = "█▓▒░▙▜▀▖▝"


class RosterEffectTests(unittest.TestCase):
    def test_print_is_a_thin_cursor_reveal_without_block_noise(self):
        frames = list(roster_effects._frames("print", "甲 ABC", 6))
        plain_frames = [screen._ANSI_RE.sub("", frame) for frame in frames]

        self.assertTrue(frames)
        self.assertTrue(any("▏" in frame for frame in plain_frames[:-1]))
        self.assertFalse(any(symbol in "".join(plain_frames) for symbol in _HEAVY_BLOCKS))
        self.assertEqual(plain_frames[-1], "甲 ABC")
        self.assertTrue(all(screen._display_width(frame) == 6 for frame in frames))

    def test_burn_consumes_text_with_sparse_embers_and_keeps_spaces_empty(self):
        frames = list(roster_effects._frames("burn", "A B", 3))
        plain_frames = [screen._ANSI_RE.sub("", frame) for frame in frames]

        self.assertTrue(plain_frames)
        self.assertTrue(all(frame[1] == " " for frame in plain_frames))
        self.assertFalse(any(symbol in "".join(plain_frames) for symbol in _HEAVY_BLOCKS))
        self.assertEqual(plain_frames[-1], "   ")
        self.assertTrue(all(screen._display_width(frame) == 3 for frame in frames))

    def test_burn_preserves_wide_character_geometry_while_disappearing(self):
        frames = list(roster_effects._frames("burn", "甲A", 3))

        self.assertTrue(frames)
        self.assertTrue(all(screen._display_width(frame) == 3 for frame in frames))
        self.assertEqual(screen._ANSI_RE.sub("", frames[-1]), "   ")

    def test_unknown_effect_is_rejected_instead_of_falling_back(self):
        with self.assertRaises(ValueError):
            list(roster_effects._frames("other", "AB", 2))


if __name__ == "__main__":
    unittest.main()
