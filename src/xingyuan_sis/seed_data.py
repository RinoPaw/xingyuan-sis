from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
    ("EEE2601", "元素工程2601班", "EEE", 2026),
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

# Age and birthday are descriptive source data only. They never control
# admission eligibility, enrollment year, class assignment, or seed inclusion.
# A birthday without a known year is stored as --MM-DD rather than inventing a
# full date from the character's narrative age.
# name, family, branch, gender, sourced age, sourced birthday (month, day), work
_CHARACTER_PROFILES = (
    # BEASTARS
    ("雷格西", "犬科", "灰狼", "男", 19, (4, 9), "BEASTARS"),
    ("路易", "鹿科", "红鹿", "男", 20, (3, 29), "BEASTARS"),
    ("茱诺", "犬科", "灰狼", "女", 18, (2, 12), "BEASTARS"),
    ("杰克", "犬科", "拉布拉多猎犬", "男", 19, (12, 22), "BEASTARS"),
    ("比尔", "猫科", "孟加拉虎", "男", 18, (8, 16), "BEASTARS"),
    ("里兹", "熊科", "棕熊", "男", 19, (12, 11), "BEASTARS"),
    ("刚兵", "熊科", "大熊猫", "男", 39, (6, 9), "BEASTARS"),
    ("皮纳", "牛科", "白大角羊", "男", 18, (12, 27), "BEASTARS"),
    ("席拉", "猫科", "猎豹", "女", 18, (6, 21), "BEASTARS"),
    ("米古诺", "鬣狗科", "斑鬣狗", "男", 19, (8, 2), "BEASTARS"),
    ("青叶", "鹰科", "白头海雕", "男", None, None, "BEASTARS"),
    # 疯狂动物城
    ("尼克·王尔德", "犬科", "赤狐", "男", None, None, "疯狂动物城"),
    ("Bogo", "牛科", "非洲水牛", "男", None, None, "疯狂动物城"),
    ("Benjamin Clawhauser", "猫科", "猎豹", "男", None, None, "疯狂动物城"),
    ("Dawn Bellwether", "牛科", "绵羊", "女", None, None, "疯狂动物城"),
    ("Leodore Lionheart", "猫科", "狮", "男", None, None, "疯狂动物城"),
    ("闪电", "树懒科", "三趾树懒", "男", None, None, "疯狂动物城"),
    ("大先生", "鼩鼱科", "鼩鼱", "男", None, None, "疯狂动物城"),
    ("夏奇羊", "牛科", "瞪羚", "女", None, None, "疯狂动物城"),
    ("芬尼克", "犬科", "耳廓狐", "男", None, None, "疯狂动物城"),
    ("杜克·威斯顿", "鼬科", "白鼬", "男", None, None, "疯狂动物城"),
    ("吉丁·格雷", "犬科", "赤狐", "男", None, None, "疯狂动物城"),
    # 功夫熊猫
    ("阿宝", "熊科", "大熊猫", "男", None, None, "功夫熊猫"),
    ("师父", "小熊猫科", "小熊猫", "男", None, None, "功夫熊猫"),
    ("悍娇虎", "猫科", "华南虎", "女", None, None, "功夫熊猫"),
    ("残豹", "猫科", "雪豹", "男", None, None, "功夫熊猫"),
    ("龟大仙", "陆龟科", "加拉帕戈斯象龟", "男", None, None, "功夫熊猫"),
    ("猴王", "猴科", "川金丝猴", "男", None, None, "功夫熊猫"),
    ("快螳螂", "螳科", "中华大刀螳", "男", None, None, "功夫熊猫"),
    ("灵鹤", "鹤科", "丹顶鹤", "男", None, None, "功夫熊猫"),
    ("俏小龙", "蝰科", "赤尾青竹丝", "女", None, None, "功夫熊猫"),
    ("鹅阿爹", "鸭科", "鹅", "男", None, None, "功夫熊猫"),
    # BNA
    ("影森满", "犬科", "日本狸", "女", 18, (5, 13), "BNA"),
    ("大神士郎", "犬科", "狼", "男", None, None, "BNA"),
    ("玛丽伊丹", "鼬科", "水貂", "女", None, None, "BNA"),
    ("梅丽莎·霍纳", "袋熊科", "袋熊", "女", None, None, "BNA"),
    ("尼娜", "海豚科", "海豚", "女", None, None, "BNA"),
    ("Pinga", "信天翁科", "漂泊信天翁", "男", None, None, "BNA"),
    # 冲吧烈子
    ("烈子", "小熊猫科", "小熊猫", "女", 25, (11, 6), "冲吧烈子"),
    ("灰田", "鬣狗科", "斑鬣狗", "男", None, None, "冲吧烈子"),
    ("芬妮可", "犬科", "耳廓狐", "女", 25, (12, 31), "冲吧烈子"),
    ("鹫美", "鹰科", "蛇鹫", "女", None, None, "冲吧烈子"),
    ("五里", "猩猩科", "大猩猩", "女", None, None, "冲吧烈子"),
    ("角田", "牛科", "瞪羚", "女", None, None, "冲吧烈子"),
    ("只野", "马科", "驴", "男", None, None, "冲吧烈子"),
    # Echo
    ("Chase Hunter", "鼬科", "北美河獭", "男", 21, None, "Echo"),
    ("Leo Alvarez", "犬科", "红狼", "男", 24, None, "Echo"),
    ("Jenna Begay", "犬科", "敏狐", "女", 22, None, "Echo"),
    ("TJ Hess", "猫科", "加拿大猞猁", "男", 19, None, "Echo"),
    ("Carl Hendricks", "牛科", "大角羊", "男", 21, (4, 19), "Echo"),
    ("Flynn Moore", "毒蜥科", "希拉毒蜥", "男", 23, None, "Echo"),
    # Lackadaisy
    ("Rocky Rickaby", "猫科", "家猫", "男", 22, (12, 19), "Lackadaisy"),
    ("Calvin McMurray", "猫科", "家猫", "男", 18, (3, 10), "Lackadaisy"),
    ("Ivy Pepper", "猫科", "家猫", "女", 18, (5, 20), "Lackadaisy"),
    ("Mordecai Heller", "猫科", "家猫", "男", 28, (3, 28), "Lackadaisy"),
    ("Mitzi May", "猫科", "家猫", "女", 32, (9, 25), "Lackadaisy"),
    ("Viktor Vasko", "猫科", "家猫", "男", 41, (4, 16), "Lackadaisy"),
    ("Serafine Savoy", "猫科", "家猫", "女", 24, (10, 25), "Lackadaisy"),
    ("Nicodeme Savoy", "猫科", "家猫", "男", 26, None, "Lackadaisy"),
    # Blacksad
    ("John Blacksad", "猫科", "家猫", "男", None, None, "Blacksad"),
    ("Weekly", "鼬科", "鼬", "男", None, None, "Blacksad"),
    ("Smirnov", "犬科", "德国牧羊犬", "男", None, None, "Blacksad"),
    ("Alma Mayer", "猫科", "家猫", "女", None, None, "Blacksad"),
    # Night in the Woods
    ("Mae Borowski", "猫科", "家猫", "女", 20, None, "Night in the Woods"),
    ("Gregg Lee", "犬科", "赤狐", "男", 21, None, "Night in the Woods"),
    ("Angus Delaney", "熊科", "熊", "男", 21, None, "Night in the Woods"),
    ("Bea Santello", "鳄科", "鳄鱼", "女", 20, None, "Night in the Woods"),
    # 刺猬索尼克
    ("索尼克", "猬科", "刺猬", "男", 15, None, "刺猬索尼克"),
    ("塔尔斯", "犬科", "双尾狐", "男", 8, None, "刺猬索尼克"),
    ("纳克鲁斯", "针鼹科", "针鼹", "男", 16, None, "刺猬索尼克"),
    ("艾咪", "猬科", "刺猬", "女", 12, None, "刺猬索尼克"),
    ("夏特", "猬科", "刺猬", "男", None, None, "刺猬索尼克"),
    ("罗姬", "蝙蝠科", "蝙蝠", "女", 18, None, "刺猬索尼克"),
    ("贝库特", "鳄科", "鳄鱼", "男", 20, None, "刺猬索尼克"),
    ("艾斯皮欧", "避役科", "变色龙", "男", 16, None, "刺猬索尼克"),
    ("布蕾姿", "猫科", "家猫", "女", 14, None, "刺猬索尼克"),
    # Adastra
    ("Amicus", "犬科", "狼", "男", 23, (12, 14), "Adastra"),
    ("Neferu", "犬科", "胡狼", "男", None, None, "Adastra"),
    ("Cassius", "犬科", "狼", "男", 21, None, "Adastra"),
    ("Alexios", "猫科", "家猫", "男", None, None, "Adastra"),
    # Star Fox
    ("Fox McCloud", "犬科", "赤狐", "男", 18, None, "Star Fox"),
    ("Krystal", "犬科", "狐", "女", 19, None, "Star Fox"),
    ("Wolf O'Donnell", "犬科", "狼", "男", None, None, "Star Fox"),
    ("Leon Powalski", "避役科", "变色龙", "男", None, None, "Star Fox"),
    # 家有大猫
    ("林虎", "猫科", "虎", "男", None, None, "家有大猫"),
    ("李克劳", "猫科", "云豹", "男", None, None, "家有大猫"),
    ("颜书齐", "猫科", "石虎", "男", None, None, "家有大猫"),
    # 骑士学院
    ("Argo Northrop", "犬科", "狼", "男", None, None, "骑士学院"),
    ("Grantly Bell", "猫科", "虎", "男", None, None, "骑士学院"),
    ("Oscar Lawrence", "犬科", "犬", "男", None, None, "骑士学院"),
    ("Theo Prinz von Hirschreich", "猫科", "黑豹", "男", None, None, "骑士学院"),
    ("Diederich Olsen", "犬科", "狼/狐（未定）", "男", None, (6, 8), "骑士学院"),
    ("Celio Delatorre", "犬科", "犬", "男", None, None, "骑士学院"),
    ("Julius Quingnard", "猫科", "狮", "男", None, None, "骑士学院"),
    ("Paul Pfitzner", "熊科", "北极熊", "男", None, None, "骑士学院"),
    ("Hermann Fürst von Eden", "猪科", "野猪", "男", None, None, "骑士学院"),
    ("Scheat", "龙科", "龙", "男", None, None, "骑士学院"),
    # Password
    ("Dave Halloway", "鬣狗科", "鬣狗", "男", None, None, "Password"),
    ("Tyson Grey", "犬科", "狼犬混血", "男", 20, None, "Password"),
    ("Dean Orson", "熊科", "熊", "男", None, None, "Password"),
    ("Orlando Noble", "龙科", "龙", "男", None, None, "Password"),
    ("Hoss Warner", "猫科", "狮", "男", None, None, "Password"),
    ("Sal Warden", "鳄科", "鳄鱼", "男", None, None, "Password"),
    ("Roswell Sinclair", "猪科", "野猪", "男", None, None, "Password"),
    # 矛之酒馆
    ("Eyvind", "犬科", "狼", "男", 24, None, "矛之酒馆"),
    ("Snow", "犬科", "狼", "男", None, None, "矛之酒馆"),
    ("Witer", "鳄科", "短吻鳄", "男", None, None, "矛之酒馆"),
    ("Hakan", "龙科", "龙", "男", 85, None, "矛之酒馆"),
    ("Nauxus", "蜥蜴科", "蜥蜴", "男", None, None, "矛之酒馆"),
    ("Selye", "蛇科", "娜迦", "男", None, None, "矛之酒馆"),
    ("Axel", "牛科", "牛", "男", None, None, "矛之酒馆"),
    ("Thane", "牛科", "牛", "男", None, None, "矛之酒馆"),
    ("Bread", "猫科", "雪豹", "男", None, None, "矛之酒馆"),
)

