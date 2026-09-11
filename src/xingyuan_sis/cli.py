from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys
import unicodedata
from typing import Any, Iterable, Sequence

from .database import initialize_database
from .seed_data import seed_demo
from .service import XingyuanService


def _display_width(value: object) -> int:
    return sum(
        2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        for char in str(value)
    )


def _pad(value: object, width: int) -> str:
    text = str(value)
    return text + " " * max(0, width - _display_width(text))


def print_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    rendered = [["—" if value is None or value == "" else str(value) for value in row] for row in rows]
    if not rendered:
        print("(无数据)")
        return
    widths = [
        max(_display_width(headers[index]), *(_display_width(row[index]) for row in rendered))
        for index in range(len(headers))
    ]
    print("  ".join(_pad(header, widths[index]) for index, header in enumerate(headers)))
    for row in rendered:
        print("  ".join(_pad(value, widths[index]) for index, value in enumerate(row)))


def _print_fields(fields: Sequence[tuple[str, object]]) -> None:
    width = max((_display_width(label) for label, _ in fields), default=0)
    for label, value in fields:
        shown = "—" if value is None or value == "" else value
        print(f"{_pad(label, width)}  {shown}")


def _prompt(label: str, value: str | None = None, *, required: bool = False) -> str | None:
    if value is not None:
        return value
    while True:
        text = input(f"{label}: ").strip()
        if text or not required:
            return text or None
        print(f"{label}不能为空。")


def _prompt_int(label: str, value: int | None = None, *, required: bool = False) -> int | None:
    if value is not None:
        return value
    while True:
        text = input(f"{label}: ").strip()
        if not text and not required:
            return None
        try:
            return int(text)
        except ValueError:
            print("请输入整数。")


def _prompt_float(label: str, value: float | None = None, *, required: bool = False) -> float | None:
    if value is not None:
        return value
    while True:
        text = input(f"{label}: ").strip()
        if not text and not required:
            return None
        try:
            return float(text)
        except ValueError:
            print("请输入数字。")


def _edit_prompt(label: str, current: object, *, clearable: bool = False) -> object:
    shown = "—" if current is None or current == "" else current
    suffix = "；输入 - 清空" if clearable else ""
    raw = input(f"{label} [{shown}]（留空保持{suffix}）: ").strip()
    if not raw:
        return _UNCHANGED
    if clearable and raw == "-":
        return None
    return raw


