from __future__ import annotations

import argparse

from ..service import XingyuanService
from .common import confirm, print_table, prompt, prompt_int


def run(service: XingyuanService, args: argparse.Namespace) -> int:
    if args.entity == "college":
        if args.action in {"ls", "list"}:
            print_table(("编号", "学院"), ((r["code"], r["name"]) for r in service.list_departments()))
        elif args.action == "add":
            code = prompt("学院编号", args.code, required=True)
            name = prompt("学院名称", args.name, required=True)
            service.create_department(code=str(code), name=str(name))
            print("✓ 学院已创建")
        elif args.action == "edit":
            service.update_department_by_code(args.code, new_code=args.new_code, name=args.name)
            print("✓ 学院已更新")
        else:
            if confirm(f"删除学院 {args.code}？", args.yes):
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
            code = prompt("专业编号", args.code, required=True)
            name = prompt("专业名称", args.name, required=True)
            college = prompt("学院编号", args.department_code, required=True)
            service.create_major(code=str(code), name=str(name), department_code=str(college))
            print("✓ 专业已创建")
        elif args.action == "edit":
            service.update_major_by_code(
                args.code, new_code=args.new_code, name=args.name,
                department_code=args.department_code,
            )
            print("✓ 专业已更新")
        else:
            if confirm(f"删除专业 {args.code}？", args.yes):
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
            code = prompt("班级编号", args.code, required=True)
            name = prompt("班级名称", args.name, required=True)
            major = prompt("专业编号", args.major_code, required=True)
            year = prompt_int("入学年份", args.enrollment_year, required=True)
            service.create_class(code=str(code), name=str(name), major_code=str(major), enrollment_year=int(year))
            print("✓ 班级已创建")
        elif args.action == "edit":
            service.update_class_by_code(
                args.code, new_code=args.new_code, name=args.name,
                major_code=args.major_code, enrollment_year=args.enrollment_year,
            )
            print("✓ 班级已更新")
        else:
            if confirm(f"删除班级 {args.code}？", args.yes):
                service.delete_class_by_code(args.code)
                print("✓ 班级已删除")
        return 0

    return 2
