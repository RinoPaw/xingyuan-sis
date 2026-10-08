from contextlib import nullcontext
from datetime import datetime
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
        self.assertNotIn("退出登录", text)
        self.assertIn("星原学生信息系统", text)
        self.assertIn("公告", text)
        self.assertIn("暂无公告", text)

    def test_menu_sections_have_unique_semantic_keys_and_own_their_labels(self) -> None:
        self.assertEqual(
            tuple(section.label for section in portal.SECTIONS),
            portal.PRIMARY_LABELS,
        )
        self.assertEqual(
            [section.key for section in portal.SECTIONS],
            ["home", "academics", "profile"],
        )
        self.assertEqual(
            len({section.key for section in portal.SECTIONS}),
            len(portal.SECTIONS),
        )
        self.assertEqual(
            [item.action for item in portal.secondary_items(Identity("Administrator", "admin"), 2)],
            ["profile-data", "profile-password", "logout"],
        )

    def test_portal_topbar_shows_live_date_and_time_without_sacrificing_database(self) -> None:
        identity = Identity("Administrator", "admin")
        now = datetime(2026, 9, 20, 14, 32)

        wide = screen._ANSI_RE.sub(
            "", portal._topbar(80, identity, "Administrator", "xingyuan.db", now)
        )
        narrower = screen._ANSI_RE.sub(
            "", portal._topbar(39, identity, "Administrator", "xingyuan.db", now)
        )
        narrowest = screen._ANSI_RE.sub(
            "", portal._topbar(32, identity, "Administrator", "xingyuan.db", now)
        )

        self.assertIn("09-20 周日 14:32", wide)
        self.assertIn("LOCAL  xingyuan.db", wide)
        self.assertIn("14:32", narrower)
        self.assertNotIn("周日", narrower)
        self.assertIn("LOCAL  xingyuan.db", narrower)
        self.assertNotIn("14:32", narrowest)
        self.assertIn("LOCAL  xingyuan.db", narrowest)

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

    def test_weak_context_never_competes_with_real_focus(self) -> None:
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ):
            os.environ.pop("NO_COLOR", None)
            weak_button = theme.button("学生", current=True)
            weak_nav = theme.nav_item("个人中心", current=True)
            strong = theme.button("学生", selected=True)
            marker = screen._ansi(">", theme.selection_marker_style())

        self.assertEqual(screen._TEXT_ON_SELECTED, screen._TEXT_PRIMARY)
        self.assertIn(screen._SURFACE_INTERACTIVE, weak_button)
        self.assertNotIn(screen._SURFACE_SELECTED, weak_button)
        self.assertNotIn(screen._TEXT_ACCENT, weak_button)
        self.assertIn(screen._TEXT_SECONDARY, weak_button)
        self.assertIn("[·学生 ]", screen._ANSI_RE.sub("", weak_button))

        self.assertNotIn(screen._SURFACE_SELECTED, weak_nav)
        self.assertNotIn(screen._SURFACE_INTERACTIVE, weak_nav)
        self.assertNotIn(screen._TEXT_ACCENT, weak_nav)
        self.assertIn(screen._TEXT_SECONDARY, weak_nav)
        self.assertEqual(screen._ANSI_RE.sub("", weak_nav).strip(), "· 个人中心")

        self.assertIn(screen._SURFACE_SELECTED, strong)
        self.assertIn(marker, strong)
        self.assertNotIn(screen._TEXT_ACCENT, strong.replace(marker, ""))
        self.assertIn("[>学生 ]", screen._ANSI_RE.sub("", strong))
        self.assertNotEqual(weak_button, strong)

    def test_portal_footer_has_one_core_contract_and_contextual_commands(self) -> None:
        identity = Identity("Administrator", "admin")
        states = (
            (0, "primary", {}),
            (1, "primary", {1: 0}),
            (1, "secondary", {1: 0}),
            (2, "primary", {2: 0}),
            (2, "secondary", {2: 0}),
        )
        footers: list[str] = []
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((100, 24))):
            for selected, focus, secondary in states:
                frame = portal.frame(identity, selected, focus, secondary, {}, 0, animate=False)
                footer = screen._ANSI_RE.sub("", frame.lines[-1])
                footers.append(footer)
                self.assertIn("Tab 下一项", footer)
                self.assertIn("方向键 移动", footer)
                self.assertIn("Enter 打开", footer)
                self.assertIn("Esc 返回", footer)
                self.assertFalse(any(region.y == 24 for region in frame.regions))

        self.assertIn("P 动画", footers[0])
        self.assertTrue(all("P 动画" not in footer for footer in footers[1:]))

    def test_portal_navigation_separates_focus_from_selection(self) -> None:
        for identity in (
            Identity("Administrator", "admin"),
            Identity("20260001", "student", "20260001"),
        ):
            with self.subTest(role=identity.role):
                navigate = lambda selected, focus, secondary, key: portal.navigate(
                    identity, selected, focus, secondary, key, 2
                )
                self.assertEqual(navigate(0, "primary", 0, "focus"), (1, "primary", 0))
                self.assertEqual(navigate(1, "primary", 0, "focus"), (2, "primary", 0))
                self.assertEqual(navigate(2, "primary", 0, "focus"), (0, "primary", 0))
                self.assertEqual(navigate(1, "primary", 1, "select"), (1, "secondary", 1))
                self.assertEqual(navigate(1, "primary", 1, "right"), (1, "secondary", 1))
                for parent in (1, 2):
                    total = len(portal.secondary_items(identity, parent))
                    for index in range(total):
                        self.assertEqual(
                            navigate(parent, "secondary", index, "focus"),
                            (parent, "secondary", (index + 1) % total),
                        )
                self.assertEqual(navigate(1, "secondary", 1, "back"), (1, "primary", 1))
                self.assertEqual(navigate(1, "secondary", 1, "back"), (1, "primary", 1))
                self.assertEqual(navigate(1, "primary", 1, "down"), (2, "primary", 1))
                self.assertEqual(navigate(1, "secondary", 0, "right"), (1, "secondary", 1))

    def test_portal_state_machine_preserves_menu_level_invariants(self) -> None:
        identities = (
            Identity("Administrator", "admin"),
            Identity("20260001", "student", "20260001"),
        )
        keys = (
            "focus", "up", "down", "left", "right", "home", "end",
            "select", "back", "1", "2", "3",
        )
        for identity in identities:
            for width, height in ((100, 24), (26, 18)):
                columns = portal.secondary_columns(width - 1, height=height)
                for primary in range(len(portal.PRIMARY_LABELS)):
                    items = portal.secondary_items(identity, primary)
                    for focus in (("primary", "secondary") if items else ("primary",)):
                        for index in range(len(items) if focus == "secondary" else 1):
                            for key in keys:
                                with self.subTest(
                                    role=identity.role, width=width, primary=primary,
                                    focus=focus, index=index, key=key,
                                ):
                                    next_primary, next_focus, next_secondary = portal.navigate(
                                        identity, primary, focus, index, key, columns,
                                    )
                                    self.assertIn(next_primary, range(len(portal.PRIMARY_LABELS)))
                                    self.assertIn(next_focus, ("primary", "secondary"))
                                    if next_focus == "secondary":
                                        next_items = portal.secondary_items(identity, next_primary)
                                        self.assertTrue(next_items)
                                        self.assertIn(next_secondary, range(len(next_items)))
                                    if key == "focus":
                                        self.assertEqual(next_focus, focus)
                                        if focus == "primary":
                                            self.assertEqual(
                                                next_primary,
                                                (primary + 1) % len(portal.PRIMARY_LABELS),
                                            )
                                        else:
                                            self.assertEqual(next_primary, primary)
                                            self.assertEqual(next_secondary, (index + 1) % len(items))
                                    if key == "back" and focus == "secondary":
                                        self.assertEqual((next_primary, next_focus), (primary, "primary"))

    def test_portal_tab_is_processed_by_event_loop(self) -> None:
        identity = Identity("Administrator", "admin")
        preferences: dict[str, object] = {
            "identity": identity,
            "portal_selected": 0,
            "portal_focus": "primary",
            "animate": False,
        }
        with patch("xingyuan_sis.service.XingyuanService") as service_type, \
             patch.object(app.screen, "_clear"), patch.object(app.screen, "_paint"), \
             patch.object(app.screen, "_terminal_size", return_value=os.terminal_size((100, 24))), \
             patch.object(app.keys, "_mouse_tracking", return_value=nullcontext()), \
             patch.object(app.keys, "_read_key", side_effect=["focus", "focus", "focus", "back"]):
            service_type.return_value.stats.return_value = {}
            service_type.return_value.list_announcements.return_value = []
            self.assertIsNone(app._portal_home(None, selected=0, preferences=preferences))
        self.assertEqual(preferences["portal_selected"], 0)
        self.assertEqual(preferences["portal_focus"], "primary")
        self.assertEqual(preferences["portal_secondary"].get(1, 0), 0)

    def test_portal_tab_selects_next_secondary_item_without_leaving_menu(self) -> None:
        for identity in (
            Identity("Administrator", "admin"),
            Identity("20260001", "student", "20260001"),
        ):
            items = portal.secondary_items(identity, 1)
            for initial in (0, len(items) - 1):
                with self.subTest(role=identity.role, initial=initial):
                    preferences: dict[str, object] = {
                        "identity": identity,
                        "portal_selected": 1,
                        "portal_focus": "primary",
                        "portal_secondary": {1: initial},
                        "animate": False,
                    }
                    with patch("xingyuan_sis.service.XingyuanService") as service_type, \
                         patch.object(app.screen, "_clear"), patch.object(app.screen, "_paint"), \
                         patch.object(app.screen, "_terminal_size", return_value=os.terminal_size((100, 24))), \
                         patch.object(app.keys, "_mouse_tracking", return_value=nullcontext()), \
                         patch.object(app.keys, "_read_key", side_effect=["select", "focus", "select"]):
                        service_type.return_value.stats.return_value = {}
                        service_type.return_value.list_announcements.return_value = []
                        result = app._portal_home(None, selected=1, preferences=preferences)
                    expected = (initial + 1) % len(items)
                    self.assertEqual(result, items[expected].action)
                    self.assertEqual(preferences["portal_selected"], 1)
                    self.assertEqual(preferences["portal_focus"], "secondary")
                    self.assertEqual(preferences["portal_secondary"][1], expected)

    def test_portal_escape_from_secondary_returns_to_parent(self) -> None:
        identity = Identity("Administrator", "admin")
        preferences: dict[str, object] = {
            "identity": identity,
            "portal_selected": 1,
            "portal_focus": "primary",
            "portal_secondary": {1: 2},
            "animate": False,
        }
        with patch("xingyuan_sis.service.XingyuanService") as service_type, \
             patch.object(app.screen, "_clear"), patch.object(app.screen, "_paint"), \
             patch.object(app.screen, "_terminal_size", return_value=os.terminal_size((100, 24))), \
             patch.object(app.keys, "_mouse_tracking", return_value=nullcontext()), \
             patch.object(app.keys, "_read_key", side_effect=["select", "focus", "back", "back"]):
            service_type.return_value.stats.return_value = {}
            service_type.return_value.list_announcements.return_value = []
            self.assertIsNone(app._portal_home(None, selected=1, preferences=preferences))
        self.assertEqual(preferences["portal_selected"], 1)
        self.assertEqual(preferences["portal_focus"], "primary")
        self.assertEqual(preferences["portal_secondary"][1], 3)

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

    def test_logout_is_a_profile_action_for_both_roles(self) -> None:
        for identity in (
            Identity("Administrator", "admin"),
            Identity("20260001", "student", "20260001"),
        ):
            with self.subTest(role=identity.role):
                items = portal.secondary_items(identity, 2)
                self.assertEqual(items[-1], portal.MenuItem("退出登录", "logout"))
                preferences: dict[str, object] = {
                    "identity": identity,
                    "portal_selected": 2,
                    "portal_focus": "primary",
                    "portal_secondary": {2: len(items) - 1},
                    "animate": False,
                }
                with patch("xingyuan_sis.service.XingyuanService") as service_type, \
                     patch.object(app.screen, "_clear"), patch.object(app.screen, "_paint"), \
                     patch.object(app.screen, "_terminal_size", return_value=os.terminal_size((100, 24))), \
                     patch.object(app.keys, "_mouse_tracking", return_value=nullcontext()), \
                     patch.object(app.keys, "_read_key", side_effect=["select", "select"]):
                    service_type.return_value.stats.return_value = {}
                    service_type.return_value.list_announcements.return_value = []
                    self.assertEqual(
                        app._portal_home(None, selected=2, preferences=preferences),
                        "logout",
                    )
                self.assertEqual(preferences["portal_selected"], 2)
                self.assertEqual(preferences["portal_focus"], "secondary")

    def test_profile_logout_is_visible_and_clickable_in_wide_and_narrow_layouts(self) -> None:
        identity = Identity("Administrator", "admin")
        for size in ((100, 24), (26, 18)):
            with self.subTest(size=size), \
                 patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
                frame = portal.frame(identity, 2, "secondary", {2: 2}, {}, 0, animate=False)
                text = "\n".join(screen._ANSI_RE.sub("", line) for line in frame.lines)
                self.assertIn("退出登录", text)
                self.assertTrue(any(region.action == "secondary:2" for region in frame.regions))

    def test_profile_logout_mouse_uses_same_action_in_wide_and_narrow_layouts(self) -> None:
        for identity in (
            Identity("Administrator", "admin"),
            Identity("20260001", "student", "20260001"),
        ):
            for size in ((100, 24), (26, 18)):
                focus = "primary" if size[0] >= portal.NARROW_WIDTH else "secondary"
                with self.subTest(role=identity.role, size=size):
                    preferences: dict[str, object] = {
                        "identity": identity,
                        "portal_selected": 2,
                        "portal_focus": focus,
                        "portal_secondary": {2: 2},
                        "animate": False,
                    }
                    with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
                        frame = portal.frame(identity, 2, focus, {2: 2}, {}, 0, animate=False)
                    region = next(r for r in frame.regions if r.action == "secondary:2")
                    with patch("xingyuan_sis.service.XingyuanService") as service_type, \
                         patch.object(app.screen, "_clear"), patch.object(app.screen, "_paint"), \
                         patch.object(app.screen, "_terminal_size", return_value=os.terminal_size(size)), \
                         patch.object(app.keys, "_mouse_tracking", return_value=nullcontext()), \
                         patch.object(app.keys, "_read_key", return_value=screen.MouseClick(region.x, region.y)):
                        service_type.return_value.stats.return_value = {}
                        service_type.return_value.list_announcements.return_value = []
                        self.assertEqual(
                            app._portal_home(None, selected=2, preferences=preferences),
                            "logout",
                        )

    def test_keyboard_and_mouse_activation_preserve_the_same_menu_context(self) -> None:
        for identity in (
            Identity("Administrator", "admin"),
            Identity("20260001", "student", "20260001"),
        ):
            for size in ((100, 24), (26, 18)):
                with self.subTest(role=identity.role, size=size):
                    selections = []
                    for mouse in (False, True):
                        preferences: dict[str, object] = {
                            "identity": identity,
                            "portal_selected": 2,
                            "portal_focus": "secondary",
                            "portal_secondary": {2: 0},
                            "animate": False,
                        }
                        sequence = ["end", "select"]
                        if mouse:
                            with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
                                frame = portal.frame(
                                    identity, 2, "secondary", {2: 0}, {}, 0, animate=False
                                )
                            target = next(
                                region for region in frame.regions
                                if region.action == "secondary:2"
                            )
                            sequence = [screen.MouseClick(target.x, target.y)]
                        with patch("xingyuan_sis.service.XingyuanService") as service_type, \
                             patch.object(app.screen, "_clear"), patch.object(app.screen, "_paint"), \
                             patch.object(app.screen, "_terminal_size", return_value=os.terminal_size(size)), \
                             patch.object(app.keys, "_mouse_tracking", return_value=nullcontext()), \
                             patch.object(app.keys, "_read_key", side_effect=sequence):
                            service_type.return_value.stats.return_value = {}
                            service_type.return_value.list_announcements.return_value = []
                            action = app._portal_home(None, selected=2, preferences=preferences)
                        selections.append((
                            action,
                            preferences["portal_selected"],
                            preferences["portal_focus"],
                            preferences["portal_secondary"][2],
                        ))
                    self.assertEqual(selections, [
                        ("logout", 2, "secondary", 2),
                        ("logout", 2, "secondary", 2),
                    ])

    def test_clicking_parent_does_not_activate_selected_child(self) -> None:
        identity = Identity("Administrator", "admin")
        size = (100, 24)
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            frame = portal.frame(identity, 2, "secondary", {2: 2}, {}, 0, animate=False)
        parent = next(region for region in frame.regions if region.action == "primary:2")
        preferences: dict[str, object] = {
            "identity": identity,
            "portal_selected": 2,
            "portal_focus": "secondary",
            "portal_secondary": {2: 2},
            "animate": False,
        }
        with patch("xingyuan_sis.service.XingyuanService") as service_type, \
             patch.object(app.screen, "_clear"), patch.object(app.screen, "_paint"), \
             patch.object(app.screen, "_terminal_size", return_value=os.terminal_size(size)), \
             patch.object(app.keys, "_mouse_tracking", return_value=nullcontext()), \
             patch.object(app.keys, "_read_key",
                          side_effect=[screen.MouseClick(parent.x, parent.y), "back"]):
            service_type.return_value.stats.return_value = {}
            service_type.return_value.list_announcements.return_value = []
            self.assertIsNone(app._portal_home(None, selected=2, preferences=preferences))
        self.assertEqual(preferences["portal_selected"], 2)
        self.assertEqual(preferences["portal_focus"], "primary")
        self.assertEqual(preferences["portal_secondary"][2], 2)

    def test_mouse_clicking_another_primary_menu_preserves_navigation(self) -> None:
        identity = Identity("Administrator", "admin")
        size = (100, 24)
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            frame = portal.frame(identity, 2, "secondary", {2: 2}, {}, 0, animate=False)
        target = next(region for region in frame.regions if region.action == "primary:1")
        preferences: dict[str, object] = {
            "identity": identity,
            "portal_selected": 2,
            "portal_focus": "secondary",
            "portal_secondary": {2: 2},
            "animate": False,
        }
        with patch("xingyuan_sis.service.XingyuanService") as service_type, \
             patch.object(app.screen, "_clear"), patch.object(app.screen, "_paint"), \
             patch.object(app.screen, "_terminal_size", return_value=os.terminal_size(size)), \
             patch.object(app.keys, "_mouse_tracking", return_value=nullcontext()), \
             patch.object(app.keys, "_read_key",
                          side_effect=[screen.MouseClick(target.x, target.y), "back"]):
            service_type.return_value.stats.return_value = {}
            service_type.return_value.list_announcements.return_value = []
            self.assertIsNone(app._portal_home(None, selected=2, preferences=preferences))
        self.assertEqual(preferences["portal_selected"], 1)
        self.assertEqual(preferences["portal_focus"], "primary")

    def test_logout_action_clears_session_and_resets_portal_navigation(self) -> None:
        identity = Identity("Administrator", "admin")
        calls = []

        def portal_session(db_path, *, selected, preferences):
            calls.append((selected, dict(preferences)))
            if len(calls) == 1:
                preferences["identity"] = identity
                preferences["portal_selected"] = 2
                preferences["portal_focus"] = "secondary"
                preferences["portal_secondary"] = {1: 7, 2: 2}
                return "logout"
            self.assertNotIn("identity", preferences)
            self.assertNotIn("portal_secondary", preferences)
            self.assertEqual(preferences["portal_selected"], 0)
            self.assertEqual(preferences["portal_focus"], "primary")
            return None

        with patch("sys.stdin.isatty", return_value=True), \
             patch("sys.stdout.isatty", return_value=True), \
             patch.object(app.screen, "_terminal_session", return_value=nullcontext()), \
             patch.object(app.screen, "_clear"), \
             patch.object(app, "_portal_home", side_effect=portal_session), \
             patch.object(app, "clear_session") as clear:
            app.run()

        clear.assert_called_once_with()
        self.assertEqual(len(calls), 2)

    def test_breadcrumb_navigation_resolves_parent_from_menu_sections(self) -> None:
        identity = Identity("Administrator", "admin")
        for path, target in (
            ("", 0),
            ("教务", 1),
            ("教务 / 班级", 1),
            ("个人中心 / 个人数据", 2),
            ("不存在的菜单", 0),
        ):
            calls = []

            def portal_session(db_path, *, selected, preferences):
                calls.append(selected)
                if len(calls) == 1:
                    preferences["identity"] = identity
                    preferences["portal_selected"] = 2
                    preferences["portal_focus"] = "secondary"
                    return "profile-data"
                self.assertEqual(preferences["portal_selected"], target)
                self.assertEqual(preferences["portal_focus"], "primary")
                return None

            with self.subTest(path=path), \
                 patch("sys.stdin.isatty", return_value=True), \
                 patch("sys.stdout.isatty", return_value=True), \
                 patch.object(app.screen, "_terminal_session", return_value=nullcontext()), \
                 patch.object(app, "_portal_home", side_effect=portal_session), \
                 patch.object(app, "_execute_portal_action", side_effect=screen.NavigateTo(path)):
                app.run()

            self.assertEqual(len(calls), 2)

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
        self.assertEqual(portal.PRIMARY_LABELS, ("首页", "教务", "个人中心"))
        self.assertGreater(len(portal.secondary_items(admin, 1)), 1)
        self.assertEqual(
            [item.label for item in portal.secondary_items(student, 1)],
            ["学生查询", "班级公告"],
        )
        self.assertEqual(
            [item.label for item in portal.secondary_items(student, 2)],
            ["个人数据", "修改密码", "退出登录"],
        )


if __name__ == "__main__":
    unittest.main()