def _confirm(message: str, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    return input(f"{message} [y/N] ").strip().lower() in {"y", "yes"}


_UNCHANGED = object()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xy",
        description="星原大学学生信息系统",
    )
    parser.add_argument("--db", type=Path, help="使用指定 SQLite 数据库")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--tui", action="store_true", help="强制启动 Textual TUI")
    modes.add_argument("--basic", action="store_true", help="启动基础菜单界面")

    groups = parser.add_subparsers(dest="group")

    # students
    stu = groups.add_parser("stu", aliases=["student"], help="学生")
    stu_cmd = stu.add_subparsers(dest="action", required=True)
    stu_ls = stu_cmd.add_parser("ls", aliases=["list"], help="列出学生")
    stu_ls.add_argument("-s", "--search", default="", help="搜索关键字")
    stu_show = stu_cmd.add_parser("show", help="查看学生")
    stu_show.add_argument("student_no", help="学号")

    stu_add = stu_cmd.add_parser("add", help="新建学生")
    _student_add_options(stu_add)

    stu_edit = stu_cmd.add_parser("edit", help="编辑学生")
    stu_edit.add_argument("student_no", help="当前学号")
    stu_edit.add_argument("--new-no", dest="new_student_no", help="修改学号")
    _student_edit_options(stu_edit)

    stu_rm = stu_cmd.add_parser("rm", aliases=["remove", "delete"], help="删除学生")
    stu_rm.add_argument("student_no", help="学号")
    stu_rm.add_argument("-y", "--yes", action="store_true", help="跳过确认")

    # academics
    acad = groups.add_parser("acad", aliases=["academic"], help="学院、专业和班级")
    entity = acad.add_subparsers(dest="entity", required=True)
    _build_college_parser(entity)
    _build_major_parser(entity)
    _build_class_parser(entity)

    # courses
    course = groups.add_parser("course", aliases=["co"], help="课程")
    course_cmd = course.add_subparsers(dest="action", required=True)
    course_cmd.add_parser("ls", aliases=["list"], help="列出课程")
    course_show = course_cmd.add_parser("show", help="查看课程")
    course_show.add_argument("course_code", help="课程编号")
    course_add = course_cmd.add_parser("add", help="新建课程")
    _course_add_options(course_add)
    course_edit = course_cmd.add_parser("edit", help="编辑课程")
    course_edit.add_argument("course_code", help="当前课程编号")
    course_edit.add_argument("--new-code", help="修改课程编号")
    course_edit.add_argument("--name")
    course_edit.add_argument("--department", dest="department_code")
    course_edit.add_argument("--no-department", action="store_true")
    course_edit.add_argument("--credits", type=float)
    course_edit.add_argument("--hours", type=int)
    course_rm = course_cmd.add_parser("rm", aliases=["remove", "delete"], help="删除课程")
    course_rm.add_argument("course_code")
    course_rm.add_argument("-y", "--yes", action="store_true")

    # grades
    grade = groups.add_parser("grade", aliases=["gr"], help="选课与成绩")
    grade_cmd = grade.add_subparsers(dest="action", required=True)
    grade_ls = grade_cmd.add_parser("ls", aliases=["list"], help="列出成绩")
    grade_ls.add_argument("-s", "--search", default="")
    grade_add = grade_cmd.add_parser("add", help="添加选课/成绩")
    grade_add.add_argument("student_no", nargs="?")
    grade_add.add_argument("course_code", nargs="?")
    grade_add.add_argument("--semester")
    grade_add.add_argument("--score", type=float)
    grade_edit = grade_cmd.add_parser("edit", help="编辑成绩")
    grade_edit.add_argument("student_no")
    grade_edit.add_argument("course_code")
    grade_edit.add_argument("semester")
    grade_edit.add_argument("--semester-to")
    score_group = grade_edit.add_mutually_exclusive_group()
    score_group.add_argument("--score", type=float)
    score_group.add_argument("--clear-score", action="store_true")
    grade_rm = grade_cmd.add_parser("rm", aliases=["remove", "delete"], help="删除选课")
    grade_rm.add_argument("student_no")
    grade_rm.add_argument("course_code")
    grade_rm.add_argument("semester")
    grade_rm.add_argument("-y", "--yes", action="store_true")

    # data
    data = groups.add_parser("data", help="统计与数据交换")
    data_cmd = data.add_subparsers(dest="action", required=True)
    data_cmd.add_parser("stats", help="显示统计摘要")
    data_seed = data_cmd.add_parser("seed", help="写入默认演示数据")
    data_seed.add_argument(
        "--reset",
        action="store_true",
        help="清空现有业务数据后重建演示数据",
    )
    data_export = data_cmd.add_parser("export", help="导出学生 CSV")
    data_export.add_argument("path", type=Path)
    data_import = data_cmd.add_parser("import", help="导入学生 CSV")
    data_import.add_argument("path", type=Path)

    return parser


def _student_add_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no", dest="student_no")
    parser.add_argument("--name")
    parser.add_argument("--family")
    parser.add_argument("--branch")
    parser.add_argument("--year", dest="enrollment_year", type=int)
    parser.add_argument("--class", dest="class_code")
    parser.add_argument("--gender")
    parser.add_argument("--birth", dest="birth_date")
    parser.add_argument("--status")
    parser.add_argument("--element", dest="primary_element")
    parser.add_argument("--affinity", dest="primary_affinity")
    parser.add_argument("--contact")
    parser.add_argument("--dorm", dest="dormitory")
    parser.add_argument("--notes")


def _student_edit_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name")
    parser.add_argument("--family")
    parser.add_argument("--branch")
    parser.add_argument("--year", dest="enrollment_year", type=int)
    class_group = parser.add_mutually_exclusive_group()
    class_group.add_argument("--class", dest="class_code")
    class_group.add_argument("--no-class", action="store_true")
    parser.add_argument("--gender")
    parser.add_argument("--birth", dest="birth_date")
    parser.add_argument("--status")
    parser.add_argument("--element", dest="primary_element")
    parser.add_argument("--affinity", dest="primary_affinity")
    parser.add_argument("--contact")
    parser.add_argument("--dorm", dest="dormitory")
    parser.add_argument("--notes")


def _course_add_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--code")
    parser.add_argument("--name")
    parser.add_argument("--department", dest="department_code")
    parser.add_argument("--credits", type=float)
    parser.add_argument("--hours", type=int)


