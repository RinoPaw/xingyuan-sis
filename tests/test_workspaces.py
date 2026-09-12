from contextlib import nullcontext, redirect_stdout
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import ENROLLMENTS, STUDENTS, seed_demo
from xingyuan_sis.tui import app, keys, screen, workspace, workspace_view
from xingyuan_sis.tui.workspace_data import COLLECTIONS, Catalog


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
            return workspace._interact(state, self.catalog)

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
                            self.assertEqual(screen._hit_action(keys.MouseClick(region.x, region.y), frame.regions), region.action)

    def test_wheel_scrolls_the_panel_under_the_pointer(self):
        state = workspace.Workspace("students")
        with patch.object(keys, "_read_key", side_effect=[keys.MouseScroll(70, 12, "down"), "back", "back"]), \
             patch.object(screen, "_paint") as paint, patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 24))):
            workspace._interact(state, self.catalog)
        self.assertEqual(state.selected, 0)
        self.assertIn("2–", "".join(paint.call_args_list[1].args[0]))
        self.interact(state, [keys.MouseScroll(2, 12, "down"), "back"])
        self.assertEqual(state.selected, 1)

    def test_selection_updates_profile_without_query_or_enter(self):
        state = workspace.Workspace("students")
        first = self.render(state)
        expected = self.catalog.records["students"][1]
        second_row = next(r for r in first.regions if r.action == "row:1")
        with patch.object(keys, "_read_key", side_effect=[keys.MouseClick(second_row.x, second_row.y), "back"]), \
             patch.object(screen, "_paint") as paint, patch.object(screen, "_terminal_size", return_value=os.terminal_size((120, 35))):
            workspace._interact(state, self.catalog)
        self.assertEqual(state.current(self.catalog)["name"], expected["name"])
        last_frame = paint.call_args_list[-1].args[0]
        self.assertIn(expected["name"], last_frame[9])
        self.assertGreater(screen._display_width(last_frame[9].split(expected["name"])[0]), 60)
        self.assertIn(expected["department_name"], "".join(last_frame))
        self.assertNotIn("Enter 查询", "".join(last_frame))

    def test_related_record_link_and_return_preserve_roster_position(self):
        state = workspace.Workspace("students", query="元素", selected=1)
        original = state.current(self.catalog)
        related_key, related = self.catalog.related(state.key, original)
        self.assertTrue(related)
        self.interact(state, [f"related:{related_key}:{related[0]['id']}", "back", "back"])
        self.assertEqual((state.key, state.query, state.selected), ("students", "元素", 1))
        self.assertEqual(state.current(self.catalog)["id"], original["id"])

    def test_keyboard_filters_and_unicode_search_use_real_records(self):
        state = workspace.Workspace("grades")
        self.interact(state, ["2", "back"])
        self.assertTrue(state.rows(self.catalog))
        self.assertTrue(all(row["score"] is None for row in state.rows(self.catalog)))
        state.switch("students")
        expected = STUDENTS[0]
        with patch("builtins.input", return_value=str(expected[1])), patch.object(screen, "_paint"), redirect_stdout(StringIO()):
            workspace._read_value(state, self.catalog, ("search", 0))
        self.assertEqual(
            [row["student_no"] for row in state.rows(self.catalog)],
            [str(expected[0])],
        )

    def test_edit_stages_values_and_cancel_does_not_write(self):
        state = workspace.Workspace("students")
        original = state.current(self.catalog).copy()
        workspace._open_form(state, self.catalog, "edit")
        with patch("builtins.input", return_value="暂存的名字"), patch.object(screen, "_paint"), redirect_stdout(StringIO()):
            workspace._read_value(state, self.catalog, ("field", 1))
        self.assertEqual(state.form.values["name"], "暂存的名字")
        self.assertEqual(self.catalog.service.student_by_no(original["student_no"])["name"], original["name"])
        self.interact(state, ["cancel", "back"])
        self.assertIsNone(state.form)
        self.assertEqual(self.catalog.service.student_by_no(original["student_no"])["name"], original["name"])

    def test_edit_selected_student_can_change_identifier_and_keeps_relationships(self):
        state = workspace.Workspace("students", selected=9)
        original = state.current(self.catalog).copy()
        workspace._open_form(state, self.catalog, "edit")
        state.form.values.update(student_no="20990001", name="临时新档案")
        workspace._apply_form(state, self.catalog)
        self.assertIsNone(self.catalog.service.student_by_no(original["student_no"]))
        changed = self.catalog.service.student_by_no("20990001")
        self.assertEqual((changed["id"], changed["name"]), (original["id"], "临时新档案"))
        self.assertEqual(state.current(self.catalog)["id"], original["id"])
        self.assertTrue(any(row["student_no"] == "20990001" for row in self.catalog.records["grades"]))

    def test_course_edit_renames_code_without_changing_enrollments(self):
        row = self.catalog.records["courses"][0]
        values = self.catalog.defaults("courses", row)
        values["course_code"] = "NEW101"
        self.catalog.save("courses", values, row)
        self.assertEqual(self.catalog.service.course_by_code("NEW101")["id"], row["id"])

    def test_zero_score_and_clearing_score_are_distinct(self):
        state = workspace.Workspace("grades", view=1)
        original = state.current(self.catalog).copy()
        workspace._open_form(state, self.catalog, "edit")
        self.assertNotIn("student_no", [field.key for field in state.form.fields])
        state.form.values["score"] = 0
        workspace._apply_form(state, self.catalog)
        row = next(r for r in self.catalog.records["grades"] if r["id"] == original["id"])
        self.assertEqual(row["score"], 0)
        self.assertIn("不符合当前筛选", state.notice)
        values = self.catalog.defaults("grades", row)
        values["score"] = None
        self.catalog.save("grades", values, row)
        self.assertIsNone(next(r for r in self.catalog.records["grades"] if r["id"] == row["id"])["score"])

    def test_invalid_form_values_do_not_write(self):
        row = self.catalog.records["grades"][0]
        for score in ("nan", "inf", "101", "-1", "不合法"):
            with self.subTest(score=score):
                values = self.catalog.defaults("grades", row)
                values["score"] = score
                with self.assertRaises(ValueError):
                    self.catalog.save("grades", values, row)
                self.assertEqual(self.catalog.service.enrollment(row["student_no"], row["course_code"], row["semester"])["score"], row["score"])

    def test_foreign_keys_are_picked_by_name_and_staged(self):
        state = workspace.Workspace("students", selected=9)
        workspace._open_form(state, self.catalog, "edit")
        state.form.position = 5
        workspace._read_value(state, self.catalog, ("field", 5))
        self.assertTrue(any("元素学" in label for _, label in state.form.options))
        self.interact(state, ["option:0", "save"])
        self.assertIsNone(state.form.values["class_code"])
        self.assertIsNotNone(state.form.original["class_id"])

    def test_create_and_remove_record_refresh_the_workspace(self):
        state = workspace.Workspace("departments")
        workspace._open_form(state, self.catalog, "create")
        state.form.values.update(code="NEW", name="新学院")
        workspace._apply_form(state, self.catalog)
        self.assertEqual(state.current(self.catalog)["code"], "NEW")
        workspace._open_form(state, self.catalog, "delete")
        self.assertIsNotNone(self.catalog.service.department_by_code("NEW"))
        self.assertIn("确认删除 新学院", "".join(self.render(state).lines))
        workspace._apply_form(state, self.catalog)
        self.assertIsNone(self.catalog.service.department_by_code("NEW"))

    def test_form_scrolls_selected_field_into_view_after_resize(self):
        state = workspace.Workspace("students")
        workspace._open_form(state, self.catalog, "edit")
        state.form.position = 13
        for size in ((120, 35), (80, 24), (40, 20), (30, 12)):
            with self.subTest(size=size):
                frame = self.render(state, size)
                self.assertIn("备注", "".join(frame.lines))
                self.assertTrue(any(r.action == "field:13" for r in frame.regions))
                self.assertTrue(any(r.action == "save" for r in frame.regions))

    def test_short_workspace_keeps_every_record_accessible(self):
        state = workspace.Workspace("students")
        expected_name = self.catalog.records["students"][-1]["name"]
        with patch.object(keys, "_read_key", side_effect=["end", "back"]), patch.object(screen, "_paint") as paint, \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((30, 12))):
            workspace._interact(state, self.catalog)
        self.assertEqual(state.selected, len(self.catalog.records["students"]) - 1)
        self.assertIn(expected_name, "".join(paint.call_args_list[-1].args[0]))

    def test_breadcrumb_returns_home_after_resizing_academic_workspace(self):
        identity = app.Identity("Administrator", "admin")
        events = ["2", "right", "down", "select", keys.MouseClick(2, 2), "back"]
        with redirect_stdout(StringIO()), patch.object(keys, "_read_key", side_effect=events), \
             patch.object(app, "read_session", return_value=identity), \
             patch.object(screen, "_paint") as paint, patch.object(screen, "_clear"), \
             patch.object(keys, "_mouse_tracking", nullcontext), patch.object(screen, "_terminal_session", nullcontext), \
             patch.object(screen, "_terminal_size", return_value=os.terminal_size((80, 24))), \
             patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True):
            app.run(self.db)
        frames = [screen._ANSI_RE.sub("", "\n".join(call.args[0])) for call in paint.call_args_list]
        self.assertIn("首页 / 教务 / 班级", frames[-2])
        self.assertIn("LOCAL / test.db", frames[-1])

    def test_empty_database_offers_explicit_start_actions_without_seeding(self):
        db = Path(self.temp.name) / "empty.db"
        initialize_database(db)
        self.catalog = Catalog(db)
        frame = self.render(workspace.Workspace("students"))
        self.assertIn("名册还是空白", "".join(frame.lines))
        self.assertTrue({"create", "import", "seed"}.issubset({r.action for r in frame.regions}))
        self.assertEqual(self.catalog.service.stats()["students"], 0)

    def test_dashboard_uses_real_counts_and_import_error_details(self):
        state = workspace.Workspace("data", report=["第 3 行：学号重复"])
        frame = self.render(state)
        text = "".join(frame.lines)
        self.assertIn(f"{len(STUDENTS)} 学生", text)
        self.assertIn(f"{len(ENROLLMENTS)} 选课", text)
        self.assertIn("第 3 行：学号重复", text)

    def test_compact_inspector_can_scroll_to_last_fields(self):
        state = workspace.Workspace("students")
        with patch.object(keys, "_read_key", side_effect=["focus", "end", "back", "back"]), \
             patch.object(screen, "_paint") as paint, patch.object(screen, "_terminal_size", return_value=os.terminal_size((30, 12))):
            workspace._interact(state, self.catalog)
        self.assertTrue(any("备注" in "".join(call.args[0]) for call in paint.call_args_list))
        self.assertEqual(state.selected, 0)

    def test_data_shortcuts_open_the_displayed_collections(self):
        state = workspace.Workspace("data")
        self.interact(state, ["4", "back"])
        self.assertEqual(state.key, "departments")

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
        workspace._open_form(state, self.catalog, "import")
        state.form.values["path"] = str(path)
        workspace._apply_form(state, self.catalog)
        self.assertIn("已导入 1", state.notice)
        self.assertTrue(state.report)
        self.assertEqual(len(self.catalog.records["students"]), len(STUDENTS) + 1)

    def test_seed_confirmation_never_resets_existing_data(self):
        state = workspace.Workspace("data")
        workspace._open_form(state, self.catalog, "seed")
        with self.assertRaisesRegex(ValueError, "已有校园记录"):
            workspace._apply_form(state, self.catalog)
        self.assertEqual(self.catalog.service.stats()["students"], len(STUDENTS))


if __name__ == "__main__":
    unittest.main()
