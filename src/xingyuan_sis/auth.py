from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Any

from .database import DATA_DIR, DB_PATH, connect

ADMIN_USERNAME = "Administrator"
DEMO_STUDENT_PASSWORD = "xingyuan"
_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 16
_INITIAL_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


@dataclass(frozen=True)
class Identity:
    username: str
    role: str
    student_no: str | None = None
    must_change_password: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_student(self) -> bool:
        return self.role == "student"


def auth_dir() -> Path:
    override = os.environ.get("XINGYUAN_HOME")
    return Path(override).expanduser() if override else DATA_DIR


def admin_path() -> Path:
    return auth_dir() / "admin.json"


def session_path() -> Path:
    return auth_dir() / "session.json"


def hash_password(password: str) -> str:
    password = validate_password(password)
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations_text, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("密码至少需要 8 个字符")
    return password


def generate_initial_password(length: int = 10) -> str:
    return "".join(secrets.choice(_INITIAL_PASSWORD_ALPHABET) for _ in range(length))


def has_admin() -> bool:
    try:
        data = _read_json(admin_path())
    except (OSError, ValueError):
        return False
    return bool(data and data.get("password_hash") and data.get("session_secret"))


def initialize_admin(password: str) -> Identity:
    if has_admin():
        raise ValueError("管理员已经初始化")
    _write_json(
        admin_path(),
        {
            "version": 1,
            "password_hash": hash_password(password),
            "session_secret": secrets.token_hex(32),
        },
    )
    return Identity(ADMIN_USERNAME, "admin")


def authenticate(
    db_path: Path | str | None,
    username: str,
    password: str,
) -> Identity | None:
    username = username.strip()
    if username == ADMIN_USERNAME:
        config = _admin_config()
        if config is not None and verify_password(password, str(config.get("password_hash", ""))):
            return Identity(ADMIN_USERNAME, "admin")
        return None

    with connect(db_path) as connection:
        try:
            row = connection.execute(
                """
                SELECT student_no, password_hash, must_change_password
                FROM students
                WHERE student_no = ?
                """,
                (username,),
            ).fetchone()
        except sqlite3.Error:
            return None
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return Identity(
        str(row["student_no"]),
        "student",
        str(row["student_no"]),
        bool(row["must_change_password"]),
    )


def change_password(
    db_path: Path | str | None,
    identity: Identity,
    password: str,
) -> Identity:
    encoded = hash_password(password)
    if identity.is_admin:
        config = _admin_config()
        if config is None:
            raise ValueError("管理员尚未初始化")
        if verify_password(password, config["password_hash"]):
            raise ValueError("新密码不能与当前密码相同")
        config["password_hash"] = encoded
        _write_json(admin_path(), config)
        return Identity(ADMIN_USERNAME, "admin")

    if identity.student_no is None:
        raise ValueError("学生身份缺少学号")
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT password_hash FROM students WHERE student_no = ?", (identity.student_no,)
        ).fetchone()
        if row is not None and verify_password(password, row["password_hash"]):
            raise ValueError("新密码不能与当前密码相同")
        cursor = connection.execute(
            """
            UPDATE students
            SET password_hash = ?, must_change_password = 0
            WHERE student_no = ?
            """,
            (encoded, identity.student_no),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"找不到学生：{identity.student_no}")
    return Identity(identity.student_no, "student", identity.student_no, False)


def reset_student_password(
    db_path: Path | str | None,
    student_no: str,
    password: str | None = None,
) -> str:
    initial = password or generate_initial_password()
    encoded = hash_password(initial)
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE students
            SET password_hash = ?, must_change_password = 1
            WHERE student_no = ?
            """,
            (encoded, student_no.strip()),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"找不到学生：{student_no}")
    return initial


def provision_demo_passwords(db_path: Path | str | None) -> None:
    encoded = hash_password(DEMO_STUDENT_PASSWORD)
    with connect(db_path) as connection:
        connection.execute(
            "UPDATE students SET password_hash = ?, must_change_password = 1",
            (encoded,),
        )


def write_session(identity: Identity, db_path: Path | str | None = None) -> None:
    payload: dict[str, Any] = {
        "version": 1,
        "username": identity.username,
        "role": identity.role,
        "database": str(_resolved_db_path(db_path)),
    }
    if identity.is_student:
        payload["student_no"] = identity.student_no
    payload["signature"] = _session_signature(payload)
    _write_json(session_path(), payload)


def read_session(db_path: Path | str | None = None) -> Identity | None:
    try:
        payload = _read_json(session_path())
    except (OSError, ValueError):
        return None
    if not payload:
        return None
    signature = payload.get("signature")
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    try:
        expected_signature = _session_signature(unsigned)
    except (TypeError, ValueError):
        return None
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected_signature):
        return None
    if payload.get("database") != str(_resolved_db_path(db_path)):
        return None

    username = str(payload.get("username", ""))
    role = str(payload.get("role", ""))
    if role == "admin":
        return Identity(ADMIN_USERNAME, "admin") if username == ADMIN_USERNAME and has_admin() else None
    if role != "student":
        return None
    student_no = str(payload.get("student_no", ""))
    if not student_no or username != student_no:
        return None
    with connect(db_path) as connection:
        try:
            row = connection.execute(
                "SELECT must_change_password FROM students WHERE student_no = ?",
                (student_no,),
            ).fetchone()
        except sqlite3.Error:
            return None
    if row is None or bool(row["must_change_password"]):
        return None
    return Identity(student_no, "student", student_no, False)


def clear_session() -> None:
    try:
        session_path().unlink()
    except FileNotFoundError:
        pass


def _admin_config() -> dict[str, Any] | None:
    try:
        data = _read_json(admin_path())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("password_hash") or not data.get("session_secret"):
        return None
    return data


def _session_signature(payload: dict[str, Any]) -> str:
    config = _admin_config()
    if config is None:
        raise ValueError("管理员尚未初始化")
    key = bytes.fromhex(str(config["session_secret"]))
    message = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _resolved_db_path(db_path: Path | str | None) -> Path:
    path = Path(db_path) if db_path is not None else DB_PATH
    return path.expanduser().resolve()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"配置文件格式错误：{path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(path)
