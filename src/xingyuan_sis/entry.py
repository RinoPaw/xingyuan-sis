from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from .cli import main as cli_main, print_table
from .database import initialize_database
from .service import XingyuanService
from .student_filters import query_students


def _student_list_requested(argv: Sequence[str]) -> bool:
    tokens = list(argv)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--db":
            index += 2
            continue
        if token.startswith("--db="):
            index += 1
            continue
        break
    return (
        index + 1 < len(tokens)
        and tokens[index] in {"stu", "student"}
        and tokens[index + 1] in {"ls", "list"}
    )


def _student_list_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xy stu ls",
        description="列出学生；不同字段之间按 AND，同一字段重复时按 OR。",
    )
    parser.add_argument("--db", type=Path, help="使用指定 SQLite 数据库")
    parser.add_argument("group", choices=("stu", "student"), help=argparse.SUPPRESS)
    parser.add_argument("action", choices=("ls", "list"), help=argparse.SUPPRESS)
    parser.add_argument("-s", "--search", default="", help="全字段模糊搜索")
    parser.add_argument("--no", dest="student_nos", action="append", metavar="学号", help="精确匹配学号，可重复")
    parser.add_argument("--name", dest="names", action="append", metavar="姓名", help="姓名包含，可重复")
    parser.add_argument("--family", dest="families", action="append", metavar="族系", help="精确匹配族系，可重复")
    parser.add_argument("--branch", dest="branches", action="append", metavar="支系", help="精确匹配支系，可重复")
    parser.add_argument("--class", dest="class_codes", action="append", metavar="班级编号", help="精确匹配班级编号，可重复")
    parser.add_argument("--major", dest="major_codes", action="append", metavar="专业编号", help="精确匹配专业编号，可重复")
    parser.add_argument(
        "--college", "--department",
        dest="college_codes",
        action="append",
        metavar="学院编号",
        help="精确匹配学院编号，可重复",
    )
    parser.add_argument("--year", dest="years", action="append", type=int, metavar="年份", help="精确匹配入学年份，可重复")
    parser.add_argument("--status", dest="statuses", action="append", metavar="状态", help="精确匹配状态，可重复")
    parser.add_argument("--element", dest="elements", action="append", metavar="元素", help="精确匹配主元素，可重复")
    parser.add_argument("--affinity", dest="affinities", action="append", metavar="等级", help="精确匹配亲和等级，可重复")
    return parser


def _run_student_list(argv: Sequence[str]) -> int:
    parser = _student_list_parser()
    args = parser.parse_args(argv)
    initialize_database(args.db)
    service = XingyuanService(args.db)
    rows = query_students(
        service,
        search=args.search,
        student_nos=args.student_nos,
        names=args.names,
        families=args.families,
        branches=args.branches,
        class_codes=args.class_codes,
        major_codes=args.major_codes,
        college_codes=args.college_codes,
        years=args.years,
        statuses=args.statuses,
        elements=args.elements,
        affinities=args.affinities,
    )
    print_table(
        ("学号", "姓名", "支系", "班级", "专业", "主元素", "状态"),
        (
            (
                row.student_no,
                row.name,
                row.branch,
                row.class_name,
                row.major_name,
                row.primary_element,
                row.status,
            )
            for row in rows
        ),
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if _student_list_requested(args):
        return _run_student_list(args)
    return cli_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
