"""python examples/storage_stages.py --file demo-campus.json --db demo-campus.db

Run only against demonstration paths: the final stage requires an empty DB.
"""
from pathlib import Path
import argparse
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from xingyuan_sis.database import initialize_database
from xingyuan_sis.file_storage import JsonRepository, MemoryRepository
from xingyuan_sis.service import XingyuanService


def main():
    parser = argparse.ArgumentParser(description="内存 → JSON 文件 → SQLite 存储演进")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    memory = MemoryRepository()
    service = XingyuanService(repository=memory)
    service.create_department(code="SCI", name="自然科学学院")
    service.create_major(code="ELS", name="元素学", department_code="SCI")
    service.create_class(code="ELS2601", name="元素学2601班", major_code="ELS", enrollment_year=2026)
    service.create_species_family(name="犬科")
    service.create_species_branch(name="灰狼", family="犬科")
    service.register_student(student_no="00202601", name="示例同窗", family="犬科", branch="灰狼", enrollment_year=2026, class_code="ELS2601")
    service.create_announcement(title="欢迎来到星原", body="每一种天性，都有名字。", class_code="ELS2601")
    service.create_course(course_code="EL101", name="元素学导论", credits=3, hours=48, department_code="SCI")
    service.add_grade(student_no="00202601", course_code="EL101", semester="2026-秋", score=None)
    print("内存阶段：", service.list_students()[0]["name"], service.list_announcements()[0]["title"])
    file_service = XingyuanService(repository=JsonRepository(args.file))
    file_service.repository.restore_archive(memory.data)
    # Reopen, mutate and reopen again: proves JSON is the actual source of truth.
    reopened = XingyuanService(repository=JsonRepository(args.file))
    reopened.update_student_by_no("00202601", notes="文件阶段重启后修改")
    print("JSON 重启读取：", XingyuanService(repository=JsonRepository(args.file)).student_by_no("00202601")["notes"])
    initialize_database(args.db)
    final = XingyuanService(args.db)
    final.import_archive(args.file)
    print("SQLite 阶段：", len(final.list_students()), "学生；", len(final.list_announcements()), "公告")


if __name__ == "__main__":
    main()
