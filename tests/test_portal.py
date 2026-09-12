import os
import unittest
from unittest.mock import patch

from xingyuan_sis.auth import Identity
from xingyuan_sis.tui import portal, screen


class PortalLayoutTests(unittest.TestCase):
    def test_logged_in_home_defaults_to_home_content(self) -> None:
        identity = Identity("Administrator", "admin")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((100, 24))):
            frame = portal.frame(identity, 0, "primary", {}, {}, 0, animate=False)
        text = "\n".join(frame.lines)
        self.assertIn("首页", text)
        self.assertIn("教务", text)
        self.assertIn("个人中心", text)
        self.assertIn("退出登录", text)
        self.assertIn("星原学生信息系统", text)
        self.assertIn("公告", text)
        self.assertIn("暂无公告", text)

    def test_academic_preview_is_visible_when_width_allows(self) -> None:
        identity = Identity("Administrator", "admin")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((100, 24))):
            frame = portal.frame(identity, 1, "primary", {1: 0}, {}, 0, animate=False)
        text = "\n".join(frame.lines)
        for label in ("学生", "学院", "专业", "班级", "课程", "成绩", "数据"):
            self.assertIn(label, text)
        self.assertTrue(any(region.action.startswith("secondary:") for region in frame.regions))

    def test_extreme_narrow_width_hides_preview_but_entered_menu_still_renders(self) -> None:
        identity = Identity("Administrator", "admin")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((26, 18))):
            preview = portal.frame(identity, 1, "primary", {1: 0}, {}, 0, animate=False)
            entered = portal.frame(identity, 1, "secondary", {1: 0}, {}, 0, animate=False)

        preview_text = "\n".join(preview.lines)
        entered_text = "\n".join(entered.lines)
        self.assertIn("教务", preview_text)
        self.assertNotIn("学院", preview_text)
        self.assertIn("Enter / Space / → 进入", preview_text)
        self.assertIn("学生", entered_text)
        self.assertIn("学院", entered_text)
        self.assertIn("成绩", entered_text)

    def test_student_and_admin_share_primary_navigation_but_not_admin_operations(self) -> None:
        admin = Identity("Administrator", "admin")
        student = Identity("20260001", "student", "20260001")
        self.assertEqual(portal.PRIMARY_LABELS, ("首页", "教务", "个人中心", "退出登录"))
        self.assertGreater(len(portal.secondary_items(admin, 1)), 1)
        self.assertEqual(
            [item.label for item in portal.secondary_items(student, 1)],
            ["学生查询"],
        )
        self.assertEqual(
            [item.label for item in portal.secondary_items(student, 2)],
            ["个人数据", "修改密码"],
        )


if __name__ == "__main__":
    unittest.main()
