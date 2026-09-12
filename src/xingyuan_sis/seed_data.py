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
    ("ELS2602", "元素学2602班", "ELS", 2026),
    ("ELS2501", "元素学2501班", "ELS", 2025),
    ("ELS2301", "元素学2301班", "ELS", 2023),
    ("GEO2501", "地质与矿业2501班", "GEO", 2025),
    ("GEO2401", "地质与矿业2401班", "GEO", 2024),
    ("MET2601", "气象学2601班", "MET", 2026),
    ("MET2501", "气象学2501班", "MET", 2025),
    ("ELE2601", "元素工程2601班", "ELE", 2026),
    ("ELE2501", "元素工程2501班", "ELE", 2025),
    ("ELE2401", "元素工程2401班", "ELE", 2024),
    ("EEE2601", "电气工程2601班", "EEE", 2026),
    ("EEE2401", "电气工程2401班", "EEE", 2024),
    ("EEE2301", "电气工程2301班", "EEE", 2023),
    ("MEC2601", "机械工程2601班", "MEC", 2026),
    ("MEC2401", "机械工程2401班", "MEC", 2024),
    ("MEC2301", "机械工程2301班", "MEC", 2023),
    ("INS2501", "仪器与计量2501班", "INS", 2025),
    ("INS2401", "仪器与计量2401班", "INS", 2024),
    ("CIV2501", "建筑与土木2501班", "CIV", 2025),
    ("CIV2401", "建筑与土木2401班", "CIV", 2024),
    ("BIO2601", "生物学2601班", "BIO", 2026),
    ("BIO2501", "生物学2501班", "BIO", 2025),
    ("MED2601", "医学2601班", "MED", 2026),
    ("MED2401", "医学2401班", "MED", 2024),
    ("MED2301", "医学2301班", "MED", 2023),
)

_BASE_STUDENTS = (
    ("20260001", "林岚", "猫科", "石虎", "女", "2008-03-17", 2026, "ELS2601", "在读", "风", "A", "13000000001", "北区 3-214", "元素测量实验助理"),
    ("20260002", "闻溪", "兔科", "雪兔", "女", "2008-11-02", 2026, "BIO2601", "在读", "水", "B", None, "北区 2-308", None),
    ("20260003", "乔澈", "犬科", "萨摩耶", "男", "2007-12-21", 2026, "MET2601", "在读", "风", "B", "13000000003", "北区 5-116", None),
    ("20250001", "许麦", "犬科", "金毛", "男", "2007-05-09", 2025, "ELE2501", "在读", "火", "A", "13000000004", "东区 1-407", "工程训练中心助理"),
    ("20250002", "沈芦", "犬科", "边境牧羊犬", "女", "2006-10-14", 2025, "INS2501", "在读", "雷", "A", None, "东区 2-221", None),
    ("20250003", "黎钧", "猫科", "黑豹", "男", "2007-01-28", 2025, "GEO2501", "在读", "岩", "A", "13000000006", "东区 4-318", None),
    ("20250004", "唐棠", "狐科", "赤狐", "女", "2006-08-06", 2025, "ELS2501", "在读", "光", "B", "13000000007", "东区 3-205", "校刊摄影组"),
    ("20240001", "白榆", "猫科", "东北虎", "男", "2005-04-12", 2024, "MEC2401", "在读", "火", "B", "13000000008", "南区 2-410", None),
    ("20240002", "鹿遥", "鹿科", "梅花鹿", "女", "2005-09-30", 2024, "CIV2401", "在读", "岩", "A", None, "南区 1-302", None),
    ("20240003", "苏栎", "狐科", "赤狐", "女", "2005-01-19", 2024, "MED2401", "在读", "水", "B", "13000000010", "南区 5-209", "急救社成员"),
    ("20230001", "唐砾", "犬科", "德国牧羊犬", "男", "2004-06-25", 2023, "EEE2301", "在读", "雷", "A", "13000000011", "西区 2-116", None),
    ("20230002", "鹤川", "狼科", "灰狼", "男", "2004-02-07", 2023, "EEE2301", "休学", "风", "C", None, "西区 2-118", "保留学籍"),
)

