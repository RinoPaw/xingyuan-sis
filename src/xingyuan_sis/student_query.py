from __future__ import annotations

import argparse
from dataclasses import dataclass
import shlex


@dataclass(frozen=True)
class StudentQuery:
    search: str = ""
    student_nos: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    families: tuple[str, ...] = ()
    branches: tuple[str, ...] = ()
    class_codes: tuple[str, ...] = ()
    major_codes: tuple[str, ...] = ()
    college_codes: tuple[str, ...] = ()
    years: tuple[int, ...] = ()
    statuses: tuple[str, ...] = ()
    elements: tuple[str, ...] = ()
    affinities: tuple[str, ...] = ()

    def as_kwargs(self) -> dict[str, object]:
        return {
            "search": self.search,
            "student_nos": self.student_nos,
            "names": self.names,
            "families": self.families,
            "branches": self.branches,
            "class_codes": self.class_codes,
            "major_codes": self.major_codes,
            "college_codes": self.college_codes,
            "years": self.years,
            "statuses": self.statuses,
            "elements": self.elements,
            "affinities": self.affinities,
        }


def add_student_query_arguments(parser: argparse.ArgumentParser) -> None:
    """Register the student query language shared by CLI and TUI."""
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


def parse_student_query(text: str) -> StudentQuery:
    """Parse a TUI query using the same option names and value rules as ``xy stu ls``.

    Bare text remains convenient shorthand for ``--search``. It can be mixed
    with structured options, for example ``赤狐 --year 2025 --status 在读``.
    """
    try:
        tokens = shlex.split(text)
    except ValueError as exc:
        raise ValueError(f"查询语法错误：{exc}") from exc

    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False, exit_on_error=False)
    add_student_query_arguments(parser)
    try:
        namespace, remainder = parser.parse_known_args(tokens)
    except argparse.ArgumentError as exc:
        raise ValueError(f"查询语法错误：{exc}") from exc

    unknown_options = [token for token in remainder if token.startswith("-")]
    if unknown_options:
        raise ValueError(f"未知查询条件：{unknown_options[0]}")

    bare = " ".join(remainder).strip()
    search = namespace.search.strip()
    if bare:
        search = " ".join(part for part in (search, bare) if part)

    return StudentQuery(
        search=search,
        student_nos=tuple(namespace.student_nos or ()),
        names=tuple(namespace.names or ()),
        families=tuple(namespace.families or ()),
        branches=tuple(namespace.branches or ()),
        class_codes=tuple(namespace.class_codes or ()),
        major_codes=tuple(namespace.major_codes or ()),
        college_codes=tuple(namespace.college_codes or ()),
        years=tuple(namespace.years or ()),
        statuses=tuple(namespace.statuses or ()),
        elements=tuple(namespace.elements or ()),
        affinities=tuple(namespace.affinities or ()),
    )
