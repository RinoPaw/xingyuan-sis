from __future__ import annotations

import argparse

from ..auth import read_session
from ..service import XingyuanService
from .common import confirm, print_fields, print_table, prompt


def run(service: XingyuanService, args: argparse.Namespace) -> int:
    identity = read_session(service.db_path)
    student_no = identity.student_no or "" if identity and identity.is_student else None
    rows = service.list_announcements(student_no)
    if args.action in {"ls", "list"}:
        terms = args.search.casefold().split()
        rows = [row for row in rows if all(
            term in f"{row['title']} {row['body']} {row['class_name']}".casefold() for term in terms
        )]
        print_table(("编号", "标题", "班级", "发布时间"),
                    ((row["id"], row["title"], row["class_name"], row["created_at"]) for row in rows))
        return 0
    if args.action == "add":
        identifier = service.create_announcement(
            title=prompt("标题", args.title, required=True),
            class_code=prompt("班级编号", args.class_code, required=True),
            body=prompt("正文", args.body, required=True),
        )
        print(f"✓ 公告已发布：{identifier}")
        return 0
    row = next((row for row in rows if row["id"] == args.id), None)
    if row is None:
        raise ValueError(f"找不到公告：{args.id}")
    if args.action == "show":
        print_fields((("标题", row["title"]), ("班级", row["class_name"]), ("发布时间", row["created_at"])))
        print("\n" + row["body"])
        return 0
    if args.action in {"rm", "remove", "delete"}:
        if confirm(f"删除公告《{row['title']}》？", args.yes):
            service.delete_announcement(row["id"])
            print("✓ 公告已删除")
        else:
            print("已取消。")
        return 0
    return 2