_YEAR_CLASS_CODES = {
    2026: ("ELS2601", "ELS2602", "MET2601", "ELE2601", "EEE2601", "MEC2601", "BIO2601", "MED2601"),
    2025: ("ELS2501", "GEO2501", "MET2501", "ELE2501", "INS2501", "CIV2501", "BIO2501"),
    2024: ("GEO2401", "ELE2401", "EEE2401", "MEC2401", "INS2401", "CIV2401", "MED2401"),
    2023: ("ELS2301", "EEE2301", "MEC2301", "MED2301"),
}

_ELEMENTS = ("风", "水", "火", "雷", "岩", "光")
_AFFINITIES = ("A", "B", "B", "C", "A", "B")
_NOTES = ("元素学社活动成员", "校刊编辑组", "实验室值班助理", "校运动会志愿者", "交换培养申请中")


def _birth_date(birthday: tuple[int, int] | None) -> str | None:
    if birthday is None:
        return None
    month, day = birthday
    return f"--{month:02d}-{day:02d}"


def _character_students() -> tuple[tuple[object, ...], ...]:
    year_order = (2026, 2025, 2024, 2023)
    counters = {year: 0 for year in year_order}
    class_offsets = {year: 0 for year in year_order}
    rows: list[tuple[object, ...]] = []

    for index, (name, family, branch, gender, age, birthday, _source) in enumerate(
        _CHARACTER_PROFILES,
        start=1,
    ):
        # Academic placement is demo data and intentionally independent of age.
        year = year_order[(index - 1) % len(year_order)]
        counters[year] += 1
        student_no = f"{year}{counters[year]:04d}"
        class_codes = _YEAR_CLASS_CODES[year]
        class_code = class_codes[class_offsets[year] % len(class_codes)]
        class_offsets[year] += 1

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
                student_no, name, family, branch, gender, _birth_date(birthday), age,
                year, class_code, status, primary_element, primary_affinity,
                contact, dormitory, notes,
            )
        )

    return tuple(rows)


STUDENTS = _character_students()


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
        class_code = str(student[8])
        status = str(student[9])
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
    """Compatibility entry point for the service-owned demo seed operation."""
    from .service import XingyuanService

    return XingyuanService(db_path).seed_demo(reset=reset)
