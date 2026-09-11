from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.database import connect, initialize_database


class DatabaseTests(unittest.TestCase):
    def test_connection_commits_and_closes(self) -> None:
        with TemporaryDirectory() as directory:
            db = Path(directory) / "test.db"
            initialize_database(db)
            with connect(db) as connection:
                connection.execute("INSERT INTO departments(code, name) VALUES ('SCI', '科学')")
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")
            with connect(db) as check:
                self.assertEqual(check.execute("SELECT COUNT(*) FROM departments").fetchone()[0], 1)

    def test_failure_rolls_back_and_closes(self) -> None:
        with TemporaryDirectory() as directory:
            db = Path(directory) / "test.db"
            initialize_database(db)
            with self.assertRaises(ValueError):
                with connect(db) as connection:
                    connection.execute("INSERT INTO departments(code, name) VALUES ('SCI', '科学')")
                    raise ValueError("cancel")
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")
            with connect(db) as check:
                self.assertEqual(check.execute("SELECT COUNT(*) FROM departments").fetchone()[0], 0)
