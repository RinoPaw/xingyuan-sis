from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import csv
from pathlib import Path
import sys
from typing import Any, Sequence

from ..auth import reset_student_password
from ..csv_io import STUDENT_FIELDS
from ..schema import age_from_birth_date
from ..service import XingyuanService
from ..student_filters import StudentListRecord, query_students
from .common import UNCHANGED, confirm, edit_prompt, print_fields, print_table, prompt, prompt_int


def _student(service: XingyuanService, student_no: str):
    row = service.student_by_no(student_no)
    if row is None:
        raise ValueError(f"找不到学生：{student_no}")
    return row


def _display_age(row) -> int | None:
    derived = age_from_birth_date(row["birth_date"])
    return derived if derived is not None else row["age"]


def _csv_row(row: StudentListRecord) -> dict[str, object | None]:
    return {
        "student_no": row.student_no,
        "name": row.name,
        "family": row.family,
        "branch": row.branch,
        "gender": row.gender,
        "birth_date": row.birth_date,
        "age": row.age,
        "enrollment_year": row.enrollment_year,
        "class_code": row.class_code,
        "status": row.status,
        "primary_element": row.primary_element,
        "primary_affinity": row.primary_affinity,
        "contact": row.contact,
        "dormitory": row.dormitory,
        "notes": row.notes,
    }


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


def _write_students(rows: Sequence[StudentListRecord], format_: str, output: Path | None) -> None:
    if format_ == "csv":
        if output is None:
            writer = csv.DictWriter(sys.stdout, fieldnames=STUDENT_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(_csv_row(row) for row in rows)
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=STUDENT_FIELDS)
            writer.writeheader()
            writer.writerows(_csv_row(row) for row in rows)
        return

    if output is None:
        _print_student_table(rows)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file, redirect_stdout(file):
        _print_student_table(rows)


def run(service: XingyuanService, args: argparse.Namespace) -> int:
    if args.action in {"ls", "list"}:
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
        _write_students(rows, args.format, args.output)
        return 0

    if args.action == "show":
        row = _student(service, args.student_no)
        print_fields(
            (
                ("学号", row["student_no"]), ("姓名", row["name"]),
                ("族系", f"{row['family']} · {row['branch']}"), ("性别", row["gender"]),
                ("年龄", _display_age(row)), ("出生日期", row["birth_date"]),
                ("入学年份", row["enrollment_year"]),
                ("学院", row["department_name"]), ("专业", row["major_name"]),
                ("班级", row["class_name"]), ("状态", row["status"]),
                ("主元素", row["primary_element"]), ("亲和等级", row["primary_affinity"]),
                ("联系方式", row["contact"]), ("宿舍", row["dormitory"]),
                ("备注", row["notes"]),
            )
        )
        grades = service.enrollments_for_student(args.student_no)
        if grades:
            print("\n课程与成绩")
            print_table(
                ("课程", "学期", "成绩"),
                ((r["course_name"], r["semester"], r["score"]) for r in grades),
            )
        return 0

    if args.action == "add":
        interactive = not any((args.student_no, args.name, args.family, args.branch, args.enrollment_year))
        student_no = prompt("学号", args.student_no, required=True)
        name = prompt("姓名", args.name, required=True)
        family = prompt("族系", args.family, required=True)
        branch = prompt("支系", args.branch, required=True)
        year = prompt_int("入学年份", args.enrollment_year, required=True)
        optional: dict[str, Any] = {
            "class_code": args.class_code,
            "gender": args.gender,
            "age": args.age,
            "birth_date": args.birth_date,
            "status": args.status or "在读",
            "primary_element": args.primary_element,
            "primary_affinity": args.primary_affinity,
            "contact": args.contact,
            "dormitory": args.dormitory,
            "notes": args.notes,
        }
        if interactive:
            optional["class_code"] = prompt("班级编号")
            optional["gender"] = prompt("性别")
            optional["age"] = prompt_int("年龄")
            optional["birth_date"] = prompt("出生日期 YYYY-MM-DD / YYYY / --MM-DD")
            optional["status"] = prompt("状态", None) or "在读"
            optional["primary_element"] = prompt("主元素")
            optional["primary_affinity"] = prompt("亲和等级")
            optional["contact"] = prompt("联系方式")
            optional["dormitory"] = prompt("宿舍")
            optional["notes"] = prompt("备注")
        _, initial_password = service.register_student(
            student_no=str(student_no), name=str(name), family=str(family), branch=str(branch),
            enrollment_year=int(year), **optional,
        )
        print(f"✓ 已创建 {name} ({student_no})")
        print(f"初始密码：{initial_password}")
        print("首次登录必须修改密码")
        return 0

    if args.action == "reset-password":
        row = _student(service, args.student_no)
        initial_password = reset_student_password(service.db_path, args.student_no)
        print(f"✓ 已重置 {row['name']} ({row['student_no']}) 的登录密码")
        print(f"初始密码：{initial_password}")
        print("首次登录必须修改密码")
        return 0

    if args.action == "edit":
        row = _student(service, args.student_no)
        values: dict[str, Any] = {}
        mapping = {
            "family": args.family,
            "branch": args.branch,
            "enrollment_year": args.enrollment_year,
            "gender": args.gender,
            "age": args.age,
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
            fields = (
                ("family", "族系", row["family"], False),
                ("branch", "支系", row["branch"], False),
                ("enrollment_year", "入学年份", row["enrollment_year"], False),
                ("class_code", "班级编号", row["class_code"], True),
                ("gender", "性别", row["gender"], True),
                ("age", "年龄", row["age"], True),
                ("birth_date", "出生日期", row["birth_date"], True),
                ("status", "状态", row["status"], False),
                ("primary_element", "主元素", row["primary_element"], True),
                ("primary_affinity", "亲和等级", row["primary_affinity"], True),
                ("contact", "联系方式", row["contact"], True),
                ("dormitory", "宿舍", row["dormitory"], True),
                ("notes", "备注", row["notes"], True),
            )
            for key, label, current, clearable in fields:
                value = edit_prompt(label, current, clearable=clearable)
                if value is UNCHANGED:
                    continue
                if key in {"enrollment_year", "age"} and value is not None:
                    value = int(value)
                values[key] = value

        service.update_student_by_no(args.student_no, **values)
        print("✓ 学生档案已更新")
        return 0

    if args.action in {"rm", "remove", "delete"}:
        row = _student(service, args.student_no)
        if not confirm(f"删除 {row['name']} ({row['student_no']})？", args.yes):
            print("已取消。")
            return 0
        service.delete_student_by_no(args.student_no)
        print("✓ 学生已删除")
        return 0

    return 2
