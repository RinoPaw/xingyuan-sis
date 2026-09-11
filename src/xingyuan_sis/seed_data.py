from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .database import connect


DEPARTMENTS = (
    ("SCI", "自然科学学院"),
    ("ENG", "工程学院"),
    ("LIF", "生命科学学院"),
    ("MED", "医学院"),
)

MAJORS = (
    ("ELS", "元素学", "SCI"),
    ("GEO", "地质与矿业", "SCI"),
    ("MET", "气象学", "SCI"),
    ("ELE", "元素工程", "ENG"),
    ("EEE", "电气工程", "ENG"),
    ("MEC", "机械工程", "ENG"),
    ("INS", "仪器与计量", "ENG"),
    ("CIV", "建筑与土木", "ENG"),
    ("BIO", "生物学", "LIF"),
    ("MED", "医学", "MED"),
)

CLASSES = (
    ("ELS2601", "元素学2601班", "ELS", 2026),
    ("ELS2501", "元素学2501班", "ELS", 2025),
    ("ELE2501", "元素工程2501班", "ELE", 2025),
    ("MEC2401", "机械工程2401班", "MEC", 2024),
    ("INS2501", "仪器与计量2501班", "INS", 2025),
    ("CIV2401", "建筑与土木2401班", "CIV", 2024),
    ("BIO2601", "生物学2601班", "BIO", 2026),
    ("EEE2301", "电气工程2301班", "EEE", 2023),
    ("MED2401", "医学2401班", "MED", 2024),
    ("GEO2501", "地质与矿业2501班", "GEO", 2025),
    ("MET2601", "气象学2601班", "MET", 2026),
)

STUDENTS = (
    ("20260001", "林岚", "猫科", "石虎", "女", "2008-03-17", 2026, "ELS2601", "在读", "风", "A", "北区 3-214"),
    ("20260002", "闻溪", "兔科", "雪兔", "女", "2008-11-02", 2026, "BIO2601", "在读", "水", "B", "北区 2-308"),
    ("20260003", "乔澈", "犬科", "萨摩耶", "男", "2007-12-21", 2026, "MET2601", "在读", "风", "B", "北区 5-116"),
    ("20250001", "许麦", "犬科", "金毛", "男", "2007-05-09", 2025, "ELE2501", "在读", "火", "A", "东区 1-407"),
    ("20250002", "沈芦", "犬科", "边境牧羊犬", "女", "2006-10-14", 2025, "INS2501", "在读", "雷", "A", "东区 2-221"),
    ("20250003", "黎钧", "猫科", "黑豹", "男", "2007-01-28", 2025, "GEO2501", "在读", "岩", "A", "东区 4-318"),
    ("20250004", "唐棠", "狐科", "赤狐", "女", "2006-08-06", 2025, "ELS2501", "在读", "光", "B", "东区 3-205"),
    ("20240001", "白榆", "猫科", "东北虎", "男", "2005-04-12", 2024, "MEC2401", "在读", "火", "B", "南区 2-410"),
    ("20240002", "鹿遥", "鹿科", "梅花鹿", "女", "2005-09-30", 2024, "CIV2401", "在读", "岩", "A", "南区 1-302"),
    ("20240003", "苏栎", "狐科", "赤狐", "女", "2005-01-19", 2024, "MED2401", "在读", "水", "B", "南区 5-209"),
    ("20230001", "唐砾", "犬科", "德国牧羊犬", "男", "2004-06-25", 2023, "EEE2301", "在读", "雷", "A", "西区 2-116"),
    ("20230002", "鹤川", "狼科", "灰狼", "男", "2004-02-07", 2023, "EEE2301", "休学", "风", "C", "西区 2-118"),
)

COURSES = (
    ("ELS101", "元素现象导论", "SCI", 3.0, 48),
    ("ELS120", "元素测量基础", "SCI", 2.5, 40),
    ("GEO110", "地表与岩体", "SCI", 3.0, 48),
    ("MET110", "大气观测", "SCI", 3.0, 48),
    ("ENG101", "工程制图", "ENG", 2.0, 32),
    ("ELE120", "元素装置基础", "ENG", 3.0, 48),
    ("EEE130", "电路基础", "ENG", 3.5, 56),
    ("MEC130", "机械原理", "ENG", 3.5, 56),
    ("INS140", "仪器与计量基础", "ENG", 3.0, 48),
    ("BIO110", "生物结构与功能", "LIF", 3.0, 48),
    ("MED110", "基础解剖", "MED", 4.0, 64),
)

