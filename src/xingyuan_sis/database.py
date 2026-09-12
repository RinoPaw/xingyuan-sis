from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

DATA_DIR = Path.cwd() / "data"
DB_PATH = DATA_DIR / "xingyuan.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS majors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    department_id INTEGER NOT NULL,
    UNIQUE(name, department_id),
    FOREIGN KEY (department_id) REFERENCES departments(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    major_id INTEGER NOT NULL,
    enrollment_year INTEGER NOT NULL CHECK(enrollment_year >= 1900),
    UNIQUE(name, major_id, enrollment_year),
    FOREIGN KEY (major_id) REFERENCES majors(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS species_families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS species_branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    family_id INTEGER NOT NULL,
    UNIQUE(name, family_id),
    FOREIGN KEY (family_id) REFERENCES species_families(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_no TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    species_branch_id INTEGER NOT NULL,
    gender TEXT,
    birth_date TEXT,
    enrollment_year INTEGER NOT NULL CHECK(enrollment_year >= 1900),
    class_id INTEGER,
    status TEXT NOT NULL DEFAULT '在读',
    primary_element TEXT,
    primary_affinity TEXT,
    contact TEXT,
    dormitory TEXT,
    notes TEXT,
    password_hash TEXT,
    must_change_password INTEGER NOT NULL DEFAULT 1 CHECK(must_change_password IN (0, 1)),
    FOREIGN KEY (species_branch_id) REFERENCES species_branches(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (class_id) REFERENCES classes(id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    department_id INTEGER,
    credits REAL NOT NULL DEFAULT 0 CHECK(credits >= 0),
    hours INTEGER NOT NULL DEFAULT 0 CHECK(hours >= 0),
    FOREIGN KEY (department_id) REFERENCES departments(id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    semester TEXT NOT NULL,
    score REAL CHECK(score IS NULL OR (score >= 0 AND score <= 100)),
    UNIQUE(student_id, course_id, semester),
    FOREIGN KEY (student_id) REFERENCES students(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_students_name ON students(name);
CREATE INDEX IF NOT EXISTS idx_students_class_id ON students(class_id);
CREATE INDEX IF NOT EXISTS idx_students_species_branch_id ON students(species_branch_id);
CREATE INDEX IF NOT EXISTS idx_species_branches_family_id ON species_branches(family_id);
CREATE INDEX IF NOT EXISTS idx_courses_name ON courses(name);
CREATE INDEX IF NOT EXISTS idx_enrollments_student_id ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course_id ON enrollments(course_id);
"""

_LEGACY_SPECIES_MIGRATION = """
PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS species_families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS species_branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    family_id INTEGER NOT NULL,
    UNIQUE(name, family_id),
    FOREIGN KEY (family_id) REFERENCES species_families(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

INSERT OR IGNORE INTO species_families(name)
SELECT DISTINCT family FROM students ORDER BY family;

INSERT OR IGNORE INTO species_branches(name, family_id)
SELECT DISTINCT s.branch, f.id
FROM students AS s
JOIN species_families AS f ON f.name = s.family
ORDER BY s.family, s.branch;

CREATE TABLE students_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_no TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    species_branch_id INTEGER NOT NULL,
    gender TEXT,
    birth_date TEXT,
    enrollment_year INTEGER NOT NULL CHECK(enrollment_year >= 1900),
    class_id INTEGER,
    status TEXT NOT NULL DEFAULT '在读',
    primary_element TEXT,
    primary_affinity TEXT,
    contact TEXT,
    dormitory TEXT,
    notes TEXT,
    password_hash TEXT,
    must_change_password INTEGER NOT NULL DEFAULT 1 CHECK(must_change_password IN (0, 1)),
    FOREIGN KEY (species_branch_id) REFERENCES species_branches(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (class_id) REFERENCES classes(id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

INSERT INTO students_new(
    id, student_no, name, species_branch_id, gender, birth_date,
    enrollment_year, class_id, status, primary_element, primary_affinity,
    contact, dormitory, notes, password_hash, must_change_password
)
SELECT
    s.id, s.student_no, s.name, b.id, s.gender, s.birth_date,
    s.enrollment_year, s.class_id, s.status, s.primary_element,
    s.primary_affinity, s.contact, s.dormitory, s.notes, NULL, 1
FROM students AS s
JOIN species_families AS f ON f.name = s.family
JOIN species_branches AS b ON b.family_id = f.id AND b.name = s.branch;

DROP TABLE students;
ALTER TABLE students_new RENAME TO students;

PRAGMA foreign_keys = ON;
"""


@contextmanager
def connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Commit or roll back a transaction, then always close its connection."""
    path = Path(db_path) if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(db_path: Path | str | None = None) -> None:
    with connect(db_path) as connection:
        if _uses_legacy_species_columns(connection):
            connection.executescript(_LEGACY_SPECIES_MIGRATION)
        connection.executescript(SCHEMA)
        _ensure_auth_columns(connection)


def _uses_legacy_species_columns(connection: sqlite3.Connection) -> bool:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'students'"
    ).fetchone()
    if exists is None:
        return False
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(students)")}
    return {"family", "branch"}.issubset(columns) and "species_branch_id" not in columns


def _ensure_auth_columns(connection: sqlite3.Connection) -> None:
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(students)")}
    if "password_hash" not in columns:
        connection.execute("ALTER TABLE students ADD COLUMN password_hash TEXT")
    if "must_change_password" not in columns:
        connection.execute(
            "ALTER TABLE students ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 1 "
            "CHECK(must_change_password IN (0, 1))"
        )