# Established furry / anthropomorphic characters are used as diverse demo names.
# Stable Chinese translations are preferred where available; otherwise the
# original name is retained. The family/branch pair stays close to the source.
_CHARACTER_PROFILES = (
    # BEASTARS
    ("雷格西", "犬科", "灰狼", "男"),
    ("春", "兔科", "侏儒兔", "女"),
    ("路易", "鹿科", "红鹿", "男"),
    ("茱诺", "犬科", "灰狼", "女"),
    ("杰克", "犬科", "拉布拉多猎犬", "男"),
    ("比尔", "猫科", "孟加拉虎", "男"),
    ("里兹", "熊科", "棕熊", "男"),
    ("刚兵", "熊科", "大熊猫", "男"),
    ("皮纳", "牛科", "白大角羊", "男"),
    ("席拉", "猫科", "豹", "女"),
    ("米古诺", "鬣狗科", "斑鬣狗", "男"),
    ("青叶", "鹰科", "白头海雕", "男"),
    # 疯狂动物城
    ("朱迪·霍普斯", "兔科", "棉尾兔", "女"),
    ("尼克·王尔德", "犬科", "赤狐", "男"),
    ("牛局长", "牛科", "非洲水牛", "男"),
    ("本杰明警官", "猫科", "猎豹", "男"),
    ("羊副市长", "牛科", "绵羊", "女"),
    ("狮市长", "猫科", "狮", "男"),
    ("闪电", "树懒科", "三趾树懒", "男"),
    ("大先生", "鼩鼱科", "鼩鼱", "男"),
    ("夏奇羊", "牛科", "瞪羚", "女"),
    ("芬尼克", "犬科", "耳廓狐", "男"),
    ("杜克·威斯顿", "鼬科", "白鼬", "男"),
    ("吉丁", "犬科", "赤狐", "男"),
    # 功夫熊猫
    ("阿宝", "熊科", "大熊猫", "男"),
    ("师父", "小熊猫科", "小熊猫", "男"),
    ("悍娇虎", "猫科", "华南虎", "女"),
    ("残豹", "猫科", "雪豹", "男"),
    ("龟大仙", "陆龟科", "加拉帕戈斯象龟", "男"),
    ("猴王", "猴科", "川金丝猴", "男"),
    ("快螳螂", "螳科", "中华大刀螳", "男"),
    ("灵鹤", "鹤科", "丹顶鹤", "男"),
    ("俏小龙", "蝰科", "赤尾青竹丝", "女"),
    ("鹅阿爹", "鸭科", "鹅", "男"),
    # BNA
    ("影森满", "犬科", "日本狸", "女"),
    ("大神士郎", "犬科", "狼", "男"),
    ("玛丽伊丹", "鼬科", "水貂", "女"),
    ("杰姆·霍纳", "雉科", "鸡", "男"),
    ("梅丽莎·霍纳", "袋熊科", "袋熊", "女"),
    ("尼娜", "海豚科", "海豚", "女"),
    ("Pinga", "信天翁科", "漂泊信天翁", "男"),
    # 冲吧烈子
    ("烈子", "小熊猫科", "小熊猫", "女"),
    ("灰田", "鬣狗科", "斑鬣狗", "男"),
    ("芬妮可", "犬科", "耳廓狐", "女"),
    ("鹫美", "鹰科", "蛇鹫", "女"),
    ("五里", "猩猩科", "大猩猩", "女"),
    ("角田", "牛科", "瞪羚", "女"),
    ("只野", "马科", "驴", "男"),
    # Echo
    ("Chase Hunter", "鼬科", "北美水獭", "男"),
    ("Leo Alvarez", "犬科", "红狼", "男"),
    ("Jenna Begay", "犬科", "敏狐", "女"),
    ("TJ Hess", "猫科", "加拿大猞猁", "男"),
    ("Carl Hendricks", "牛科", "大角羊", "男"),
    ("Flynn Moore", "毒蜥科", "希拉毒蜥", "男"),
    # Lackadaisy
    ("Rocky Rickaby", "猫科", "家猫", "男"),
    ("Calvin McMurray", "猫科", "家猫", "男"),
    ("Ivy Pepper", "猫科", "家猫", "女"),
    ("Mordecai Heller", "猫科", "家猫", "男"),
    ("Mitzi May", "猫科", "家猫", "女"),
    ("Viktor Vasko", "猫科", "家猫", "男"),
    ("Serafine Savoy", "猫科", "家猫", "女"),
    ("Nicodeme Savoy", "猫科", "家猫", "男"),
    # Blacksad
    ("John Blacksad", "猫科", "家猫", "男"),
    ("Weekly", "鼬科", "鼬", "男"),
    ("Smirnov", "犬科", "德国牧羊犬", "男"),
    ("Alma Mayer", "猫科", "家猫", "女"),
    # Night in the Woods
    ("Mae Borowski", "猫科", "家猫", "女"),
    ("Gregg Lee", "犬科", "赤狐", "男"),
    ("Angus Delaney", "熊科", "熊", "男"),
    ("Bea Santello", "鳄科", "鳄鱼", "女"),
    # 刺猬索尼克
    ("刺猬索尼克", "猬科", "刺猬", "男"),
    ("麦尔斯·“塔尔斯”·普劳尔", "犬科", "双尾狐", "男"),
    ("针鼹纳克鲁斯", "针鼹科", "针鼹", "男"),
    ("艾咪·罗斯", "猬科", "刺猬", "女"),
    ("刺猬夏特", "猬科", "刺猬", "男"),
    ("露姬", "蝙蝠科", "蝙蝠", "女"),
    ("鳄鱼贝库特", "鳄科", "鳄鱼", "男"),
    ("艾斯皮欧", "避役科", "变色龙", "男"),
    ("猫咪布蕾姿", "猫科", "家猫", "女"),
    # Adastra
    ("Amicus", "犬科", "狼", "男"),
    ("Neferu", "犬科", "胡狼", "男"),
    ("Cassius", "犬科", "狼", "男"),
    ("Alexios", "猫科", "家猫", "男"),
    # Star Fox
    ("Fox McCloud", "犬科", "赤狐", "男"),
    ("Peppy Hare", "兔科", "兔", "男"),
    ("Krystal", "犬科", "狐", "女"),
    ("Wolf O'Donnell", "犬科", "狼", "男"),
    ("Leon Powalski", "避役科", "变色龙", "男"),
)

