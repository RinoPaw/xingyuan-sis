"""Interactions must address the controls actually visible at every breakpoint."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from xingyuan_sis.auth import Identity
from xingyuan_sis.database import initialize_database
from xingyuan_sis.seed_data import seed_demo
from xingyuan_sis.tui import app, keys, portal, screen, workspace, workspace_view
from xingyuan_sis.tui.workspace_data import Catalog


class ResponsiveContractTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'test.db'
        initialize_database(self.db)
        seed_demo(self.db)
        self.catalog = Catalog(self.db)
        self.identity = Identity('Administrator', 'admin')

    def test_portal_down_selects_the_next_visible_row(self):
        for size in ((34, 18), (49, 24), (100, 7)):
            with self.subTest(size=size), patch.object(screen, '_terminal_size', return_value=os.terminal_size(size)), \
                 patch.object(screen, '_paint'), patch.object(screen, '_clear'), \
                 patch.object(keys, '_read_key', side_effect=['down', 'select']):
                action = app._portal_home(self.db, selected=1, preferences={
                    'identity': self.identity, 'portal_focus': 'secondary', 'animate': False,
                })
                self.assertEqual(action, 'workspace:departments')

    def test_every_portal_selection_is_visible_and_clickable_after_resize(self):
        for size in ((26, 8), (34, 12), (49, 9), (100, 7), (100, 24)):
            for index in range(7):
                with self.subTest(size=size, selected=index), \
                     patch.object(screen, '_terminal_size', return_value=os.terminal_size(size)):
                    frame = portal.frame(self.identity, 1, 'secondary', {1: index}, {}, 0, animate=False)
                    selected = next(r for r in frame.regions if r.action == f'secondary:{index}')
                    self.assertLess(selected.y, size[1])
                    self.assertIn(portal.secondary_items(self.identity, 1)[index].label, frame.lines[selected.y - 1])
                    self.assertEqual(screen._hit_action(keys.MouseClick(selected.x, selected.y), frame.regions), selected.action)

    def test_click_at_single_pane_boundary_opens_inspector(self):
        state = workspace.Workspace('students')
        with patch.object(screen, '_terminal_size', return_value=os.terminal_size((76, 24))), \
             patch.object(screen, '_paint'), patch.object(keys, '_read_key', side_effect=['row:1', 'refresh']):
            workspace._interact(state, self.catalog)
            self.assertTrue(state.details)
            frame = workspace_view.render(state, self.catalog)
            self.assertIn('档案', '\n'.join(frame.lines))

    def test_compact_detail_focus_is_visible_and_enter_edits_that_field(self):
        state = workspace.Workspace('students')
        with patch.dict(os.environ, {'NO_COLOR': '1'}), \
             patch.object(screen, '_terminal_size', return_value=os.terminal_size((30, 12))), \
             patch.object(screen, '_paint') as paint, \
             patch.object(keys, '_read_key', side_effect=['right', 'end', 'select']):
            event = workspace._interact(state, self.catalog)
        self.assertEqual(event[0], 'field')
        self.assertEqual(state.form.fields[event[1]].key, 'notes')
        self.assertTrue(any('› 备注' in line for line in paint.call_args_list[-1].args[0]))

    def test_narrow_workspace_keeps_every_filter_clickable(self):
        with patch.object(screen, '_terminal_size', return_value=os.terminal_size((30, 24))):
            for key in ('courses', 'grades'):
                state = workspace.Workspace(key, view=2)
                frame = workspace_view.render(state, self.catalog)
                self.assertTrue({'view:0', 'view:1', 'view:2'} <= {r.action for r in frame.regions})

    def test_no_color_roster_has_a_visible_selected_record(self):
        with patch.dict(os.environ, {'NO_COLOR': '1'}), \
             patch.object(screen, '_terminal_size', return_value=os.terminal_size((120, 35))):
            frame = workspace_view.render(workspace.Workspace('students', selected=1), self.catalog)
        selected = next(r for r in frame.regions if r.action == 'row:1')
        self.assertIn(self.catalog.records['students'][1]['name'], frame.lines[selected.y - 1])
        self.assertNotIn('\x1b', ''.join(frame.lines))

    def test_related_return_restores_identity_and_inspector_context_after_reordering(self):
        state = workspace.Workspace('students', selected=1, details=True, detail_selected=2, detail_scroll=3)
        original = state.current(self.catalog).copy()
        key, related = self.catalog.related(state.key, original)
        state.visit(key, str(related[0]['id']), self.catalog)
        self.catalog.service.update_student_by_no(original['student_no'], student_no='99999999')
        self.catalog.refresh()
        state.restore(self.catalog)
        self.assertEqual(state.current(self.catalog)['id'], original['id'])
        self.assertTrue(state.details)
        self.assertEqual((state.detail_selected, state.detail_scroll), (2, 3))
