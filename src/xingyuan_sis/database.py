from pathlib import Path
import sqlite3

DATA_DIR = Path.cwd() / "data"
DB_PATH = DATA_DIR / "xingyuan.db"


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    """Create the database file and prepare the connection environment.

    Table definitions are intentionally left to the data-model issue.
    """
    with connect():
        pass
