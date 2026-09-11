from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .service import XingyuanService


@dataclass(frozen=True)
class StudentListRecord:
    student_no: str
    name: str
    family: str
    branch: str
    enrollment_year: int
    class_code: str | None
    class_name: str | None
    major_code: str | None
    major_name: str | None
    college_code: str | None
    college_name: str | None
    status: str
    primary_element: str | None
    primary_affinity: str | None
    search_text: str


def _norm(value: object | None) -> str:
    return "" if value is None else str(value).strip().casefold()


def _exact(value: object | None, choices: Iterable[object] | None) -> bool:
    if not choices:
        return True
    actual = _norm(value)
    return any(actual == _norm(choice) for choice in choices)


def _contains(value: object | None, choices: Iterable[object] | None) -> bool:
    if not choices:
        return True
    actual = _norm(value)
    return any(_norm(choice) in actual for choice in choices)


def _contains_any(values: Iterable[object | None], choices: Iterable[object] | None) -> bool:
    if not choices:
        return True
    actuals = tuple(_norm(value) for value in values)
    needles = tuple(_norm(choice) for choice in choices)
    return any(needle in actual for needle in needles for actual in actuals)


def query_students(
    service: XingyuanService,
    *,
    search: str = "",
    student_nos: Iterable[str] | None = None,
    names: Iterable[str] | None = None,
    families: Iterable[str] | None = None,
    branches: Iterable[str] | None = None,
    class_codes: Iterable[str] | None = None,
    major_codes: Iterable[str] | None = None,
    college_codes: Iterable[str] | None = None,
    years: Iterable[int] | None = None,
    statuses: Iterable[str] | None = None,
    elements: Iterable[str] | None = None,
    affinities: Iterable[str] | None = None,
) -> list[StudentListRecord]:
    classes = {int(row["id"]): row for row in service.list_classes()}
    majors = {int(row["id"]): row for row in service.list_majors()}
    colleges = {int(row["id"]): row for row in service.list_departments()}

    result: list[StudentListRecord] = []
    keyword = _norm(search)

    for row in service.list_students(""):
        class_row = None
        major_row = None
        college_row = None

        if row["class_id"] is not None:
            class_row = classes.get(int(row["class_id"]))
        if class_row is not None:
            major_row = majors.get(int(class_row["major_id"]))
        if major_row is not None:
            college_row = colleges.get(int(major_row["department_id"]))

        class_code = None if class_row is None else str(class_row["code"])
        class_name = None if class_row is None else str(class_row["name"])
        major_code = None if major_row is None else str(major_row["code"])
        major_name = None if major_row is None else str(major_row["name"])
        college_code = None if college_row is None else str(college_row["code"])
        college_name = None if college_row is None else str(college_row["name"])

        searchable = (
            row["student_no"], row["name"], row["family"], row["branch"],
            row["gender"], row["birth_date"], row["enrollment_year"],
            class_code, class_name, major_code, major_name,
            college_code, college_name, row["status"],
            row["primary_element"], row["primary_affinity"],
            row["contact"], row["dormitory"], row["notes"],
        )
        search_text = " ".join(_norm(value) for value in searchable if value is not None)

        if keyword and keyword not in search_text:
            continue
        if not _exact(row["student_no"], student_nos):
            continue
        if not _contains(row["name"], names):
            continue
        if not _contains(row["family"], families):
            continue
        if not _contains(row["branch"], branches):
            continue
        if not _contains_any((class_code, class_name), class_codes):
            continue
        if not _contains_any((major_code, major_name), major_codes):
            continue
        if not _contains_any((college_code, college_name), college_codes):
            continue
        if not _exact(row["enrollment_year"], years):
            continue
        if not _contains(row["status"], statuses):
            continue
        if not _contains(row["primary_element"], elements):
            continue
        if not _contains(row["primary_affinity"], affinities):
            continue

        result.append(
            StudentListRecord(
                student_no=str(row["student_no"]),
                name=str(row["name"]),
                family=str(row["family"]),
                branch=str(row["branch"]),
                enrollment_year=int(row["enrollment_year"]),
                class_code=class_code,
                class_name=class_name,
                major_code=major_code,
                major_name=major_name,
                college_code=college_code,
                college_name=college_name,
                status=str(row["status"]),
                primary_element=None if row["primary_element"] is None else str(row["primary_element"]),
                primary_affinity=None if row["primary_affinity"] is None else str(row["primary_affinity"]),
                search_text=search_text,
            )
        )

    return result