_YEAR_CLASS_CODES = {
    2026: ("ELS2601", "ELS2602", "MET2601", "ELE2601", "EEE2601", "MEC2601", "BIO2601", "MED2601"),
    2025: ("ELS2501", "GEO2501", "MET2501", "ELE2501", "INS2501", "CIV2501", "BIO2501"),
    2024: ("GEO2401", "ELE2401", "EEE2401", "MEC2401", "INS2401", "CIV2401", "MED2401"),
    2023: ("ELS2301", "EEE2301", "MEC2301", "MED2301"),
}

_ELEMENTS = ("风", "水", "火", "雷", "岩", "光")
_AFFINITIES = ("A", "B", "B", "C", "A", "B")
_YEAR_TARGETS = {2026: 27, 2025: 24, 2024: 21, 2023: 16}
_EXISTING_YEAR_COUNTS = {2026: 3, 2025: 4, 2024: 3, 2023: 2}
_NOTES = ("元素学社活动成员", "校刊编辑组", "实验室值班助理", "校运动会志愿者", "交换培养申请中")


def _character_students() -> tuple[tuple[object, ...], ...]:
    remaining = dict(_YEAR_TARGETS)
    year_order = (2026, 2025, 2024, 2023)
    years: list[int] = []
    cursor = 0
    while len(years) < len(_CHARACTER_PROFILES):
        year = year_order[cursor % len(year_order)]
        cursor += 1
        if remaining[year] <= 0:
            continue
        years.append(year)
        remaining[year] -= 1

    counters = dict(_EXISTING_YEAR_COUNTS)
    class_offsets = {year: 0 for year in year_order}
    rows: list[tuple[object, ...]] = []

    for index, ((name, family, branch, gender), year) in enumerate(
        zip(_CHARACTER_PROFILES, years, strict=True),
        start=1,
    ):
        counters[year] += 1
        student_no = f"{year}{counters[year]:04d}"
        class_codes = _YEAR_CLASS_CODES[year]
        class_code = class_codes[class_offsets[year] % len(class_codes)]
        class_offsets[year] += 1

        birth_year = year - 18 - (index % 2)
        month = (index * 5) % 12 + 1
        day = (index * 7) % 28 + 1
        birth_date = f"{birth_year:04d}-{month:02d}-{day:02d}"

        if index % 29 == 0:
            status = "保留学籍"
        elif index % 19 == 0:
            status = "休学"
        else:
            status = "在读"

        primary_element = _ELEMENTS[(index - 1) % len(_ELEMENTS)]
        primary_affinity = _AFFINITIES[(index - 1) % len(_AFFINITIES)]
        contact = None if index % 4 == 0 else f"13{index % 10}{index:08d}"[-11:]
        campus = {2026: "北区", 2025: "东区", 2024: "南区", 2023: "西区"}[year]
        dormitory = f"{campus} {(index % 6) + 1}-{100 + ((index * 13) % 400):03d}"
        notes = _NOTES[(index // 13) % len(_NOTES)] if index % 13 == 0 else None

        rows.append(
            (
                student_no, name, family, branch, gender, birth_date, year,
                class_code, status, primary_element, primary_affinity,
                contact, dormitory, notes,
            )
        )

    return tuple(rows)


STUDENTS = _BASE_STUDENTS + _character_students()


def _species_catalog() -> tuple[tuple[tuple[str], ...], tuple[tuple[str, str], ...]]:
    families: dict[str, None] = {}
    branches: dict[tuple[str, str], None] = {}
    for student in STUDENTS:
        family = str(student[2])
        branch = str(student[3])
        families.setdefault(family, None)
        branches.setdefault((branch, family), None)
    return tuple((name,) for name in families), tuple(branches)


SPECIES_FAMILIES, SPECIES_BRANCHES = _species_catalog()

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
    ("SCI130", "实验设计与统计", "SCI", 2.5, 40),
    ("ELS210", "元素场分析", "SCI", 3.5, 56),
    ("GEO210", "矿物分析", "SCI", 3.0, 48),
    ("MET210", "天气系统", "SCI", 3.0, 48),
    ("ENG120", "工程材料", "ENG", 2.5, 40),
    ("ENG150", "程序设计基础", "ENG", 3.0, 48),
    ("ELE210", "元素装置设计", "ENG", 3.5, 56),
    ("BIO120", "生态与行为", "LIF", 2.5, 40),
    ("MED120", "生理学基础", "MED", 3.5, 56),
)

_MAJOR_COURSES = {
    "ELS": ("ELS101", "ELS120", "SCI130", "ELS210", "ENG150"),
    "GEO": ("GEO110", "GEO210", "SCI130", "ENG150", "ELS101"),
    "MET": ("MET110", "MET210", "SCI130", "ENG150", "ELS120"),
    "ELE": ("ELE120", "ELE210", "ENG101", "ENG120", "ENG150"),
    "EEE": ("ENG101", "EEE130", "ENG120", "ENG150", "ELE210"),
    "MEC": ("MEC130", "ENG101", "ENG120", "ENG150", "INS140"),
    "INS": ("INS140", "ENG101", "ENG120", "ENG150", "EEE130"),
    "CIV": ("ENG101", "ENG120", "ENG150", "GEO110", "SCI130"),
    "BIO": ("BIO110", "BIO120", "SCI130", "ELS101", "MED120"),
    "MED": ("MED110", "MED120", "BIO110", "BIO120", "SCI130"),
}


def _enrollments() -> tuple[tuple[object, ...], ...]:
    rows: list[tuple[object, ...]] = []
    for student_index, student in enumerate(STUDENTS):
        student_no = str(student[0])
        class_code = str(student[7])
        status = str(student[8])
        pool = _MAJOR_COURSES[class_code[:3]]
        start = student_index % len(pool)

        for slot in range(4):
            course_code = pool[(start + slot) % len(pool)]
            if status != "在读":
                score = None
            else:
                marker = (student_index * 7 + slot * 11) % 43
                if marker == 0:
                    score = None
                elif marker in {1, 2}:
                    score = float(48 + marker * 5)
                else:
                    score = float(62 + ((student_index * 13 + slot * 17) % 38))
            rows.append((student_no, course_code, "2026-2027-1", score))
    return tuple(rows)


ENROLLMENTS = _enrollments()


@dataclass(frozen=True)
class SeedResult:
    departments: int
    majors: int
    classes: int
    species_families: int
    species_branches: int
    students: int
    courses: int
    enrollments: int


def seed_demo(db_path: Path | str | None = None, *, reset: bool = False) -> SeedResult:
    """Populate a database with the canonical Xingyuan demo dataset."""

    with connect(db_path) as connection:
        if not reset and _has_business_data(connection):
            raise ValueError("数据库中已有数据；如需重建演示数据，请使用 --reset")

        if reset:
            _clear_business_data(connection)

        connection.executemany(
            "INSERT INTO departments(code, name) VALUES (?, ?)", DEPARTMENTS
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
            "INSERT INTO species_families(name) VALUES (?)",
            SPECIES_FAMILIES,
        )
        connection.executemany(
            """
            INSERT INTO species_branches(name, family_id)
            VALUES (?, (SELECT id FROM species_families WHERE name = ?))
            """,
            SPECIES_BRANCHES,
        )
        connection.executemany(
            """
            INSERT INTO students(
                student_no, name, species_branch_id, gender, birth_date,
                enrollment_year, class_id, status,
                primary_element, primary_affinity, contact, dormitory, notes
            ) VALUES (
                ?, ?,
                (
                    SELECT b.id
                    FROM species_branches AS b
                    JOIN species_families AS f ON f.id = b.family_id
                    WHERE f.name = ? AND b.name = ?
                ),
                ?, ?, ?,
                (SELECT id FROM classes WHERE code = ?),
                ?, ?, ?, ?, ?, ?
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
        species_families=len(SPECIES_FAMILIES),
        species_branches=len(SPECIES_BRANCHES),
        students=len(STUDENTS),
        courses=len(COURSES),
        enrollments=len(ENROLLMENTS),
    )


def _has_business_data(connection) -> bool:
    tables = (
        "departments", "majors", "classes", "species_families",
        "species_branches", "students", "courses", "enrollments",
    )
    return any(
        connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is not None
        for table in tables
    )


def _clear_business_data(connection) -> None:
    for table in (
        "enrollments", "students", "species_branches", "species_families",
        "classes", "majors", "courses", "departments",
    ):
        connection.execute(f"DELETE FROM {table}")
    connection.execute(
        "DELETE FROM sqlite_sequence WHERE name IN (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "departments", "majors", "classes", "species_families",
            "species_branches", "students", "courses", "enrollments",
        ),
    )
