from __future__ import annotations

import argparse
import sys

from ..auth import DEMO_STUDENT_PASSWORD
from ..service import XingyuanService
from .common import print_fields


def run(service: XingyuanService, args: argparse.Namespace) -> int:
    if args.action == "stats":
        stats = service.stats()
        print_fields(
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
        result = service.seed_demo(reset=args.reset)
        print(
            "✓ 演示数据已写入："
            f"学院 {result.departments}，专业 {result.majors}，班级 {result.classes}，"
            f"学生 {result.students}，课程 {result.courses}，选课 {result.enrollments}"
        )
        print(f"演示学生初始密码：{DEMO_STUDENT_PASSWORD}")
        print("首次登录必须修改密码")
        return 0
    if args.action == "export":
        count = service.export_students(args.path)
        print(f"✓ 已导出 {count} 条学生记录到 {args.path}")
        return 0
    if args.action == "import":
        result = service.import_students(args.path)
        print(f"✓ 已导入 {result.imported} 条")
        if result.credentials:
            print("首次登录必须修改密码；请交给对应学生：")
            for student_no, password in result.credentials:
                print(f"  {student_no}  初始密码：{password}")
        if result.errors:
            print(f"失败 {len(result.errors)} 条：", file=sys.stderr)
            for message in result.errors[:10]:
                print(f"  {message}", file=sys.stderr)
            return 1
        return 0
    return 2