ENROLLMENTS = (
    ("20260001", "ELS101", "2026-2027-1", 92.0),
    ("20260001", "ELS120", "2026-2027-1", 88.0),
    ("20260002", "BIO110", "2026-2027-1", 91.0),
    ("20260003", "MET110", "2026-2027-1", 86.0),
    ("20250001", "ELE120", "2026-2027-1", 94.0),
    ("20250001", "ENG101", "2026-2027-1", 82.0),
    ("20250002", "INS140", "2026-2027-1", 96.0),
    ("20250002", "EEE130", "2026-2027-1", 89.0),
    ("20250003", "GEO110", "2026-2027-1", 93.0),
    ("20250004", "ELS101", "2026-2027-1", 84.0),
    ("20240001", "MEC130", "2026-2027-1", 90.0),
    ("20240001", "ENG101", "2026-2027-1", 88.0),
    ("20240002", "ENG101", "2026-2027-1", 85.0),
    ("20240003", "MED110", "2026-2027-1", 95.0),
    ("20230001", "EEE130", "2026-2027-1", 97.0),
    ("20230002", "EEE130", "2026-2027-1", None),
)


@dataclass(frozen=True)
class SeedResult:
    departments: int
    majors: int
    classes: int
    students: int
    courses: int
    enrollments: int


def seed_demo(db_path: Path | str | None = None, *, reset: bool = False) -> SeedResult:
    """Populate a database with the canonical Xingyuan demo dataset.

    Without ``reset`` this only runs on a completely empty business database.
    With ``reset`` all business rows are deleted first and the seed is rebuilt
    in one transaction.
    """

    with connect(db_path) as connection:
        if not reset and _has_business_data(connection):
            raise ValueError("数据库中已有数据；如需重建演示数据，请使用 --reset")

        if reset:
            _clear_business_data(connection)

        connection.executemany(
            "INSERT INTO departments(code, name) VALUES (?, ?)",
            DEPARTMENTS,
        )
        connection.executemany(
            """
            INSERT INTO majors(code, name, department_id)
            VALUES (?, ?, (SELECT id FROM departments WHERE code = ?))
            """,
            MAJORS,
        )
        connection.executemany(
            """
            INSERT INTO classes(code, name, major_id, enrollment_year)
            VALUES (?, ?, (SELECT id FROM majors WHERE code = ?), ?)
            """,
            CLASSES,
        )
        connection.executemany(
            """
            INSERT INTO students(
                student_no, name, family, branch, gender, birth_date,
                enrollment_year, class_id, status,
                primary_element, primary_affinity, dormitory
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                (SELECT id FROM classes WHERE code = ?),
                ?, ?, ?, ?
            )
            """,
            STUDENTS,
        )
        connection.executemany(
            """
            INSERT INTO courses(course_code, name, department_id, credits, hours)
            VALUES (?, ?, (SELECT id FROM departments WHERE code = ?), ?, ?)
            """,
            COURSES,
        )
        connection.executemany(
            """
            INSERT INTO enrollments(student_id, course_id, semester, score)
            VALUES (
                (SELECT id FROM students WHERE student_no = ?),
                (SELECT id FROM courses WHERE course_code = ?),
                ?, ?
            )
            """,
            ENROLLMENTS,
        )

    return SeedResult(
        departments=len(DEPARTMENTS),
        majors=len(MAJORS),
        classes=len(CLASSES),
        students=len(STUDENTS),
        courses=len(COURSES),
        enrollments=len(ENROLLMENTS),
    )


def _has_business_data(connection) -> bool:
    tables = ("departments", "majors", "classes", "students", "courses", "enrollments")
    return any(
        connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is not None
        for table in tables
    )


def _clear_business_data(connection) -> None:
    for table in ("enrollments", "students", "classes", "majors", "courses", "departments"):
        connection.execute(f"DELETE FROM {table}")
    connection.execute(
        "DELETE FROM sqlite_sequence WHERE name IN (?, ?, ?, ?, ?, ?)",
        ("departments", "majors", "classes", "students", "courses", "enrollments"),
    )
