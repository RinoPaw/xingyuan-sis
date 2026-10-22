from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import unittest

from xingyuan_sis.auth import Identity
from xingyuan_sis.database import initialize_database
from xingyuan_sis.service import XingyuanService
from xingyuan_sis.gui.controller import CampusController, fields


class CampusFixture:
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "campus.db"
        initialize_database(self.db)
        self.service = XingyuanService(self.db)
        self.service.seed_demo()
        self.admin = CampusController(self.db, Identity("Administrator", "admin"))
        self.student = CampusController(self.db, Identity("20260001", "student", "20260001"))


class ControllerTests(CampusFixture, unittest.TestCase):
    def test_every_write_and_admin_read_rejects_student_identity(self):
        for key in ("students", "courses", "grades", "departments", "majors", "classes", "announcements", "families", "branches"):
            with self.subTest(key=key):
                with self.assertRaises(PermissionError):
                    self.student.save(key, {})
                with self.assertRaises(PermissionError):
                    self.student.delete(key, {})
        for action in (lambda: self.student.seed(), lambda: self.student.import_csv("missing"),
                lambda: self.student.export_csv("missing"), lambda: self.student.reset_password("20260001"),
                lambda: self.student.rows("grades")):
            with self.assertRaises(PermissionError):
                action()

    def test_forced_password_identity_cannot_enter_workspace(self):
        with self.assertRaises(PermissionError):
            CampusController(self.db, Identity("20260001", "student", "20260001", True))

    def test_student_announcements_follow_current_class_and_other_grades_are_hidden(self):
        own = self.service.student_by_no("20260001")["class_code"]
        other = next(r["code"] for r in self.service.list_classes() if r["code"] != own)
        self.service.create_announcement(title="本班", body="正文", class_code=own)
        self.service.create_announcement(title="另班", body="正文", class_code=other)
        self.assertEqual([r["title"] for r in self.student.rows("announcements")], ["本班"])
        self.assertEqual(self.student.student_grades("20250001"), [])
        self.service.update_student_by_no("20260001", class_code=other)
        self.assertEqual([r["title"] for r in self.student.rows("announcements")], ["另班"])

    def test_related_public_codes_are_present_in_edit_drafts(self):
        for key in ("departments", "majors", "classes", "courses", "grades", "students", "announcements"):
            rows = self.admin.rows(key)
            if key == "announcements" and not rows:
                continue
            for field in fields(key):
                self.assertIn(field.key, rows[0], (key, field.key))

    def test_edit_keeps_name_and_student_number_immutable(self):
        row = self.admin.rows("students")[0]
        with self.assertRaisesRegex(ValueError, "姓名不能修改"):
            self.admin.save("students", {"name": "修改姓名"}, row)
        self.admin.save("students", {"notes": "新备注"}, row)
        self.assertEqual(self.service.student_by_no(row["student_no"])["notes"], "新备注")