def _entity_commands(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    return parser.add_subparsers(dest="action", required=True)


def _build_college_parser(parent: argparse._SubParsersAction) -> None:
    parser = parent.add_parser("college", aliases=["dept", "department"], help="学院")
    cmd = _entity_commands(parser)
    cmd.add_parser("ls", aliases=["list"])
    add = cmd.add_parser("add")
    add.add_argument("code", nargs="?")
    add.add_argument("name", nargs="?")
    edit = cmd.add_parser("edit")
    edit.add_argument("code")
    edit.add_argument("--new-code")
    edit.add_argument("--name")
    rm = cmd.add_parser("rm", aliases=["remove", "delete"])
    rm.add_argument("code")
    rm.add_argument("-y", "--yes", action="store_true")


def _build_major_parser(parent: argparse._SubParsersAction) -> None:
    parser = parent.add_parser("major", help="专业")
    cmd = _entity_commands(parser)
    cmd.add_parser("ls", aliases=["list"])
    add = cmd.add_parser("add")
    add.add_argument("code", nargs="?")
    add.add_argument("name", nargs="?")
    add.add_argument("--college", dest="department_code")
    edit = cmd.add_parser("edit")
    edit.add_argument("code")
    edit.add_argument("--new-code")
    edit.add_argument("--name")
    edit.add_argument("--college", dest="department_code")
    rm = cmd.add_parser("rm", aliases=["remove", "delete"])
    rm.add_argument("code")
    rm.add_argument("-y", "--yes", action="store_true")


def _build_class_parser(parent: argparse._SubParsersAction) -> None:
    parser = parent.add_parser("class", help="班级")
    cmd = _entity_commands(parser)
    cmd.add_parser("ls", aliases=["list"])
    add = cmd.add_parser("add")
    add.add_argument("code", nargs="?")
    add.add_argument("name", nargs="?")
    add.add_argument("--major", dest="major_code")
    add.add_argument("--year", dest="enrollment_year", type=int)
    edit = cmd.add_parser("edit")
    edit.add_argument("code")
    edit.add_argument("--new-code")
    edit.add_argument("--name")
    edit.add_argument("--major", dest="major_code")
    edit.add_argument("--year", dest="enrollment_year", type=int)
    rm = cmd.add_parser("rm", aliases=["remove", "delete"])
    rm.add_argument("code")
    rm.add_argument("-y", "--yes", action="store_true")


def _student_class_code(service: XingyuanService, student: Any) -> str | None:
    class_id = student["class_id"]
    if class_id is None:
        return None
    row = next(
        (row for row in service.list_classes() if int(row["id"]) == int(class_id)),
        None,
    )
    return None if row is None else str(row["code"])


def _run_student(service: XingyuanService, args: argparse.Namespace) -> int:
    if args.action in {"ls", "list"}:
        rows = service.list_students(args.search)
        print_table(
            ("学号", "姓名", "班级", "专业", "主元素", "状态"),
            (
                (
                    row["student_no"], row["name"], row["class_name"],
                    row["major_name"], row["primary_element"], row["status"],
                )
                for row in rows
            ),
        )
        return 0

    if args.action == "show":
        row = service._require(service.student_by_no(args.student_no), f"找不到学生：{args.student_no}")
        _print_fields(
            (
                ("学号", row["student_no"]), ("姓名", row["name"]),
                ("族系", f"{row['family']} · {row['branch']}"), ("性别", row["gender"]),
                ("出生日期", row["birth_date"]), ("入学年份", row["enrollment_year"]),
                ("学院", row["department_name"]), ("专业", row["major_name"]),
                ("班级", row["class_name"]), ("状态", row["status"]),
                ("主元素", row["primary_element"]), ("亲和等级", row["primary_affinity"]),
                ("联系方式", row["contact"]), ("宿舍", row["dormitory"]),
                ("备注", row["notes"]),
            )
        )
        grades = [r for r in service.list_enrollments() if r["student_no"] == args.student_no]
        if grades:
            print("\n课程与成绩")
            print_table(
                ("课程", "学期", "成绩"),
                ((r["course_name"], r["semester"], r["score"]) for r in grades),
            )
        return 0

    if args.action == "add":
        interactive = not any(
            (args.student_no, args.name, args.family, args.branch, args.enrollment_year)
        )
        student_no = _prompt("学号", args.student_no, required=True)
        name = _prompt("姓名", args.name, required=True)
        family = _prompt("族系", args.family, required=True)
        branch = _prompt("支系", args.branch, required=True)
        year = _prompt_int("入学年份", args.enrollment_year, required=True)
        optional: dict[str, Any] = {
            "class_code": args.class_code,
            "gender": args.gender,
            "birth_date": args.birth_date,
            "status": args.status or "在读",
            "primary_element": args.primary_element,
            "primary_affinity": args.primary_affinity,
            "contact": args.contact,
            "dormitory": args.dormitory,
            "notes": args.notes,
        }
        if interactive:
            optional["class_code"] = _prompt("班级编号")
            optional["gender"] = _prompt("性别")
            optional["birth_date"] = _prompt("出生日期 YYYY-MM-DD")
            optional["status"] = _prompt("状态", None) or "在读"
            optional["primary_element"] = _prompt("主元素")
            optional["primary_affinity"] = _prompt("亲和等级")
            optional["contact"] = _prompt("联系方式")
            optional["dormitory"] = _prompt("宿舍")
            optional["notes"] = _prompt("备注")
        service.create_student(
            student_no=str(student_no), name=str(name), family=str(family), branch=str(branch),
            enrollment_year=int(year), **optional,
        )
        print(f"✓ 已创建 {name} ({student_no})")
        return 0

    if args.action == "edit":
        row = service._require(service.student_by_no(args.student_no), f"找不到学生：{args.student_no}")
        values: dict[str, Any] = {}
        mapping = {
            "student_no": args.new_student_no,
            "name": args.name,
            "family": args.family,
            "branch": args.branch,
            "enrollment_year": args.enrollment_year,
            "gender": args.gender,
            "birth_date": args.birth_date,
            "status": args.status,
            "primary_element": args.primary_element,
            "primary_affinity": args.primary_affinity,
            "contact": args.contact,
            "dormitory": args.dormitory,
            "notes": args.notes,
        }
        values.update({key: value for key, value in mapping.items() if value is not None})
        if args.class_code is not None:
            values["class_code"] = args.class_code
        elif args.no_class:
            values["class_code"] = None

        if not values:
            current_class = _student_class_code(service, row)
            fields = (
                ("student_no", "学号", row["student_no"], False),
                ("name", "姓名", row["name"], False),
                ("family", "族系", row["family"], False),
                ("branch", "支系", row["branch"], False),
                ("enrollment_year", "入学年份", row["enrollment_year"], False),
                ("class_code", "班级编号", current_class, True),
                ("gender", "性别", row["gender"], True),
                ("birth_date", "出生日期", row["birth_date"], True),
                ("status", "状态", row["status"], False),
                ("primary_element", "主元素", row["primary_element"], True),
                ("primary_affinity", "亲和等级", row["primary_affinity"], True),
                ("contact", "联系方式", row["contact"], True),
                ("dormitory", "宿舍", row["dormitory"], True),
                ("notes", "备注", row["notes"], True),
            )
            for key, label, current, clearable in fields:
                value = _edit_prompt(label, current, clearable=clearable)
                if value is _UNCHANGED:
                    continue
                if key == "enrollment_year" and value is not None:
                    value = int(value)
                values[key] = value

        service.update_student_by_no(args.student_no, **values)
        print("✓ 学生档案已更新")
        return 0

    if args.action in {"rm", "remove", "delete"}:
        row = service._require(service.student_by_no(args.student_no), f"找不到学生：{args.student_no}")
        if not _confirm(f"删除 {row['name']} ({row['student_no']})？", args.yes):
            print("已取消。")
            return 0
        service.delete_student_by_no(args.student_no)
        print("✓ 学生已删除")
        return 0

    return 2


def _run_academic(service: XingyuanService, args: argparse.Namespace) -> int:
    if args.entity in {"college", "dept", "department"}:
        if args.action in {"ls", "list"}:
            print_table(("编号", "学院"), ((r["code"], r["name"]) for r in service.list_departments()))
        elif args.action == "add":
            code = _prompt("学院编号", args.code, required=True)
            name = _prompt("学院名称", args.name, required=True)
            service.create_department(code=str(code), name=str(name))
            print("✓ 学院已创建")
        elif args.action == "edit":
            service.update_department_by_code(args.code, new_code=args.new_code, name=args.name)
            print("✓ 学院已更新")
        else:
            if _confirm(f"删除学院 {args.code}？", args.yes):
                service.delete_department_by_code(args.code)
                print("✓ 学院已删除")
        return 0

    if args.entity == "major":
        if args.action in {"ls", "list"}:
            print_table(
                ("编号", "专业", "学院"),
                ((r["code"], r["name"], r["department_name"]) for r in service.list_majors()),
            )
        elif args.action == "add":
            code = _prompt("专业编号", args.code, required=True)
            name = _prompt("专业名称", args.name, required=True)
            college = _prompt("学院编号", args.department_code, required=True)
            service.create_major(code=str(code), name=str(name), department_code=str(college))
            print("✓ 专业已创建")
        elif args.action == "edit":
            service.update_major_by_code(
                args.code, new_code=args.new_code, name=args.name,
                department_code=args.department_code,
            )
            print("✓ 专业已更新")
        else:
            if _confirm(f"删除专业 {args.code}？", args.yes):
                service.delete_major_by_code(args.code)
                print("✓ 专业已删除")
        return 0

    if args.entity == "class":
        if args.action in {"ls", "list"}:
            print_table(
                ("编号", "班级", "专业", "入学"),
                ((r["code"], r["name"], r["major_name"], r["enrollment_year"]) for r in service.list_classes()),
            )
        elif args.action == "add":
            code = _prompt("班级编号", args.code, required=True)
            name = _prompt("班级名称", args.name, required=True)
            major = _prompt("专业编号", args.major_code, required=True)
            year = _prompt_int("入学年份", args.enrollment_year, required=True)
            service.create_class(code=str(code), name=str(name), major_code=str(major), enrollment_year=int(year))
            print("✓ 班级已创建")
        elif args.action == "edit":
            service.update_class_by_code(
                args.code, new_code=args.new_code, name=args.name,
                major_code=args.major_code, enrollment_year=args.enrollment_year,
            )
            print("✓ 班级已更新")
        else:
            if _confirm(f"删除班级 {args.code}？", args.yes):
                service.delete_class_by_code(args.code)
                print("✓ 班级已删除")
        return 0

    return 2


def _run_course(service: XingyuanService, args: argparse.Namespace) -> int:
    if args.action in {"ls", "list"}:
        print_table(
            ("编号", "课程", "学院", "学分", "课时"),
            (
                (r["course_code"], r["name"], r["department_name"], r["credits"], r["hours"])
                for r in service.list_courses()
            ),
        )
        return 0

    if args.action == "show":
        row = service._require(service.course_by_code(args.course_code), f"找不到课程：{args.course_code}")
        _print_fields(
            (
                ("课程编号", row["course_code"]), ("课程", row["name"]),
                ("学院", row["department_name"]), ("学分", row["credits"]),
                ("课时", row["hours"]),
            )
        )
        grades = [r for r in service.list_enrollments() if r["course_code"] == args.course_code]
        if grades:
            print("\n学生与成绩")
            print_table(
                ("学号", "姓名", "学期", "成绩"),
                ((r["student_no"], r["student_name"], r["semester"], r["score"]) for r in grades),
            )
        return 0

    if args.action == "add":
        interactive = not any((args.code, args.name, args.credits, args.hours))
        code = _prompt("课程编号", args.code, required=True)
        name = _prompt("课程名称", args.name, required=True)
        credits = _prompt_float("学分", args.credits, required=True)
        hours = _prompt_int("课时", args.hours, required=True)
        department = args.department_code
        if interactive:
            department = _prompt("学院编号")
        service.create_course(
            course_code=str(code), name=str(name), credits=float(credits),
            hours=int(hours), department_code=department,
        )
        print("✓ 课程已创建")
        return 0

    if args.action == "edit":
        values = {
            key: value
            for key, value in {
                "course_code": args.new_code,
                "name": args.name,
                "credits": args.credits,
                "hours": args.hours,
            }.items()
            if value is not None
        }
        if args.department_code is not None:
            values["department_code"] = args.department_code
        elif args.no_department:
            values["department_code"] = None
        service.update_course_by_code(args.course_code, **values)
        print("✓ 课程已更新")
        return 0

    if args.action in {"rm", "remove", "delete"}:
        row = service._require(service.course_by_code(args.course_code), f"找不到课程：{args.course_code}")
        if _confirm(f"删除课程 {row['name']} ({row['course_code']})？", args.yes):
            service.delete_course_by_code(args.course_code)
            print("✓ 课程已删除")
        else:
            print("已取消。")
        return 0

    return 2


def _run_grade(service: XingyuanService, args: argparse.Namespace) -> int:
    if args.action in {"ls", "list"}:
        keyword = args.search.strip().lower()
        rows = service.list_enrollments()
        if keyword:
            rows = [
                row for row in rows
                if keyword in " ".join(
                    str(row[key] or "")
                    for key in ("student_no", "student_name", "course_code", "course_name", "semester")
                ).lower()
            ]
        print_table(
            ("学号", "姓名", "课程", "学期", "成绩"),
            ((r["student_no"], r["student_name"], r["course_name"], r["semester"], r["score"]) for r in rows),
        )
        return 0

    if args.action == "add":
        student_no = _prompt("学号", args.student_no, required=True)
        course_code = _prompt("课程编号", args.course_code, required=True)
        semester = _prompt("学期", args.semester, required=True)
        score = args.score
        if args.student_no is None and args.course_code is None and args.semester is None:
            score = _prompt_float("成绩（可空）", score)
        service.add_grade(
            student_no=str(student_no), course_code=str(course_code),
            semester=str(semester), score=score,
        )
        print("✓ 选课记录已创建")
        return 0

    if args.action == "edit":
        row = service._require(
            service.enrollment(args.student_no, args.course_code, args.semester),
            "找不到这条选课记录",
        )
        if args.clear_score:
            score = None
        elif args.score is not None:
            score = args.score
        else:
            score = row["score"]
        service.update_grade(
            student_no=args.student_no,
            course_code=args.course_code,
            semester=args.semester,
            score=score,
            new_semester=args.semester_to,
        )
        print("✓ 成绩已更新")
        return 0

    if args.action in {"rm", "remove", "delete"}:
        if _confirm(
            f"删除 {args.student_no} / {args.course_code} / {args.semester}？",
            args.yes,
        ):
            service.delete_grade(
                student_no=args.student_no,
                course_code=args.course_code,
                semester=args.semester,
            )
            print("✓ 选课记录已删除")
        else:
            print("已取消。")
        return 0

    return 2


def _run_data(service: XingyuanService, args: argparse.Namespace) -> int:
    if args.action == "stats":
        stats = service.stats()
        _print_fields(
            (
                ("学生", stats["students"]), ("学院", stats["departments"]),
                ("专业", stats["majors"]), ("班级", stats["classes"]),
                ("课程", stats["courses"]), ("选课", stats["enrollments"]),
                ("平均成绩", stats["average_score"]), ("最高", stats["max_score"]),
                ("最低", stats["min_score"]),
            )
        )
        return 0
    if args.action == "seed":
        result = seed_demo(service.db_path, reset=args.reset)
        print(
            "✓ 演示数据已写入："
            f"学院 {result.departments}，专业 {result.majors}，班级 {result.classes}，"
            f"学生 {result.students}，课程 {result.courses}，选课 {result.enrollments}"
        )
        return 0
    if args.action == "export":
        count = service.export_students(args.path)
        print(f"✓ 已导出 {count} 条学生记录到 {args.path}")
        return 0
    if args.action == "import":
        result = service.import_students(args.path)
        print(f"✓ 已导入 {result.imported} 条")
        if result.errors:
            print(f"失败 {len(result.errors)} 条：", file=sys.stderr)
            for message in result.errors[:10]:
                print(f"  {message}", file=sys.stderr)
            return 1
        return 0
    return 2


def _tui_terminal_supported() -> bool:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    if sys.platform == "win32":
        try:
            return sys.getwindowsversion().major >= 10
        except AttributeError:
            return True
    return True


def _run_tui(service: XingyuanService, *, force: bool) -> int:
    if not force and not _tui_terminal_supported():
        return _run_basic(service.db_path)
    try:
        from .app import XingyuanSIS
    except ImportError as error:
        if force:
            print(f"无法启动 TUI：{error}", file=sys.stderr)
            return 1
        return _run_basic(service.db_path)
    XingyuanSIS(service).run()
    return 0


def _run_basic(db_path: Path | str | None) -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("当前环境不是交互终端；请使用 xy <command>。", file=sys.stderr)
        return 2
    from .basic_ui import run
    run(db_path)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    initialize_database(args.db)
    service = XingyuanService(args.db)

    try:
        if args.group is None:
            if args.basic:
                return _run_basic(args.db)
            return _run_tui(service, force=args.tui)

        if args.basic or args.tui:
            parser.error("--basic / --tui 不能与 CLI 子命令同时使用")

        if args.group in {"stu", "student"}:
            return _run_student(service, args)
        if args.group in {"acad", "academic"}:
            return _run_academic(service, args)
        if args.group in {"course", "co"}:
            return _run_course(service, args)
        if args.group in {"grade", "gr"}:
            return _run_grade(service, args)
        if args.group == "data":
            return _run_data(service, args)
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except (ValueError, sqlite3.Error, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())