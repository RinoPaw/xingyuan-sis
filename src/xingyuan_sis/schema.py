"""Canonical field contracts shared by services, CSV imports and terminal forms."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import re
from typing import Any, Mapping


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    required: bool = False
    kind: str = "text"
    default: Any = None
    minimum: float = 0
    maximum: float | None = None
    editable: bool = True

    def parse(self, value: Any) -> Any:
        text = "" if value is None else str(value).strip()
        if not text:
            if self.required:
                raise ValueError(f"请填写{self.label}")
            return None
        if self.kind == "digits" and re.fullmatch(r"[0-9]+", text) is None:
            raise ValueError(f"{self.label}只能包含 0–9 的数字")
        if self.kind in {"int", "float"}:
            try:
                number = int(text) if self.kind == "int" else float(text)
            except ValueError:
                raise ValueError(f"{self.label}需要填写{'整数' if self.kind == 'int' else '数字'}") from None
            if self.kind == "int" and number > 2**63 - 1:
                raise ValueError(f"{self.label}数值过大")
            if (self.kind == "float" and not math.isfinite(number)) or number < self.minimum or (
                self.maximum is not None and number > self.maximum
            ):
                bound = f"{self.minimum:g}～{self.maximum:g}" if self.maximum is not None else f"不小于 {self.minimum:g}"
                raise ValueError(f"{self.label}应为{bound}")
            return number
        if self.kind == "date":
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
                    raise ValueError
                date.fromisoformat(text)
            except ValueError:
                raise ValueError(f"{self.label}请使用 YYYY-MM-DD") from None
        return text


YEAR = Field("enrollment_year", "入学年份", True, "int", minimum=1900, maximum=9999)
STUDENT_NUMBER = Field("student_no", "学号", True, "digits", editable=False)

FIELDS: dict[str, tuple[Field, ...]] = {
    "students": (
        STUDENT_NUMBER, Field("name", "姓名", True, editable=False),
        Field("family", "族系", True), Field("branch", "支系", True), YEAR,
        Field("class_code", "班级编号"), Field("status", "学籍状态", True, default="在读"),
        Field("gender", "性别"), Field("birth_date", "出生日期", kind="date"),
        Field("primary_element", "主元素"), Field("primary_affinity", "亲和等级"),
        Field("contact", "联系方式"), Field("dormitory", "宿舍"), Field("notes", "备注"),
    ),
    "courses": (
        Field("course_code", "课程编号", True), Field("name", "课程名称", True),
        Field("credits", "学分", True, "float", 0), Field("hours", "课时", True, "int", 0),
        Field("department_code", "学院编号"),
    ),
    "grades": (
        STUDENT_NUMBER, Field("course_code", "课程编号", True, editable=False),
        Field("semester", "学期", True), Field("score", "成绩", kind="float", maximum=100),
    ),
    "departments": (Field("code", "学院编号", True), Field("name", "学院名称", True)),
    "majors": (Field("code", "专业编号", True), Field("name", "专业名称", True),
        Field("department_code", "学院编号", True)),
    "classes": (Field("code", "班级编号", True), Field("name", "班级名称", True),
        Field("major_code", "专业编号", True), YEAR),
    "announcements": (
        Field("title", "标题", True), Field("class_code", "班级编号", True),
        Field("body", "正文", True),
    ),
}


def validate_values(key: str, values: Mapping[str, Any], *, partial: bool = False) -> dict[str, Any]:
    """Normalize supplied values; partial updates never fill omitted fields."""
    fields = {field.key: field for field in FIELDS[key]}
    unknown = values.keys() - fields.keys()
    if unknown:
        raise ValueError(f"不支持的字段：{', '.join(sorted(unknown))}")
    return {
        name: field.parse(values.get(name, field.default))
        for name, field in fields.items()
        if not partial or name in values
    }
