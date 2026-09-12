from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xy",
        description="星原大学学生信息系统",
    )
    parser.add_argument("--db", type=Path, help="使用指定 SQLite 数据库")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--tui", action="store_true", help="强制启动即时键盘界面")
    modes.add_argument("--basic", action="store_true", help="启动基础菜单界面")

    groups = parser.add_subparsers(dest="group")

    auth = groups.add_parser("auth", help="认证")
    auth_cmd = auth.add_subparsers(dest="action")
    auth_login = auth_cmd.add_parser("login", help="登录")
    auth_login.add_argument("username", nargs="?", help="账号；省略时交互输入")
    auth_cmd.add_parser("logout", help="退出登录")
    auth_cmd.add_parser("status", help="查看当前身份")
    auth_cmd.add_parser("passwd", help="修改当前账户密码")

    stu = groups.add_parser("stu", aliases=["student"], help="学生")
    stu_cmd = stu.add_subparsers(dest="action", required=True)
    stu_ls = stu_cmd.add_parser(
        "ls",
        aliases=["list"],
        help="列出学生",
        description=(
            "列出学生；文本字段使用包含匹配，不同字段之间按 AND，"
            "同一字段重复时按 OR。学号和年份保持精确匹配。"
        ),
    )
    _student_list_options(stu_ls)
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
    stu_reset = stu_cmd.add_parser("reset-password", help="重置学生登录密码")
    stu_reset.add_argument("student_no", help="学号")

    _build_college_parser(groups)
    _build_major_parser(groups)
    _build_class_parser(groups)

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

    data = groups.add_parser("data", help="统计与数据交换")
    data_cmd = data.add_subparsers(dest="action", required=True)
    data_cmd.add_parser("stats", help="显示统计摘要")
    data_seed = data_cmd.add_parser("seed", help="写入默认演示数据")
    data_seed.add_argument("--reset", action="store_true", help="清空现有业务数据后重建演示数据")
    data_export = data_cmd.add_parser("export", help="导出学生 CSV")
    data_export.add_argument("path", type=Path)
    data_import = data_cmd.add_parser("import", help="导入学生 CSV")
    data_import.add_argument("path", type=Path)

    return parser


def _student_list_options(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument(
        "--format",
        choices=("table", "csv"),
        default="table",
        help="输出格式，默认 table",
    )
    parser.add_argument("-o", "--output", type=Path, help="输出文件；省略时写到 stdout")


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
    parser = parent.add_parser("college", help="学院")
    parser.set_defaults(entity="college")
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
    parser.set_defaults(entity="major")
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
    parser.set_defaults(entity="class")
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
