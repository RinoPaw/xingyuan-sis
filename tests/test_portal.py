from contextlib import nullcontext
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.auth import Identity
from xingyuan_sis.tui import app, portal, screen, theme


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

    def test_wide_academic_menu_caps_at_four_columns(self) -> None:
        self.assertEqual(portal.secondary_columns(99, "secondary", height=24), 4)

    def test_secondary_focus_uses_shared_selection_language(self) -> None:
        identity = Identity("Administrator", "admin")
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((100, 24))):
            os.environ.pop("NO_COLOR", None)
            preview = portal.frame(identity, 1, "primary", {1: 0}, {}, 0, animate=False)
            entered = portal.frame(identity, 1, "secondary", {1: 0}, {}, 0, animate=False)

        preview_raw = "\n".join(preview.lines)
        entered_raw = "\n".join(entered.lines)
        preview_text = screen._ANSI_RE.sub("", preview_raw)
        entered_text = screen._ANSI_RE.sub("", entered_raw)
        self.assertIn("学生", preview_text)
        self.assertIn("> 学生", entered_text)
        self.assertNotIn("[ 学生 ]", preview_text)
        self.assertNotIn("[ 学生 ]", entered_text)
        self.assertNotIn("\x1b[4m", entered_raw)
        self.assertIn(screen._SURFACE_INTERACTIVE, preview_raw)
        self.assertIn(screen._SURFACE_SELECTED, entered_raw)
        self.assertIn(screen._TEXT_ACCENT, entered_raw)

    def test_primary_keeps_weak_selection_when_focus_enters_secondary(self) -> None:
        identity = Identity("Administrator", "admin")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((100, 24))):
            primary = portal.frame(identity, 1, "primary", {1: 0}, {}, 0, animate=False)
            secondary = portal.frame(identity, 1, "secondary", {1: 0}, {}, 0, animate=False)

        primary_row = screen._ANSI_RE.sub("", primary.lines[3])
        secondary_row = screen._ANSI_RE.sub("", secondary.lines[3])
        self.assertTrue(primary_row.startswith("> 教务"))
        self.assertTrue(secondary_row.startswith("· 教务"))

    def test_buttons_distinguish_current_context_from_keyboard_focus(self) -> None:
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            weak = theme.button("学生", current=True)
            strong = theme.button("学生", selected=True)
            marker = screen._ansi(">", theme.selection_marker_style())
        self.assertEqual(screen._TEXT_ON_SELECTED, screen._TEXT_PRIMARY)
        self.assertIn(screen._SURFACE_INTERACTIVE, weak)
        self.assertIn(screen._TEXT_ACCENT, weak)
        self.assertIn("[·学生 ]", screen._ANSI_RE.sub("", weak))
        self.assertNotIn(screen._SURFACE_SELECTED, weak)
        self.assertIn(screen._SURFACE_SELECTED, strong)
        self.assertIn(marker, strong)
        self.assertNotIn(screen._TEXT_ACCENT, strong.replace(marker, ""))
        self.assertIn("[>学生 ]", screen._ANSI_RE.sub("", strong))
        self.assertNotEqual(weak, strong)

    def test_portal_footer_has_one_core_contract_and_contextual_commands(self) -> None:
        identity = Identity("Administrator", "admin")
        states = (
            (0, "primary", {}),
            (1, "primary", {1: 0}),
            (1, "secondary", {1: 0}),
            (2, "primary", {2: 0}),
            (2, "secondary", {2: 0}),
            (3, "primary", {}),
        )
        footers: list[str] = []
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((100, 24))):
            for selected, focus, secondary in states:
                frame = portal.frame(identity, selected, focus, secondary, {}, 0, animate=False)
                footer = screen._ANSI_RE.sub("", frame.lines[-1])
                footers.append(footer)
                self.assertIn("方向键 移动", footer)
                self.assertIn("Enter 打开", footer)
                self.assertIn("Esc 返回", footer)
                self.assertFalse(any(region.y == 24 for region in frame.regions))

        self.assertIn("P 动画", footers[0])
        self.assertTrue(all("P 动画" not in footer for footer in footers[1:]))

    def test_home_animation_shortcut_is_resolved_in_portal_context(self) -> None:
        identity = Identity("Administrator", "admin")
        preferences: dict[str, object] = {
            "identity": identity,
            "portal_selected": 0,
            "portal_focus": "primary",
            "animate": True,
        }
        with patch("xingyuan_sis.service.XingyuanService") as service_type, \
             patch.object(app.screen, "_clear"), patch.object(app.screen, "_paint"), \
             patch.object(app.screen, "_terminal_size", return_value=os.terminal_size((100, 24))), \
             patch.object(app.keys, "_mouse_tracking", return_value=nullcontext()), \
             patch.object(app.keys, "_read_key", side_effect=["p", "back"]):
            service_type.return_value.stats.return_value = {}
            service_type.return_value.list_announcements.return_value = []
            self.assertIsNone(app._portal_home(None, selected=0, preferences=preferences))
        self.assertFalse(preferences["animate"])

    def test_logout_is_an_explicit_action_not_a_right_arrow_destination(self) -> None:
        identity = Identity("Administrator", "admin")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((100, 24))):
            frame = portal.frame(identity, 3, "primary", {}, {}, 0, animate=False)
        text = "\n".join(screen._ANSI_RE.sub("", line) for line in frame.lines)
        self.assertIn("Enter 退出当前账户", text)
        self.assertNotIn("→ 退出当前账户", text)

        preferences: dict[str, object] = {
            "identity": identity,
            "portal_selected": 3,
            "portal_focus": "primary",
            "animate": False,
        }
        with patch("xingyuan_sis.service.XingyuanService") as service_type, \
             patch.object(app.screen, "_clear"), \
             patch.object(app.screen, "_paint"), \
             patch.object(app.screen, "_terminal_size", return_value=os.terminal_size((100, 24))), \
             patch.object(app.keys, "_mouse_tracking", return_value=nullcontext()), \
             patch.object(app.keys, "_read_key", side_effect=["right", "back"]) as read_key:
            service_type.return_value.stats.return_value = {}
            service_type.return_value.list_announcements.return_value = []
            self.assertIsNone(app._portal_home(None, selected=3, preferences=preferences))
        self.assertEqual(read_key.call_count, 2)

    def test_extreme_narrow_width_hides_preview_but_entered_menu_still_renders(self) -> None:
        identity = Identity("Administrator", "admin")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((26, 18))):
            preview = portal.frame(identity, 1, "primary", {1: 0}, {}, 0, animate=False)
            entered = portal.frame(identity, 1, "secondary", {1: 0}, {}, 0, animate=False)

        preview_text = "\n".join(preview.lines)
        entered_text = "\n".join(entered.lines)
        self.assertIn("教务", preview_text)
        self.assertNotIn("学院", preview_text)
        self.assertIn("Enter 进入", preview_text)
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
            ["学生查询", "班级公告"],
        )
        self.assertEqual(
            [item.label for item in portal.secondary_items(student, 2)],
            ["个人数据", "修改密码"],
        )


if __name__ == "__main__":
    unittest.main()
