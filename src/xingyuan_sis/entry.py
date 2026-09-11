from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import csv
from pathlib import Path
import sqlite3
import sys
from typing import Sequence

from .cli import main as cli_main, print_table
from .csv_io import STUDENT_FIELDS
from .database import initialize_database
from .service import XingyuanService
from .student_filters import StudentListRecord, query_students


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


def _menu_tail(argv: Sequence[str]) -> list[str]:
    tokens = list(argv)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--db":
            if index + 1 >= len(tokens):
                return tokens[index:]
            index += 2
            continue
        if token.startswith("--db="):
            index += 1
            continue
        break
    return tokens[index:]


def _menu_db(argv: Sequence[str]) -> Path | None:
    tokens = list(argv)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--db":
            if index + 1 >= len(tokens):
                return None
            return Path(tokens[index + 1])
        if token.startswith("--db="):
            return Path(token.split("=", 1)[1])
        index += 1
    return None


def _student_list_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xy stu ls",
        description=(
            "列出学生；文本字段使用包含匹配，不同字段之间按 AND，"
            "同一字段重复时按 OR。学号和年份保持精确匹配。"
        ),
    )
    parser.add_argument("--db", type=Path, help="使用指定 SQLite 数据库")
    parser.add_argument("group", choices=("stu", "student"), help=argparse.SUPPRESS)
    parser.add_argument("action", choices=("ls", "list"), help=argparse.SUPPRESS)
    parser.add_argument("-s", "--search", default="", help="全字段模糊搜索")
    parser.add_argument("--no", dest="student_nos", action="append", metavar="学号", help="精确匹配学号，可重复")
    parser.add_argument("--name", dest="names", action="append", metavar="姓名", help="姓名包含，可重复")
    parser.add_argument("--family", dest="families", action="append", metavar="族系", help="族系包含，可重复")
    parser.add_argument("--branch", dest="branches", action="append", metavar="支系", help="支系包含，可重复")
    parser.add_argument("--class", dest="class_codes", action="append", metavar="班级", help="班级编号或名称包含，可重复")
    parser.add_argument("--major", dest="major_codes", action="append", metavar="专业", help="专业编号或名称包含，可重复")
    parser.add_argument(
        "--college", "--department",
        dest="college_codes",
        action="append",
        metavar="学院",
        help="学院编号或名称包含，可重复",
    )
    parser.add_argument("--year", dest="years", action="append", type=int, metavar="年份", help="精确匹配入学年份，可重复")
    parser.add_argument("--status", dest="statuses", action="append", metavar="状态", help="状态包含，可重复")
    parser.add_argument("--element", dest="elements", action="append", metavar="元素", help="主元素包含，可重复")
    parser.add_argument("--affinity", dest="affinities", action="append", metavar="等级", help="亲和等级包含，可重复")
    parser.add_argument(
        "--format",
        choices=("table", "csv"),
        default="table",
        help="输出格式，默认 table",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="输出文件；省略时写到 stdout",
    )
    return parser


def _csv_row(row: StudentListRecord) -> dict[str, object | None]:
    return {
        "student_no": row.student_no,
        "name": row.name,
        "family": row.family,
        "branch": row.branch,
        "gender": row.gender,
        "birth_date": row.birth_date,
        "enrollment_year": row.enrollment_year,
        "class_code": row.class_code,
        "status": row.status,
        "primary_element": row.primary_element,
        "primary_affinity": row.primary_affinity,
        "contact": row.contact,
        "dormitory": row.dormitory,
        "notes": row.notes,
    }


def _write_student_csv(rows: Sequence[StudentListRecord], output: Path | None) -> None:
    if output is None:
        writer = csv.DictWriter(sys.stdout, fieldnames=STUDENT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(_csv_row(row))
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=STUDENT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(_csv_row(row))


def _print_student_table(rows: Sequence[StudentListRecord]) -> None:
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


def _write_student_table(rows: Sequence[StudentListRecord], output: Path | None) -> None:
    if output is None:
        _print_student_table(rows)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        with redirect_stdout(file):
            _print_student_table(rows)


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

    if args.format == "csv":
        _write_student_csv(rows, args.output)
    else:
        _write_student_table(rows, args.output)
    return 0


def _run_menu(argv: Sequence[str], *, basic: bool) -> int:
    db_path = _menu_db(argv)
    initialize_database(db_path)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("当前环境不是交互终端；请使用 xy <command>。", file=sys.stderr)
        return 2

    if basic:
        from .basic_ui import run
    else:
        from .menu import run

    run(db_path)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if _student_list_requested(args):
            return _run_student_list(args)

        tail = _menu_tail(args)
        if not tail:
            return _run_menu(args, basic=False)
        if tail == ["--basic"]:
            return _run_menu(args, basic=True)

        return cli_main(args)
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except EOFError:
        print("\n输入已结束，操作已取消。", file=sys.stderr)
        return 1
    except (ValueError, sqlite3.Error, OSError) as error:
        print(f"操作失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
