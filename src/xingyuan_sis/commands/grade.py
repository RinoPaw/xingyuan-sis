from __future__ import annotations

import argparse

from ..service import XingyuanService
from .common import confirm, print_table, prompt, prompt_float


def run(service: XingyuanService, args: argparse.Namespace) -> int:
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
        student_no = prompt("学号", args.student_no, required=True)
        course_code = prompt("课程编号", args.course_code, required=True)
        semester = prompt("学期", args.semester, required=True)
        score = args.score
        if args.student_no is None and args.course_code is None and args.semester is None:
            score = prompt_float("成绩（可空）", score)
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
        if confirm(f"删除 {args.student_no} / {args.course_code} / {args.semester}？", args.yes):
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