class RealTkWorkflowTests(CampusFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
        except ImportError as error:
            raise unittest.SkipTest(f"Tk unavailable: {error}")
        try:
            probe = tk.Tk()
            probe.destroy()
        except tk.TclError as error:
            raise unittest.SkipTest(f"Tk display unavailable: {error}")

    def setUp(self):
        super().setUp()
        import tkinter as tk
        from xingyuan_sis.gui.theme import configure_styles
        from xingyuan_sis.gui.main_window import MainWindow
        self.root = tk.Tk()
        self.callback_errors = []
        self.root.report_callback_exception = lambda kind, value, tb: self.callback_errors.append(str(value))
        self.addCleanup(self.assertEqual, self.callback_errors, [])
        self.root.geometry("1280x820")
        self.root.tk.call("tk", "scaling", 96/72)
        self.addCleanup(self.root.destroy)
        configure_styles(self.root)
        self.window = MainWindow(self.root, self.db, Identity("Administrator", "admin"), on_logout=lambda: None)
        self.window.pack(fill="both", expand=True)
        self.root.update()

    def test_all_admin_pages_render_and_theme_rebuild_preserves_selection(self):
        for page, _ in self.window.navigation:
            self.window.show_page(page)
            self.root.update()
        for key in ("departments", "majors", "classes", "families", "branches"):
            self.window._academic_page(key)
            self.root.update()
        self.window.show_page("students")
        self.window.tree.selection_set("20260001")
        self.window.inspect()
        self.window.search.set("雷格西")
        self.window.reload_rows()
        self.window.theme_var.set("afterhours")
        self.window.change_theme()
        self.root.update()
        self.assertEqual(self.window.current_record()["student_no"], "20260001")
        self.assertEqual(self.window.search.get(), "雷格西")

    def test_type_roles_use_bundled_faces_and_scale_without_losing_navigation(self):
        import sys
        from tkinter import font, ttk
        from xingyuan_sis.gui.typography import font_tuple
        if sys.platform == "win32":
            self.assertEqual(self.root.campus_fonts["display"], "MFLiHeiNoncommercial")
            self.assertEqual(self.root.campus_fonts["latin"], "Barlow Condensed Black")
        for zoom in (1.0, 1.25, 1.5):
            self.window.zoom_var.set(zoom)
            self.window.change_theme()
            self.root.update()
            face = font.Font(root=self.root, font=font_tuple(self.root, "display", 20))
            self.assertEqual(face.actual("family"), self.root.campus_fonts["display"])
            style = ttk.Style(self.root)
            for nav in self.window.nav_buttons.values():
                face = font.Font(root=self.root, font=style.lookup(nav.button.cget("style"), "font"))
                self.assertLess(face.measure(nav.button.cget("text")), nav.button.winfo_width() - 8)
                self.assertGreaterEqual(nav.button.winfo_height(), face.metrics("linespace"))
                number = nav.canvas.find_withtag("nav-number")[0]
                number_face = font.Font(root=self.root, font=nav.canvas.itemcget(number,"font"))
                number_baseline = nav.canvas.coords(number)[1] + number_face.metrics("ascent")
                label_baseline = nav.button.winfo_y() + (nav.button.winfo_height()-face.metrics("linespace"))//2 + face.metrics("ascent")
                self.assertAlmostEqual(number_baseline,label_baseline,delta=1)

    def test_detail_tabs_share_grid_and_long_notes_use_outer_scrolling(self):
        from tkinter import ttk
        from xingyuan_sis.gui.widgets import ScrollArea, ReadonlyParagraph
        row = self.admin.rows("students")[0]
        notes = (("一段需要随窗口宽度换行的长备注。" * 6 + "\n") * 16).rstrip()
        self.service.update_student_by_no(row["student_no"],notes=notes)
        self.window.show_page("students")
        self.window.tree.selection_set(row["student_no"]);self.window.inspect();self.root.update()
        tabs = next(w for w in self.window.inspector.winfo_children() if isinstance(w,ttk.Notebook))
        areas = [self.root.nametowidget(tab) for tab in tabs.tabs()]
        self.assertTrue(all(isinstance(area,ScrollArea) for area in areas))
        origins = []
        for index, area in enumerate(areas):
            tabs.select(index);self.root.update()
            origins.append(area.body.grid_slaves(row=0,column=1)[0].winfo_x())
        self.assertEqual(origins,[origins[0]]*3)
        area = areas[2]
        text = area.body.grid_slaves(row=2,column=1)[0]
        self.assertIsInstance(text,ReadonlyParagraph)
        self.assertEqual(text.get("1.0","end-1c"),notes)
        text.insert("1.0","不能编辑")
        self.assertEqual(text.get("1.0","end-1c"),notes)
        self.assertGreater(int(text.cget("height")),16)
        text.event_generate("<MouseWheel>",delta=-120);self.root.update()
        self.assertGreater(area.canvas.yview()[0],0)
        self.assertEqual(text.yview(),(0.0,1.0))
        widgets = tuple(self.window.inspector.winfo_children())
        self.window.inspect();self.root.update()
        self.assertEqual(tuple(self.window.inspector.winfo_children()),widgets)
        self.assertEqual(tabs.index(tabs.select()),2)

    def test_academic_tabs_reuse_mapped_layout_and_update_columns_and_actions(self):
        from xingyuan_sis.gui.controller import COLLECTIONS
        self.window.show_page("academics");self.root.update()
        children = tuple(self.window.content.winfo_children())
        tree = self.window.tree
        unmapped = []
        for widget in children:
            widget.bind("<Unmap>",lambda e:unmapped.append(str(e.widget)),add="+")
        for key in ("classes","families","branches","majors","departments"):
            self.window._academic_page(key);self.root.update()
            self.assertEqual(tuple(self.window.content.winfo_children()),children)
            self.assertIs(self.window.tree,tree)
            self.assertEqual(tree.cget("columns"),tuple(c[0] for c in COLLECTIONS[key].columns))
            self.assertEqual(self.window.new_button.cget("text"),"新增"+COLLECTIONS[key].singular+"…")
            self.assertTrue(tree.get_children())
        self.assertEqual(unmapped,[])

    def test_missing_display_fonts_keep_native_controls_usable(self):
        from xingyuan_sis.gui.typography import configure_fonts
        with patch("xingyuan_sis.gui.typography.load_display_fonts"), patch(
                "xingyuan_sis.gui.typography.tkfont.families", return_value=("Microsoft YaHei UI",)):
            chosen = configure_fonts(self.root)
        self.assertEqual(set(chosen.values()), {"Microsoft YaHei UI"})
        self.window.show_page("students")
        self.root.update()
        self.assertTrue(self.window.tree.winfo_ismapped())

    def test_sort_and_search_keep_record_identity(self):
        self.window.show_page("students")
        self.window.tree.selection_set("20260001")
        self.window.inspect()
        self.window.sort("name")
        self.assertEqual(self.window.current_record()["name"], "雷格西")
        self.window.search.set("不存在的人物")
        self.window.reload_rows()
        self.assertIsNone(self.window.current_record())
        self.assertEqual(self.window.tree.get_children(), ())

    def test_collection_has_one_page_title_and_no_decorative_masthead(self):
        import tkinter as tk
        from tkinter import ttk
        self.window.show_page("students")
        self.root.update()
        def walk(widget):
            yield widget
            for child in widget.winfo_children():
                yield from walk(child)
        labels = [w.cget("text") for w in walk(self.window) if isinstance(w, ttk.Label)]
        titles = [w.itemcget(item,"text") for w in walk(self.window) if isinstance(w,tk.Canvas)
                  for item in w.find_withtag("page-title")]
        self.assertEqual(titles, ["学生名册"])
        self.assertFalse(hasattr(self.window, "masthead"))
        self.assertNotIn("同窗。\n不止一个名字。", labels)

    def test_wheel_over_filter_scrolls_roster_without_changing_filter(self):
        from tkinter import ttk
        self.window.show_page("students")
        self.root.update()
        combo = next(w for w in self.window.search_entry.master.winfo_children() if isinstance(w,ttk.Combobox))
        value, selected = combo.get(), self.window.tree.selection()
        self.window.tree.yview_moveto(0)
        combo.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertEqual(combo.get(), value)
        self.assertEqual(self.window.tree.selection(), selected)
        self.assertGreater(self.window.tree.yview()[0], 0)

    def test_wheel_over_editor_combo_scrolls_exactly_once_and_preserves_draft(self):
        from xingyuan_sis.gui.widgets import RecordDialog
        row = self.admin.rows("students")[0]
        dialog = RecordDialog(self.window, self.admin, "students", row)
        self.root.update()
        before = dialog.values()
        dialog.canvas.yview_moveto(0)
        dialog.canvas.yview_scroll(1,"units")
        expected = dialog.canvas.yview()
        dialog.canvas.yview_moveto(0)
        dialog.controls["gender"].event_generate("<MouseWheel>",delta=-120)
        self.root.update()
        self.assertEqual(dialog.values(),before)
        self.assertEqual(dialog.canvas.yview(),expected)
        dialog.destroy()

    def test_wheel_over_notebook_scrolls_selected_page_without_changing_tab(self):
        from tkinter import ttk
        self.window.show_page("students")
        self.root.update()
        tabs = next(w for w in self.window.inspector.winfo_children() if isinstance(w,ttk.Notebook))
        selected = tabs.select()
        area = self.root.nametowidget(selected)
        area.canvas.yview_moveto(0)
        tabs.event_generate("<MouseWheel>",delta=-120)
        self.root.update()
        self.assertEqual(tabs.select(),selected)
        self.assertGreater(area.canvas.yview()[0],0)

    def test_large_editor_keeps_all_fields_and_places_birthday_before_age(self):
        from xingyuan_sis.gui.widgets import RecordDialog
        from xingyuan_sis.gui.theme import configure_styles
        configure_styles(self.root, "afterhours", 1.5)
        row = self.admin.rows("students")[0]
        dialog = RecordDialog(self.window, self.admin, "students", row)
        self.root.update()
        self.assertEqual(set(dialog.vars), {f.key for f in fields("students")})
        self.assertLess(dialog.controls["birth_date"].winfo_y(), dialog.controls["age"].winfo_y())
        for control in dialog.controls.values():
            self.assertGreaterEqual(control.winfo_x(), 0)
            self.assertLessEqual(control.winfo_x()+control.winfo_width(), dialog.form.winfo_width())
        dialog.destroy()

    def test_invalid_dialog_and_cancel_do_not_write(self):
        from xingyuan_sis.gui.widgets import RecordDialog
        self.window.show_page("students")
        row = self.window.controller.rows("students")[0]
        dialog = RecordDialog(self.window, self.admin, "students", row)
        dialog.vars["enrollment_year"].set("错误年份")
        dialog.save()
        self.assertIn("入学年份", dialog.error.get())
        self.assertEqual(self.service.student_by_no(row["student_no"])["enrollment_year"], row["enrollment_year"])
        with patch("xingyuan_sis.gui.widgets.messagebox.askyesno", return_value=True):
            dialog.cancel()
        self.assertFalse(dialog.winfo_exists())

    def test_valid_dialog_preserves_family_branch_and_class_codes(self):
        from xingyuan_sis.gui.widgets import RecordDialog
        row = self.admin.rows("students")[0]
        dialog = RecordDialog(self.window, self.admin, "students", row)
        dialog.multiline["notes"].insert("1.0", "保存测试")
        dialog.save()
        self.assertFalse(dialog.winfo_exists())
        saved = self.service.student_by_no(row["student_no"])
        self.assertEqual(saved["class_code"], row["class_code"])
        self.assertEqual(saved["branch"], row["branch"])
        self.assertEqual(saved["notes"], "保存测试")

    def test_root_key_bindings_are_removed_on_logout(self):
        binding = self.window.bindings["<Control-n>"]
        self.assertIn(binding, self.root.bind("<Control-n>"))
        self.window.destroy()
        self.assertNotIn(binding, self.root.bind("<Control-n>"))

    def test_large_font_small_window_keeps_details_inline_and_restores_split(self):
        from tkinter import ttk
        self.root.geometry("960x640")
        self.window.show_page("students")
        self.window.tree.selection_set("20260001")
        self.window.inspect()
        self.window.theme_var.set("afterhours")
        self.window.zoom_var.set(1.5)
        self.window.change_theme()
        self.root.update()
        self.assertTrue(self.window.compact_inspector)
        self.assertTrue(self.window.tree.winfo_ismapped())
        selected = self.window.tree.selection()[0]
        for key in (selected, self.window.tree.next(selected)):
            bounds = self.window.tree.bbox(key)
            self.assertTrue(bounds)
            self.assertLessEqual(bounds[1] + bounds[3], self.window.tree.winfo_height())
        self.window.compact_tabs.select(1)
        self.root.update()
        self.assertTrue(self.window.inspector.winfo_ismapped())
        details = next(w for w in self.window.inspector.winfo_children() if isinstance(w, ttk.Notebook))
        self.assertGreater(details.winfo_height(), 150)
        self.assertFalse(self.window.search_entry.winfo_ismapped())
        selected_area = self.root.nametowidget(details.select())
        self.assertGreater(selected_area.canvas.winfo_height(), 70)
        self.window.focus_search()
        self.root.update()
        self.assertTrue(self.window.tree.winfo_ismapped())
        self.assertTrue(self.window.search_entry.winfo_ismapped())
        self.assertEqual(self.window.tree.selection(), (selected,))
        self.assertFalse(self.window.bindings.get("<F6>"))
        self.assertFalse(self.window.tree.bind("<Return>"))
        self.assertFalse(self.window.tree.bind("<Double-1>"))
        # Tk's virtual desktop default maxsize can be smaller on scaled Windows
        # desktops. Explicitly allow the wide layout for this round-trip check.
        self.root.maxsize(1800, 1100)
        self.root.geometry("1800x1100")
        self.root.update_idletasks()
        self.root.update()
        self.assertFalse(self.window.compact_inspector)
        self.assertTrue(self.window.tree.winfo_ismapped())
        self.assertTrue(self.window.inspector.winfo_ismapped())
        self.assertEqual(self.window.tree.selection(), (selected,))

    def test_initialize_login_and_first_student_password_change(self):
        from xingyuan_sis.gui.login import LoginView
        from xingyuan_sis.auth import INITIAL_STUDENT_PASSWORD, read_session
        with patch.dict(os.environ, {"XINGYUAN_HOME": str(Path(self.temp.name) / "auth")}):
            self.window.destroy()
            identities = []
            login = LoginView(self.root, self.db, on_success=identities.append)
            login.pack(fill="both", expand=True)
            self.assertEqual(login.mode, "setup")
            login.password_var.set("adminpass")
            login.confirm_var.set("adminpass")
            login._submit_setup()
            self.assertEqual(login.mode, "login")
            login.username_var.set("20260001")
            login.password_var.set(INITIAL_STUDENT_PASSWORD)
            login._submit_login()
            self.assertEqual(login.mode, "forced-password")
            self.assertEqual(identities, [])
            login.password_var.set("changedpass")
            login.confirm_var.set("changedpass")
            login._submit_forced_password()
            self.assertEqual(len(identities), 1)
            self.assertFalse(identities[0].must_change_password)
            self.assertEqual(read_session(self.db).student_no, "20260001")


if __name__ == "__main__":
    unittest.main()
