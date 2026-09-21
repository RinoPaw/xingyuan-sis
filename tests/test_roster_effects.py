import unittest
from unittest.mock import call, patch

from xingyuan_sis.tui import animation, screen
from xingyuan_sis.tui.effects.effect_burn import Burn
from xingyuan_sis.tui.effects.effect_print import Print
from xingyuan_sis.tui.workspace import roster_effects


class RosterEffectTests(unittest.TestCase):
    def test_effect_classes_are_the_local_ports(self):
        self.assertEqual(Burn.__module__, "xingyuan_sis.tui.effects.effect_burn")
        self.assertEqual(Print.__module__, "xingyuan_sis.tui.effects.effect_print")

    def test_effect_keeps_tte_native_canvas_geometry(self):
        effect = roster_effects._effect("print", "AB")

        self.assertEqual(effect.terminal_config.canvas_width, -1)
        self.assertEqual(effect.terminal_config.canvas_height, -1)

    def test_print_uses_roster_speed_without_rewriting_the_effect(self):
        effect = roster_effects._effect("print", "AB")

        self.assertEqual(effect.effect_config.print_speed, 4)

    def test_print_frames_are_not_projected_to_one_line(self):
        with patch.object(roster_effects, "_effect", return_value=("top\nbottom",)):
            frames = list(roster_effects._frames("print", "AB"))

        self.assertEqual(frames, ["top\nbottom"])

    def test_print_keeps_the_upstream_block_typing_sequence(self):
        frames = list(roster_effects._frames("print", "AB"))
        plain = "".join(screen._ANSI_RE.sub("", frame) for frame in frames)

        self.assertTrue(frames)
        self.assertTrue(any(symbol in plain for symbol in "█▓▒░"))
        self.assertIn("AB", screen._ANSI_RE.sub("", frames[-1]))

    def test_burn_makes_blank_roster_cells_part_of_the_input(self):
        effect = roster_effects._effect("burn", " A ")

        self.assertEqual(effect.input_data, "\u00a0A\u00a0")

    def test_burn_keeps_the_upstream_fire_glyphs(self):
        frames = list(roster_effects._frames("burn", "AB"))
        plain = "".join(screen._ANSI_RE.sub("", frame) for frame in frames)

        self.assertTrue(frames)
        self.assertTrue(any(symbol in plain for symbol in "▖▙█▜▀▝"))

    def test_burn_does_not_restore_deleted_source_text(self):
        frames = list(roster_effects._frames("burn", "A B"))
        last = screen._ANSI_RE.sub("", frames[-1]).replace("\u00a0", " ")

        self.assertNotIn("A", last)
        self.assertNotIn("B", last)

    def test_unknown_effect_is_rejected_instead_of_falling_back(self):
        with self.assertRaises(ValueError):
            list(roster_effects._frames("other", "AB"))

    def test_animation_layer_repaints_base_once_and_restores_only_uncovered_rows(self):
        base = ("one", "two", "three")
        with (
            patch.object(animation, "_paint") as paint,
            patch.object(animation, "_paint_region") as paint_region,
            patch.object(animation.time, "sleep"),
        ):
            animation.play_region_frames(base, 4, 3, 8, ("top\nbottom", "done"))

        paint.assert_called_once_with(base)
        self.assertEqual(
            paint_region.call_args_list,
            [
                call(4, 2, 8, "top"),
                call(4, 3, 8, "bottom"),
                call(1, 2, 3, "two"),
                call(4, 3, 8, "done"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
