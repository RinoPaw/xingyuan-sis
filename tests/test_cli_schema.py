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

    def test_student_list_filters_live_in_the_main_schema(self):
        args = build_parser().parse_args([
            "stu", "ls",
            "--major", "元素",
            "--year", "2026",
            "--format", "csv",
            "-o", "students.csv",
        ])
        self.assertEqual(args.group, "stu")
        self.assertEqual(args.action, "ls")
        self.assertEqual(args.major_codes, ["元素"])
        self.assertEqual(args.years, [2026])
        self.assertEqual(args.format, "csv")
        self.assertEqual(args.output.name, "students.csv")


if __name__ == "__main__":
    unittest.main()
