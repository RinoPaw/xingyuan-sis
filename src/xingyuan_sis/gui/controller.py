"""Read models and command dispatch, with authorization before every write."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from ..auth import Identity, change_password, write_session
from ..schema import FIELDS, Field
from ..service import XingyuanService
from ..student_filters import query_students
from ..record_projection import project_records


@dataclass(frozen=True)
class Collection:
    title: str
    singular: str
    columns: tuple[tuple[str, str, int], ...]


COLLECTIONS = {
    "students": Collection("学生名册", "学生", (("student_no", "学号", 125), ("name", "姓名", 150), ("branch", "支系", 100), ("class_name", "班级", 160), ("status", "学籍", 85))),
    "departments": Collection("学院", "学院", (("code", "编号", 100), ("name", "学院", 260))),
    "majors": Collection("专业", "专业", (("code", "编号", 100), ("name", "专业", 180), ("department_name", "学院", 200))),
    "classes": Collection("班级", "班级", (("code", "编号", 120), ("name", "班级", 180), ("major_name", "专业", 140), ("enrollment_year", "入学年份", 100))),
    "courses": Collection("课程目录", "课程", (("course_code", "编号", 120), ("name", "课程", 200), ("credits", "学分", 70), ("hours", "课时", 70))),
    "grades": Collection("选课与成绩", "选课", (("student_name", "学生", 130), ("course_name", "课程", 200), ("semester", "学期", 140), ("score", "成绩", 80))),
    "announcements": Collection("班级公告", "公告", (("title", "标题", 270), ("class_name", "班级", 170), ("created_at", "发布时间", 170))),
    "families": Collection("族系", "族系", (("name", "族系", 240),)),
    "branches": Collection("支系", "支系", (("name", "支系", 180), ("family_name", "族系", 180))),
}
SPECIES_FIELDS = {"families": (Field("name", "族系名称", True),),
    "branches": (Field("name", "支系名称", True), Field("family", "族系", True))}
STUDENT_PAGES = {"overview", "students", "announcements", "profile"}


def fields(key: str) -> tuple[Field, ...]:
    return SPECIES_FIELDS[key] if key in SPECIES_FIELDS else FIELDS[key]


class CampusController:
    def __init__(self, db_path, identity: Identity):
        if identity.must_change_password:
            raise PermissionError("首次登录请先修改密码")
        self.identity, self.service = identity, XingyuanService(db_path)

    def require_admin(self):
        if not self.identity.is_admin:
            raise PermissionError("此操作需要管理员身份")

    def allow_page(self, key):
        return self.identity.is_admin or key in STUDENT_PAGES

    def rows(self, key, search="", **filters):
        if not self.allow_page(key):
            raise PermissionError("当前身份不能访问此章节")
        if key == "students":
            return [asdict(row) for row in query_students(self.service, search=search, **filters)]
        readers = {"families": self.service.list_species_families, "branches": self.service.list_species_branches,
            "grades": self.service.list_enrollments, "announcements": lambda: self.service.list_announcements(
                self.identity.student_no if self.identity.is_student else None)}
        reader = readers.get(key) or getattr(self.service, f"list_{key}")
        needle = search.strip().casefold()
        result = project_records(self.service, key, reader())
        return [row for row in result if not needle or needle in " ".join(str(v) for v in row.values()).casefold()]

    def student_grades(self, no):
        if self.identity.is_student and no != self.identity.student_no:
            return []
        return [dict(r) for r in self.service.enrollments_for_student(no)]

    def choices(self, key, values):
        s = self.service
        related = {"department_code": (s.list_departments, "code", "name"),
            "major_code": (s.list_majors, "code", "name"), "class_code": (s.list_classes, "code", "name"),
            "course_code": (s.list_courses, "course_code", "name"), "student_no": (s.list_students, "student_no", "name")}
        if key in related:
            read, code, name = related[key]
            return [(str(r[code]), f"{r[name]} · {r[code]}") for r in read()]
        if key == "family":
            return [(r["name"], r["name"]) for r in s.list_species_families()]
        if key == "branch":
            return [(r["name"], r["name"]) for r in s.list_species_branches() if r["family_name"] == values.get("family")]
        return None

    def save(self, key, values, original=None):
        self.require_admin()
        s = self.service
        if key == "students":
            if original is None:
                _, password = s.register_student(**values)
                return f"学号：{values['student_no']}\n初始密码：{password}\n请告知学生首次登录后修改密码。"
            s.update_student_by_no(original["student_no"], **values)
        elif key in ("departments", "majors", "classes"):
            kind = {"departments": "department", "majors": "major", "classes": "class"}[key]
            if original is None:
                getattr(s, f"create_{kind}")(**values)
            else:
                values = dict(values)
                values["new_code"] = values.pop("code")
                getattr(s, f"update_{kind}_by_code")(original["code"], **values)
        elif key == "courses":
            if original is None:
                s.create_course(**values)
            else:
                s.update_course_by_code(original["course_code"], **values)
        elif key == "grades":
            if original is None:
                s.add_grade(**values)
            else:
                s.update_grade(student_no=original["student_no"], course_code=original["course_code"],
                    semester=original["semester"], new_semester=values["semester"], score=values["score"])
        elif key == "announcements":
            if original is not None:
                raise ValueError("已发布的公告请删除后重新发布")
            s.create_announcement(**values)
        elif key == "families":
            if original is None:
                s.create_species_family(**values)
            else:
                s.update_species_family_by_name(original["name"], new_name=values["name"])
        elif key == "branches":
            if original is None:
                s.create_species_branch(**values)
            else:
                s.update_species_branch_by_name(original["name"], family=original["family_name"],
                    new_name=values["name"], new_family=values["family"])
        else:
            raise ValueError("未知资料类型")

    def delete(self, key, row):
        self.require_admin()
        s = self.service
        if key == "students":
            s.delete_student_by_no(row["student_no"])
        elif key in ("departments", "majors", "classes"):
            kind = {"departments": "department", "majors": "major", "classes": "class"}[key]
            getattr(s, f"delete_{kind}_by_code")(row["code"])
        elif key == "courses":
            s.delete_course_by_code(row["course_code"])
        elif key == "grades":
            s.delete_grade(**{k: row[k] for k in ("student_no", "course_code", "semester")})
        elif key == "announcements":
            s.delete_announcement(int(row["id"]))
        elif key == "families":
            s.delete_species_family_by_name(row["name"])
        elif key == "branches":
            s.delete_species_branch_by_name(row["name"], family=row["family_name"])
        else:
            raise ValueError("未知资料类型")

    def reset_password(self, no):
        self.require_admin()
        return self.service.reset_student_password(no)

    def import_csv(self, path):
        self.require_admin()
        return self.service.import_students(path)

    def export_csv(self, path):
        self.require_admin()
        return self.service.export_students(path)

    def seed(self):
        self.require_admin()
        return self.service.seed_demo()

    def change_password(self, password):
        self.identity = change_password(self.service.db_path, self.identity, password)
        write_session(self.identity, self.service.db_path)


def record_key(key, row):
    return row["student_no"] if key == "students" else str(row["id"])


def readable_error(error):
    text = str(error)
    if "UNIQUE constraint failed" in text:
        return "编号或名称已存在，请检查后重新保存。"
    if "FOREIGN KEY constraint failed" in text:
        return "仍有记录引用此资料，请先调整关联的专业、班级、学生或课程。"
    return text
