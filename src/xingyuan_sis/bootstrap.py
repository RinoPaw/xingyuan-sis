from __future__ import annotations

from pathlib import Path

from .auth import has_admin, initialize_admin
from .database import initialize_database
from .service import XingyuanService

DEFAULT_ADMIN_PASSWORD = "12345678"


def ensure_default_state(db_path: Path | str | None = None) -> None:
    """Prepare a usable campus on first launch without resetting existing data."""
    initialize_database(db_path)
    service = XingyuanService(db_path)
    if not service.list_students():
        service.seed_demo()
    if not has_admin():
        initialize_admin(DEFAULT_ADMIN_PASSWORD)


__all__ = ["DEFAULT_ADMIN_PASSWORD", "ensure_default_state"]
