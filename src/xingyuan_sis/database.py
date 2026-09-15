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
    """Create the current schema; historical schemas are not migrated in place."""
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)
