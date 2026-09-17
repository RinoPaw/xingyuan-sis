"""Regression coverage for data that previously bypassed form validation."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xingyuan_sis.cli import main as cli_main
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.service import XingyuanService
from xingyuan_sis.tui.workspace.data import Catalog


class UnifiedContractTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'test.db'
        initialize_database(self.db)
        seed_demo(self.db)
        self.service = XingyuanService(self.db)

    def test_invalid_scores_never_clear_an_existing_grade(self):
        row = next(r for r in self.service.list_enrollments() if r['score'] is not None)
        identity = {key: row[key] for key in ('student_no', 'course_code', 'semester')}
        for score in (float('nan'), float('inf'), -1, 101):
            with self.subTest(score=score), self.assertRaises(ValueError):
                self.service.update_grade(**identity, score=score)
            self.assertEqual(self.service.enrollment(**identity)['score'], row['score'])
        with self.assertRaises(ValueError):
            self.service.add_grade(**{**identity, 'semester': 'new'}, score=float('nan'))
        self.assertIsNone(self.service.enrollment(identity['student_no'], identity['course_code'], 'new'))

    def test_cli_reports_invalid_numeric_input_without_writing(self):
        row = self.service.list_enrollments()[0]
        with redirect_stderr(StringIO()) as output:
            result = cli_main(['--db', str(self.db), 'grade', 'edit', row['student_no'],
                               row['course_code'], row['semester'], '--score', 'nan'])
        self.assertNotEqual(result, 0)
        self.assertIn('成绩', output.getvalue())
        self.assertEqual(self.service.enrollment(row['student_no'], row['course_code'], row['semester'])['score'], row['score'])

    def test_course_updates_reject_unknown_fields_and_fractional_hours(self):
        row = self.service.list_courses()[0]
        for values in ({'credist': 5}, {'credits': float('inf')}, {'hours': 2.5}, {'hours': 2**63}, {'name': '   '}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.service.update_course_by_code(row['course_code'], **values)
            self.assertEqual(dict(self.service.course_by_code(row['course_code'])), dict(row))

    def test_student_edits_normalize_without_changing_other_fields(self):
        row = self.service.list_students()[0]
        self.service.update_student_by_no(row['student_no'], name='  新名字  ', notes='  ')
        updated = self.service.student_by_no(row['student_no'])
        self.assertEqual(updated['name'], '新名字')
        self.assertIsNone(updated['notes'])
        for key in ('id', 'class_id', 'species_branch_id', 'enrollment_year'):
            self.assertEqual(updated[key], row[key])

    def test_partial_birth_dates_and_manual_age_share_one_contract(self):
        row = self.service.list_students()[0]
        student_no = row['student_no']

        self.service.update_student_by_no(student_no, birth_date='--06-09', age=39)
        updated = self.service.student_by_no(student_no)
        self.assertEqual(updated['birth_date'], '--06-09')
        self.assertEqual(updated['age'], 39)

        self.service.update_student_by_no(student_no, birth_date='1987')
        updated = self.service.student_by_no(student_no)
        self.assertEqual(updated['birth_date'], '1987')
        self.assertEqual(updated['age'], 39)

        self.service.update_student_by_no(student_no, birth_date='2000-06-09', age=99)
        updated = self.service.student_by_no(student_no)
        self.assertEqual(updated['birth_date'], '2000-06-09')
        self.assertIsNone(updated['age'])

        with self.assertRaises(ValueError):
            self.service.update_student_by_no(student_no, age=-1)

    def test_csv_and_form_share_partial_birth_date_validation(self):
        row = self.service.list_students()[0]
        catalog = Catalog(self.db)
        for field, invalid in (
            ('birth_date', '20070230'), ('birth_date', '2007-02-30'),
            ('birth_date', '2007-W01-1'), ('birth_date', '--02-30'),
            ('birth_date', '0000'), ('enrollment_year', '10000'),
        ):
            with self.subTest(field=field, invalid=invalid):
                with self.assertRaises(ValueError):
                    self.service.update_student_by_no(row['student_no'], **{field: invalid})
                values = catalog.defaults('students', catalog.records['students'][0])
                values[field] = invalid
                with self.assertRaises(ValueError):
                    catalog.save('students', values, catalog.records['students'][0])

        path = self.db.with_suffix('.csv')
        path.write_text(
            'student_no,name,family,branch,enrollment_year,birth_date,age\n'
            f"NEW1,坏日期,{row['family']},{row['branch']},2026,2007-02-30,18\n"
            f"NEW2,只有生日,{row['family']},{row['branch']},2026,--02-29,18\n"
            f"NEW3,完整生日,{row['family']},{row['branch']},2026,2008-02-29,99\n",
            encoding='utf-8',
        )
        result = self.service.import_students(path)
        self.assertEqual(result.imported, 2)
        self.assertEqual(len(result.errors), 1)
        self.assertIn('第 2 行', result.errors[0])
        self.assertIsNone(self.service.student_by_no('NEW1'))
        self.assertEqual(self.service.student_by_no('NEW2')['birth_date'], '--02-29')
        self.assertEqual(self.service.student_by_no('NEW2')['age'], 18)
        self.assertEqual(self.service.student_by_no('NEW3')['birth_date'], '2008-02-29')
        self.assertIsNone(self.service.student_by_no('NEW3')['age'])

    def test_empty_academic_names_and_semesters_are_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_department(code='NEW', name=' ')
        row = self.service.list_enrollments()[0]
        with self.assertRaises(ValueError):
            self.service.update_grade(student_no=row['student_no'], course_code=row['course_code'],
                                      semester=row['semester'], new_semester='', score=80)
