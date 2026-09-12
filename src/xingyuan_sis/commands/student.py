from __future__ import annotations

import argparse
from typing import Any

from ..service import XingyuanService
from .common import UNCHANGED, confirm, edit_prompt, print_fields, print_table, prompt, prompt_int


def _student_class_code(service: XingyuanService, student: Any) -> str | None:
    class_id = student["class_id"]
    if class_id is None:
        return None
    row = next(
        (row for row in service.list_classes() if int(row["id"]) == int(class_id)),
        None,
    )
    return None if row is None else str(row["code"])


def run(service: XingyuanService, args: argparse.Namespace) -> int:
    if args.action in {"ls", "list"}:
        rows = service.list_students(args.search)
        print_table(
            ("学号", "姓名", "支系", "班级", "专业", "主元素", "状态"),
            (
                (
                    row["student_no"], row["name"], row["branch"], row["class_name"],
                    row["major_name"], row["primary_element"], row["status"],
                )
                for row in rows
            ),
        )
        return 0

    if args.action == "show":
        row = service._require(service.student_by_no(args.student_no), f"找不到学生：{args.student_no}")
        print_fields(
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
        interactive = not any((args.student_no, args.name, args.family, args.branch, args.enrollment_year))
        student_no = prompt("学号", args.student_no, required=True)
        name = prompt("姓名", args.name, required=True)
        family = prompt("族系", args.family, required=True)
        branch = prompt("支系", args.branch, required=True)
        year = prompt_int("入学年份", args.enrollment_year, required=True)
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
            optional["class_code"] = prompt("班级编号")
            optional["gender"] = prompt("性别")
            optional["birth_date"] = prompt("出生日期 YYYY-MM-DD")
            optional["status"] = prompt("状态", None) or "在读"
            optional["primary_element"] = prompt("主元素")
            optional["primary_affinity"] = prompt("亲和等级")
            optional["contact"] = prompt("联系方式")
            optional["dormitory"] = prompt("宿舍")
            optional["notes"] = prompt("备注")
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
                value = edit_prompt(label, current, clearable=clearable)
                if value is UNCHANGED:
                    continue
                if key == "enrollment_year" and value is not None:
                    value = int(value)
                values[key] = value

        service.update_student_by_no(args.student_no, **values)
        print("✓ 学生档案已更新")
        return 0

    if args.action in {"rm", "remove", "delete"}:
        row = service._require(service.student_by_no(args.student_no), f"找不到学生：{args.student_no}")
        if not confirm(f"删除 {row['name']} ({row['student_no']})？", args.yes):
            print("已取消。")
            return 0
        service.delete_student_by_no(args.student_no)
        print("✓ 学生已删除")
        return 0

    return 2
