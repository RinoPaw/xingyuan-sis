from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.auth import authenticate, change_password
from xingyuan_sis.bootstrap import DEFAULT_ADMIN_PASSWORD, ensure_default_state
from xingyuan_sis.service import XingyuanService


class DefaultStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "campus.db"
        self.home = patch.dict(os.environ, {"XINGYUAN_HOME": str(self.root / "auth")})
        self.home.start()
        self.addCleanup(self.home.stop)

    def test_first_launch_seeds_campus_and_creates_default_admin(self) -> None:
        ensure_default_state(self.db)

        self.assertEqual(len(XingyuanService(self.db).list_students()), 113)
        identity = authenticate(self.db, "Administrator", DEFAULT_ADMIN_PASSWORD)
        self.assertIsNotNone(identity)
        self.assertTrue(identity.is_admin)

    def test_repeated_launch_does_not_reset_existing_data_or_password(self) -> None:
        ensure_default_state(self.db)
        service = XingyuanService(self.db)
        service.create_announcement(title="保留我", body="已有数据", class_code="ELS2601")
        identity = authenticate(self.db, "Administrator", DEFAULT_ADMIN_PASSWORD)
        change_password(self.db, identity, "new-admin-password")

        ensure_default_state(self.db)

        self.assertIn("保留我", [row["title"] for row in service.list_announcements()])
        self.assertIsNone(authenticate(self.db, "Administrator", DEFAULT_ADMIN_PASSWORD))
        self.assertIsNotNone(authenticate(self.db, "Administrator", "new-admin-password"))


if __name__ == "__main__":
    unittest.main()
