from contextlib import nullcontext, redirect_stdout
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import ENROLLMENTS, STUDENTS, seed_demo
from xingyuan_sis.tui import app, keys, screen, workspace
from xingyuan_sis.tui.workspace import events as workspace_events
from xingyuan_sis.tui.workspace import field_session as workspace_field
from xingyuan_sis.tui.workspace import forms as workspace_forms, view as workspace_view
from xingyuan_sis.tui.workspace.data import COLLECTIONS, Catalog


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)

    def render(self, state, size=(120, 35)):
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size(size)):
            return workspace_view.render(state, self.catalog)

    def interact(self, state, events):
        with patch.object(keys, "_read_key", side_effect=events), patch.object(screen, "_paint"), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            return workspace_events.interact(state, self.catalog)

    @staticmethod
    def inspector_state(collection: str, **kwargs):
        return workspace.Workspace(
            collection,
            focus=workspace.FocusArea.INSPECTOR,
            content_panel=workspace.ContentPanel.INSPECTOR,
            **kwargs,
        )

    def test_all_pages_fit_and_click_regions_match_visible_content(self):
        for collection in (*COLLECTIONS, "data"):
            for size in ((160, 46), (120, 35), (80, 24), (40, 20), (30, 12), (18, 8)):
                with self.subTest(collection=collection, size=size):
                    frame = self.render(workspace.Workspace(collection), size)
                    self.assertEqual(len(frame.lines), size[1])
                    self.assertTrue(all(screen._display_width(line) == size[0] - 1 for line in frame.lines))
                    for region in frame.regions:
                        self.assertLessEqual(region.x + region.width, size[0])
                        self.assertLessEqual(region.y, size[1])
                        if region.action != "focus-details":
                            self.assertEqual(
                                screen._hit_action(keys.MouseClick(region.x, region.y), frame.regions),
                                region.action,
                            )

    def test_student_workspace_header_has_no_ghost_rows(self):
        plain = [screen._ANSI_RE.sub("", line) for line in self.render(workspace.Workspace("students")).lines]
        self.assertIn("搜索", plain[3])
        self.assertTrue(plain[4].lstrip().startswith("─"))
        self.assertIn("名册", plain[5])
        self.assertIn("档案", plain[5])
        self.assertNotIn("学生档案", "\n".join(plain[:6]))

    def test_wheel_scrolls_panel_under_pointer(self):
        state = workspace.Workspace("students")
        size = (120, 24)
        frame = self.render(state, size)
        detail_region = next(region for region in frame.regions if region.action == "focus-details")
        right_wheel = keys.MouseScroll(detail_region.x, min(detail_region.y, 12), "down")
        with patch.object(keys, "_read_key", side_effect=[right_wheel, "back"]), \
             patch.object(screen, "_paint"), patch.object(
                 screen, "_terminal_size", return_value=os.terminal_size(size)
             ):
            workspace_events.interact(state, self.catalog)
        self.assertEqual(state.selected, 0)
        self.interact(state, [keys.MouseScroll(2, 12, "down"), "back"])
        self.assertEqual(state.selected, 1)

    def test_selection_updates_profile_without_query_or_enter(self):
        state = workspace.Workspace("students")
        first = self.render(state)
        expected = self.catalog.records["students"][1]
        second_row = next(r for r in first.regions if r.action == "row:1")
        with patch.object(keys, "_read_key", side_effect=[keys.MouseClick(second_row.x, second_row.y), "refresh"]), \
             patch.object(screen, "_paint"), patch.object(
                 screen, "_terminal_size", return_value=os.terminal_size((120, 35))
             ):
            workspace_events.interact(state, self.catalog)
        self.assertEqual(state.current(self.catalog)["name"], expected["name"])

    def test_related_record_return_preserves_roster_position(self):
        state = workspace.Workspace("students", query="元素", selected=1)
        original = state.current(self.catalog)
        related_key, related = self.catalog.related(state.key, original)
        self.interact(state, [f"related:{related_key}:{related[0]['id']}", "back", "refresh"])
        self.assertEqual((state.key, state.query, state.selected), ("students", "元素", 1))
        self.assertEqual(state.current(self.catalog)["id"], original["id"])

    def test_keyboard_search_uses_current_seed_data(self):
        state = workspace.Workspace("students")
        expected = STUDENTS[0]
        with patch("builtins.input", return_value=str(expected[1])), \
             patch.object(screen, "_paint"), redirect_stdout(StringIO()):
            workspace_forms.read_search(state, self.catalog)
        self.assertEqual([row["student_no"] for row in state.rows(self.catalog)], [str(expected[0])])

    def test_field_session_saves_freeform_value_without_record_form(self):
        state = self.inspector_state("students")
        original = state.current(self.catalog).copy()
        workspace_field.start(state, self.catalog, "contact")
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))), \
             patch.object(screen, "_paint"), \
             patch.object(workspace_field, "read_inline_input", return_value="即时新联系方式"):
            workspace_field.edit_current(state, self.catalog)
        self.assertIsNone(state.field_session)
        self.assertIsNone(state.form)
        self.assertEqual(self.catalog.service.student_by_no(original["student_no"])["contact"], "即时新联系方式")

    def test_student_identity_fields_are_focusable_but_read_only(self):
        state = self.inspector_state("students")
        actions = {region.action for region in self.render(state).regions}
        self.assertIn("field:name", actions)
        self.assertIn("field:student_no", actions)
        for field in ("name", "student_no"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "只读"):
                workspace_field.start(state, self.catalog, field)

    def test_course_edit_renames_code_without_changing_enrollments(self):
        row = self.catalog.records["courses"][0]
        before = len(self.catalog.service.enrollments_for_course(row["course_code"]))
        self.catalog.save("courses", {"course_code": "NEW101"}, row)
        self.assertEqual(self.catalog.service.course_by_code("NEW101")["id"], row["id"])
        self.assertEqual(len(self.catalog.service.enrollments_for_course("NEW101")), before)

    def test_zero_score_and_clearing_score_are_distinct(self):
        state = self.inspector_state("grades", view=1)
        original = state.current(self.catalog).copy()
        workspace_field.start(state, self.catalog, "score")
        state.field_session.values["score"] = 0
        workspace_field.commit(state, self.catalog)
        row = next(r for r in self.catalog.records["grades"] if r["id"] == original["id"])
        self.assertEqual(row["score"], 0)
        self.assertIn("不符合当前筛选", state.notice)
        self.catalog.save("grades", {"score": None}, row)
        self.assertIsNone(next(r for r in self.catalog.records["grades"] if r["id"] == row["id"])["score"])

    def test_invalid_values_do_not_write(self):
        row = self.catalog.records["grades"][0]
        for score in ("nan", "inf", "101", "-1", "不合法"):
            with self.subTest(score=score), self.assertRaises(ValueError):
                self.catalog.save("grades", {"score": score}, row)

    def test_class_picker_saves_major_and_local_number_as_one_relationship(self):
        state = self.inspector_state("students", selected=9)
        original = state.current(self.catalog).copy()
        workspace_field.start(state, self.catalog, "major_code")
        workspace_field.edit_current(state, self.catalog)
        major_index = next(
            i for i, (value, _) in enumerate(state.field_session.options)
            if value not in {None, original["major_code"]}
        )
        selected_major = state.field_session.options[major_index][0]
        workspace_field.accept_option(state, self.catalog, major_index)
        self.assertEqual(state.field_session.active_key, "class_number")
        selected_number = state.field_session.options[0][0]
        workspace_field.accept_option(state, self.catalog, 0)

        changed = self.catalog.service.student_by_no(original["student_no"])
        expected = next(
            row for row in self.catalog.records["classes"]
            if row["major_code"] == selected_major
            and self.catalog.class_numbers[row["id"]] == selected_number
        )
        self.assertEqual(changed["class_id"], expected["id"])

    def test_create_and_remove_record_refresh_workspace(self):
        state = workspace.Workspace("departments")
        workspace_forms.open_form(state, self.catalog, "create")
        state.form.values.update(code="NEW", name="新学院")
        workspace_forms.apply_form(state, self.catalog)
        self.assertEqual(state.current(self.catalog)["code"], "NEW")
        workspace_forms.open_form(state, self.catalog, "delete")
        workspace_forms.apply_form(state, self.catalog)
        self.assertIsNone(self.catalog.service.department_by_code("NEW"))

    def test_active_field_target_stays_visible_after_resize_without_save_button(self):
        state = self.inspector_state("students")
        workspace_field.start(state, self.catalog, "notes")
        for size in ((120, 35), (80, 24), (40, 20), (30, 12)):
            with self.subTest(size=size):
                frame = self.render(state, size)
                self.assertIn("备注", "".join(frame.lines))
                self.assertTrue(any(r.action == "field:notes" for r in frame.regions))
                self.assertFalse(any(r.action == "save" for r in frame.regions))

    def test_short_workspace_keeps_every_record_accessible(self):
        state = workspace.Workspace("students")
        expected_name = self.catalog.records["students"][-1]["name"]
        with patch.object(keys, "_read_key", side_effect=["end", "refresh"]), \
             patch.object(screen, "_paint") as paint, patch.object(
                 screen, "_terminal_size", return_value=os.terminal_size((30, 12))
             ):
            workspace_events.interact(state, self.catalog)
        self.assertEqual(state.selected, len(self.catalog.records["students"]) - 1)
        self.assertIn(expected_name, "".join(paint.call_args_list[-1].args[0]))

    def test_breadcrumb_returns_home_after_resizing_academic_workspace(self):
        identity = app.Identity("Administrator", "admin")
        events = ["2", "right", "right", "right", "right", "select", keys.MouseClick(2, 2), "back"]
        with redirect_stdout(StringIO()), patch.object(keys, "_read_key", side_effect=events), \
             patch.object(app, "read_session", return_value=identity), patch.object(screen, "_paint") as paint, \
             patch.object(screen, "_clear"), patch.object(keys, "_mouse_tracking", nullcontext), \
             patch.object(screen, "_terminal_session", nullcontext), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 24))), \
             patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True):
            app.run(self.db)
        frames = [screen._ANSI_RE.sub("", "\n".join(call.args[0])) for call in paint.call_args_list]
        self.assertIn("首页 / 班级", frames[-2])
        self.assertIn("LOCAL  test.db", frames[-1])

    def test_empty_database_offers_explicit_start_actions_without_seeding(self):
        db = Path(self.temp.name) / "empty.db"
        initialize_database(db)
        self.catalog = Catalog(db)
        frame = self.render(workspace.Workspace("students"))
        self.assertIn("名册还是空白", "".join(frame.lines))
        self.assertTrue({"create", "import", "seed"}.issubset({r.action for r in frame.regions}))
        self.assertEqual(self.catalog.service.stats()["students"], 0)

    def test_dashboard_uses_real_counts_and_import_error_details(self):
        frame = self.render(workspace.Workspace("data", report=["第 3 行：学号已存在"]))
        text = "".join(frame.lines)
        self.assertIn(f"{len(STUDENTS)} 学生", text)
        self.assertIn(f"{len(ENROLLMENTS)} 选课", text)
        self.assertIn("第 3 行：学号已存在", text)

    def test_compact_inspector_can_scroll_to_last_fields(self):
        state = workspace.Workspace("students")
        with patch.object(keys, "_read_key", side_effect=["focus", "end", "refresh"]), \
             patch.object(screen, "_paint") as paint, patch.object(
                 screen, "_terminal_size", return_value=os.terminal_size((30, 12))
             ):
            workspace_events.interact(state, self.catalog)
        self.assertTrue(any("备注" in "".join(call.args[0]) for call in paint.call_args_list))

    def test_import_reports_partial_failures_and_refreshes_data(self):
        sample = STUDENTS[0]
        path = Path(self.temp.name) / "students.csv"
        path.write_text(
            "student_no,name,family,branch,enrollment_year\n"
            f"29990001,新同学,{sample[2]},{sample[3]},2026\n"
            f"{sample[0]},重复,{sample[2]},{sample[3]},2026\n",
            encoding="utf-8",
        )
        state = workspace.Workspace("data")
        workspace_forms.open_form(state, self.catalog, "import")
        state.form.values["path"] = str(path)
        workspace_forms.apply_form(state, self.catalog)
        self.assertIn("已导入 1", state.notice)
        self.assertTrue(state.report)
        self.assertEqual(len(self.catalog.records["students"]), len(STUDENTS) + 1)


if __name__ == "__main__":
    unittest.main()
