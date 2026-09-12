import unittest

from xingyuan_sis.cli_schema import build_parser


class CliSchemaTests(unittest.TestCase):
    def test_academic_entities_are_top_level_commands(self):
        parser = build_parser()
        for entity in ("college", "major", "class"):
            with self.subTest(entity=entity):
                args = parser.parse_args([entity, "ls"])
                self.assertEqual(args.group, entity)
                self.assertEqual(args.entity, entity)
                self.assertEqual(args.action, "ls")

    def test_acad_namespace_no_longer_exists(self):
        parser = build_parser()
        with self.assertRaises(SystemExit) as error:
            parser.parse_args(["acad", "college", "ls"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
