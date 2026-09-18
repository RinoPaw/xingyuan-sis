"""The first, terminal-system unit of the supplied Word specification."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xingyuan_sis import basic_ui, terminal_ui
from xingyuan_sis.auth import (
    Identity, authenticate, change_password, initialize_admin, read_session, write_session,
)
from xingyuan_sis.database import connect, initialize_database
from xingyuan_sis.entry import main
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.service import XingyuanService
from xingyuan_sis.tui import app, screen
from xingyuan_sis.tui.workspace import events, forms, view
from xingyuan_sis.tui.workspace.data import Catalog
from xingyuan_sis.tui.workspace.state import ContentPanel, FocusArea, Workspace


class DocumentRequirementTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / "test.db"
        environment = patch.dict(os.environ, {"XINGYUAN_HOME": str(self.root / "auth")})
        environment.start()
        self.addCleanup(environment.stop)
        initialize_database(self.db)
        seed_demo(self.db)
        self.service = XingyuanService(self.db)
        self.sample = self.service.list_students()[0]

    def student_values(self, no="00990001"):
        return dict(student_no=no, name="新同学", family=self.sample["family"],
                    branch=self.sample["branch"], enrollment_year=2026, class_code=self.sample["class_code"])

    def student_identity(self):
        _, password = self.service.register_student(**self.student_values())
        return authenticate(self.db, "00990001", password)

    def test_identity_fields_cannot_change_from_service_or_form(self):
        catalog = Catalog(self.db)
        row = catalog.records["students"][0]
        for field, value in (("name", "另一姓名"), ("student_no", "00999999")):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "不能修改"):
                self.service.update_student_by_no(row["student_no"], **{field: value, "status": "休学"})
            values = catalog.defaults("students", row)
            values[field] = value
            with self.assertRaisesRegex(ValueError, "不能修改"):
                catalog.save("students", values, row)
            self.assertEqual(dict(self.service.student_by_no(row["student_no"])), row)

    def test_created_student_has_hashed_credentials_and_must_change_password(self):
        record_id, password = self.service.register_student(**self.student_values())
        identity = authenticate(self.db, "00990001", password)
        self.assertTrue(identity.must_change_password)
        with self.assertRaisesRegex(ValueError, "不能与当前密码相同"):
            change_password(self.db, identity, password)
        with connect(self.db) as connection:
            row = connection.execute("SELECT password_hash FROM students WHERE id = ?", (record_id,)).fetchone()
        self.assertNotEqual(row["password_hash"], password)
        initialize_admin("adminpass")
        write_session(identity, self.db)
        self.assertIsNone(read_session(self.db))
        updated = change_password(self.db, identity, "changedpass")
        write_session(updated, self.db)
        self.assertEqual(read_session(self.db), updated)
        self.assertIsNone(authenticate(self.db, "00990001", password))
        self.service.delete_student_by_no("00990001")
        self.assertIsNone(read_session(self.db))
        self.assertIsNone(authenticate(self.db, "00990001", "changedpass"))

    def test_student_numbers_are_digits_only_across_creation_paths(self):
        invalid_numbers = ("Administrator", "STU001", "12 34", "-12", "+12", "1.2", "1e3", "１２３", "١٢٣", "²")
        catalog = Catalog(self.db)
        for no in invalid_numbers:
            with self.subTest(no=no):
                values = self.student_values(no)
                with self.assertRaisesRegex(ValueError, "学号只能包含"):
                    self.service.register_student(**values)
                form_values = catalog.defaults("students") | values
                with self.assertRaisesRegex(ValueError, "学号只能包含"):
                    catalog.save("students", form_values)
                self.assertIsNone(self.service.student_by_no(no))
        write_session(initialize_admin("adminpass"), self.db)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as error:
            code = main(["--db", str(self.db), "stu", "add", "--no", "12a", "--name", "新同学",
                         "--family", self.sample["family"], "--branch", self.sample["branch"], "--year", "2026"])
        self.assertEqual(code, 1)
        self.assertIn("学号只能包含", error.getvalue())
        path = self.root / "invalid-numbers.csv"
        path.write_text("student_no,name,family,branch,enrollment_year\n" + "".join(
            f"{no},新同学,{self.sample['family']},{self.sample['branch']},2026\n" for no in invalid_numbers
        ), encoding="utf-8")
        result = self.service.import_students(path)
        self.assertEqual(result.imported, 0)
        self.assertEqual(len(result.errors), len(invalid_numbers))
        self.assertTrue(all("学号只能包含" in error for error in result.errors))

    def test_tui_create_delivers_credentials_only_after_successful_save(self):
        catalog = Catalog(self.db)
        state = Workspace("students")
        forms.open_form(state, catalog, "create")
        state.form.values.update(self.student_values())
        self.assertFalse(state.credentials)
        forms.apply_form(state, catalog)
        self.assertEqual(len(state.credentials), 1)
        no, password = state.credentials[0]
        self.assertEqual(no, "00990001")
        self.assertTrue(authenticate(self.db, no, password).must_change_password)
        self.assertEqual(state.focus, FocusArea.INSPECTOR)
        self.assertEqual(state.content_panel, ContentPanel.INSPECTOR)

    def test_csv_registration_uses_same_validation_and_reports_successful_credentials(self):
        path = self.root / "new.csv"
        path.write_text("student_no,name,family,branch,enrollment_year\n"
                        f"00990001,新同学,{self.sample['family']},{self.sample['branch']},2026\n"
                        f"00990001,重复,{self.sample['family']},{self.sample['branch']},2026\n"
                        f"00990002,错误年份,{self.sample['family']},{self.sample['branch']},NaN\n", encoding="utf-8")
        result = self.service.import_students(path)
        self.assertEqual(result.imported, 1)
        self.assertEqual(len(result.errors), 2)
        self.assertEqual(len(result.credentials), 1)
        no, password = result.credentials[0]
        self.assertTrue(authenticate(self.db, no, password).must_change_password)
        self.assertIsNone(self.service.student_by_no("00990002"))
        exported = self.root / "export.csv"
        self.service.export_students(exported)
        self.assertNotIn(password, exported.read_text(encoding="utf-8-sig"))
        self.assertNotIn("password", exported.read_text(encoding="utf-8-sig"))

    def test_announcements_persist_and_follow_the_students_current_class(self):
        classes = self.service.list_classes()
        first, second = classes[0], classes[1]
        own = self.service.create_announcement(title="本班通知", body="第一行\n第二行", class_code=first["code"])
        other = self.service.create_announcement(title="另一班通知", body="其他内容", class_code=second["code"])
        no = self.sample["student_no"]
        self.service.update_student_by_no(no, class_code=first["code"])
        self.assertEqual([row["id"] for row in XingyuanService(self.db).list_announcements(no)], [own])
        self.service.update_student_by_no(no, class_code=second["code"])
        self.assertEqual([row["id"] for row in self.service.list_announcements(no)], [other])
        self.service.update_student_by_no(no, class_code=None)
        self.assertEqual(self.service.list_announcements(no), [])
        self.assertEqual(self.service.list_announcements("NONEXISTENT"), [])
        self.service.delete_announcement(own)
        self.assertEqual([row["id"] for row in self.service.list_announcements()], [other])

    def test_student_cli_cannot_read_other_class_announcements_or_write(self):
        initialize_admin("adminpass")
        identity = change_password(self.db, self.student_identity(), "studentpass")
        write_session(identity, self.db)
        own = self.service.create_announcement(title="本班通知", body="本班正文", class_code=self.sample["class_code"])
        other_class = next(row for row in self.service.list_classes() if row["code"] != self.sample["class_code"])
        other = self.service.create_announcement(title="另班通知", body="另班正文", class_code=other_class["code"])
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main(["--db", str(self.db), "notice", "ls"]), 0)
        self.assertIn("本班通知", output.getvalue())
        self.assertNotIn("另班通知", output.getvalue())
        for args in (("notice", "show", str(other)), ("notice", "rm", str(own), "-y"),
                     ("stu", "rm", self.sample["student_no"], "-y"), ("data", "seed", "--reset")):
            with self.subTest(args=args), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main(["--db", str(self.db), *args]), 1)
        self.assertEqual(len(self.service.list_announcements()), 2)

    def test_basic_commands_use_authentication_before_dispatch(self):
        initialize_admin("adminpass")
        with patch("xingyuan_sis.auth_cli.read_session", return_value=None), \
             patch("xingyuan_sis.cli.run_group") as runner, patch("builtins.input", return_value=""), \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            terminal_ui.run_command(self.db, ["stu", "rm", self.sample["student_no"], "-y"], lambda: None)
        runner.assert_not_called()
        self.assertIsNotNone(self.service.student_by_no(self.sample["student_no"]))

    def test_basic_student_menu_contains_only_available_actions(self):
        initialize_admin("adminpass")
        identity = change_password(self.db, self.student_identity(), "studentpass")
        write_session(identity, self.db)
        with patch.object(basic_ui, "_clear"), patch("builtins.input", return_value="q"), redirect_stdout(StringIO()) as output:
            basic_ui.run(self.db)
        text = output.getvalue()
        self.assertIn("班级公告", text)
        self.assertIn("个人中心", text)
        self.assertNotIn("5. 数据", text)
        with patch.object(basic_ui, "_clear"), patch("builtins.input", return_value="q"), redirect_stdout(StringIO()) as output:
            basic_ui._students(self.db, manage=False)
        self.assertNotIn("删除", output.getvalue())
        self.assertIn("搜索", output.getvalue())

    def test_student_directory_and_personal_profile_use_the_same_read_only_workspace(self):
        identity = Identity(self.sample["student_no"], "student", self.sample["student_no"])
        with patch("xingyuan_sis.tui.workspace.run") as run:
            app._execute_portal_action("student-directory", self.db, identity)
            app._show_profile(self.db, identity)
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertEqual(call.args, (self.db, "students"))
            self.assertEqual(call.kwargs["identity"], identity)
        self.assertIn(self.sample["student_no"], run.call_args.kwargs["query"])

    def test_long_announcement_can_be_read_to_the_end_in_short_window(self):
        self.service.create_announcement(title="长公告", body="\n".join(f"第{i}行公告正文" for i in range(30)) + "\n最后一行",
                                         class_code=self.sample["class_code"])
        catalog = Catalog(self.db, Identity(self.sample["student_no"], "student", self.sample["student_no"]))
        state = Workspace(
            "announcements",
            focus=FocusArea.INSPECTOR,
            content_panel=ContentPanel.INSPECTOR,
        )
        with patch.object(screen, "_terminal_size", return_value=os.terminal_size((30, 12))), \
             patch.object(screen, "_paint"), patch("xingyuan_sis.tui.keys._read_key", side_effect=["end", "refresh"]):
            events.interact(state, catalog)
            frame = view.render(state, catalog)
        self.assertIn("最后一行", "".join(frame.lines))
        self.assertFalse(any(region.action.startswith("edit-field:") for region in frame.regions))
