from __future__ import annotations

import argparse

from ..service import XingyuanService
from .common import confirm, print_fields, print_table, prompt, prompt_float, prompt_int


def _course(service: XingyuanService, course_code: str):
    row = service.course_by_code(course_code)
    if row is None:
        raise ValueError(f"找不到课程：{course_code}")
    return row


def run(service: XingyuanService, args: argparse.Namespace) -> int:
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
        row = _course(service, args.course_code)
        print_fields(
            (
                ("课程编号", row["course_code"]), ("课程", row["name"]),
                ("学院", row["department_name"]), ("学分", row["credits"]),
                ("课时", row["hours"]),
            )
        )
        grades = service.enrollments_for_course(args.course_code)
        if grades:
            print("\n学生与成绩")
            print_table(
                ("学号", "姓名", "学期", "成绩"),
                ((r["student_no"], r["student_name"], r["semester"], r["score"]) for r in grades),
            )
        return 0

    if args.action == "add":
        interactive = not any((args.code, args.name, args.credits, args.hours))
        code = prompt("课程编号", args.code, required=True)
        name = prompt("课程名称", args.name, required=True)
        credits = prompt_float("学分", args.credits, required=True)
        hours = prompt_int("课时", args.hours, required=True)
        department = args.department_code
        if interactive:
            department = prompt("学院编号")
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
        row = _course(service, args.course_code)
        if confirm(f"删除课程 {row['name']} ({row['course_code']})？", args.yes):
            service.delete_course_by_code(args.course_code)
            print("✓ 课程已删除")
        else:
            print("已取消。")
        return 0

    return 2
