from __future__ import annotations

import argparse

from ..service import XingyuanService
from . import academic, course, data, grade, notice, student


def run_group(service: XingyuanService, args: argparse.Namespace) -> int:
    if args.group in {"stu", "student"}:
        return student.run(service, args)
    if args.group in {"college", "major", "class"}:
        return academic.run(service, args)
    if args.group in {"course", "co"}:
        return course.run(service, args)
    if args.group in {"grade", "gr"}:
        return grade.run(service, args)
    if args.group == "data":
        return data.run(service, args)
    if args.group == "notice":
        return notice.run(service, args)
    return 2
