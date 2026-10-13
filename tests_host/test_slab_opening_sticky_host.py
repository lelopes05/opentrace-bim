# SPDX-License-Identifier: GPL-3.0-or-later
"""Sticky slab-opening edits with the actual IngeTrazo scene, tools and history."""
import unittest
from types import SimpleNamespace

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence, QMouseEvent, QVector3D
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from OpenTrace_BIM.slab_model import DEFAULTS, make_slab, slab_openings_world
from OpenTrace_BIM.slab_ui import selected_slabs


APP = QApplication.instance() or QApplication([])
_SHARED = {}


def shared_window():
    """One host window per process avoids offscreen Qt icon refcount crashes."""
    if not _SHARED:
        from views.extension_api import ExtensionApp
        from views.main_window import MainWindow
        from OpenTrace_BIM import setup
        window = MainWindow()
        app = ExtensionApp(window, "OpenTrace_BIM")
        setup(app)
        _SHARED.update(window=window, app=app)
    return _SHARED["window"], _SHARED["app"]


def tearDownModule():
    window = _SHARED.pop("window", None)
    _SHARED.clear()
    if window is not None:
        window.deleteLater()
        APP.processEvents()


class StickySlabOpeningTests(unittest.TestCase):
    def setUp(self):
        from OpenTrace_BIM.host import activate_select
        self.window, self.app = shared_window()
        self.controller = self.window._arquitetura_parametrica_slab_controller
        self.viewport = self.window.viewport
        activate_select(self.app)
        self.controller.clear_sticky()
        self.scene = self.viewport.scene
        self.scene.clear_selection()
        self.slab = make_slab(
            [QVector3D(0, 0, 0), QVector3D(8, 0, 0),
             QVector3D(8, 6, 0), QVector3D(0, 6, 0)],
            dict(DEFAULTS),
            openings=[{
                "id": "a", "polygon": [
                    [2, 2, 0], [3, 2, 0], [3, 3, 0], [2, 3, 0]],
                "edges": [{"type": "line"} for _ in range(4)],
            }])
        self.scene.groups.append(self.slab)
        self.scene.selection.add(self.slab)
        self.scene.version += 1
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        self.controller.return_to_select()
        self.scene.clear_selection()
        if self.slab in self.scene.groups:
            self.scene.groups.remove(self.slab)
            self.scene.version += 1

    def _choose_offset(self):
        ctl = self.controller
        ctl._edit_slab = self.slab
        ctl._edit_kind = "opening_edge"
        ctl._edit_index = (0, 1)
        ctl._edit_anchor = QVector3D(3, 2.5, 0)
        ctl.begin_offset()
        self.assertIs(self.viewport.active_tool, ctl.opening_offset_tool)

    def _click_tool(self, point):
        world = QVector3D(*point)
        ctx = SimpleNamespace(viewport=self.viewport, world=world, snap=None,
                              screen=QPointF(0, 0), modifiers=Qt.NoModifier)
        self.viewport.active_tool.on_click(ctx)
        APP.processEvents()

    def _first_commit(self):
        self._choose_offset()
        self._click_tool((3.15, 2.5, 0))
        self.assertTrue(self.controller.sticky.waiting)
        self.assertIn(self.slab, self.scene.selection)

    def _event(self, point=None, pixel=None):
        if pixel is None:
            pixel = self.viewport._world_to_pixel(QVector3D(*point))
        self.assertIsNotNone(pixel)
        q = QPointF(*pixel)
        return QMouseEvent(QEvent.MouseButtonPress, q, q,
                           Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)

    def test_offset_stays_active_after_commit(self):
        initial = len(self.viewport.history.undo_stack)
        self._first_commit()
        opening = slab_openings_world(self.slab)[0]
        left_x = opening["polygon"][3][0]
        self.assertTrue(self.controller.eventFilter(
            self.viewport, self._event((left_x, 2.5, 0))))
        self.assertFalse(self.controller.edit_palette.isVisible())
        self.assertFalse(self.controller.sticky.waiting)
        self.assertIs(self.viewport.active_tool, self.controller.opening_offset_tool)
        self._click_tool((left_x - 0.12, 2.5, 0))
        self.assertTrue(self.controller.sticky.waiting)
        self.assertEqual(len(self.viewport.history.undo_stack) - initial, 2)
        self.assertIn(self.slab, self.scene.selection)

    def test_sticky_function_ends_on_escape_and_space(self):
        from OpenTrace_BIM.host import host_tool
        self._first_commit()
        esc = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        self.assertTrue(self.controller.eventFilter(self.viewport, esc))
        self.assertIs(self.viewport.active_tool, host_tool(self.app, "select"))
        self.assertIsNone(self.controller.sticky.tool)

        self._first_commit()
        select_action = self.window._tool_actions["select"]
        self.assertIn(QKeySequence(Qt.Key_Space), select_action.shortcuts())
        self.window.show()
        APP.processEvents()
        self.window.activateWindow()
        self.viewport.setFocus()
        APP.processEvents()
        QTest.keyClick(self.viewport, Qt.Key_Space)
        APP.processEvents()
        self.assertIs(self.viewport.active_tool, host_tool(self.app, "select"))
        self.assertIsNone(self.controller.sticky.tool)

    def _click_viewport(self, pos):
        vp = self.viewport
        self.assertGreaterEqual(pos.x(), 0)
        self.assertGreaterEqual(pos.y(), 0)
        self.assertLess(pos.x(), vp.width())
        self.assertLess(pos.y(), vp.height())
        QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, pos)
        APP.processEvents()

    def _blank_pixel(self):
        vp = self.viewport
        for x, y in ((8, 8), (vp.width() - 8, 8),
                     (8, vp.height() - 8),
                     (vp.width() - 8, vp.height() - 8)):
            if vp.pick_group(x, y) is None:
                return QPoint(x, y)
        self.fail("No empty viewport pixel available")

    def test_empty_click_keeps_sticky_function(self):
        self._first_commit()
        tool = self.controller.opening_offset_tool
        history_length = len(self.viewport.history.undo_stack)
        self._click_viewport(self._blank_pixel())
        self.assertIs(self.viewport.active_tool, tool)
        self.assertIs(self.controller.sticky.tool, tool)
        self.assertTrue(self.controller.sticky.waiting)
        self.assertEqual(len(self.viewport.history.undo_stack), history_length)

    def test_click_on_slab_face_outside_opening_keeps_sticky_function(self):
        self._first_commit()
        tool = self.controller.opening_offset_tool
        xy = self.viewport._world_to_pixel(QVector3D(1, 1, 0))
        self.assertIsNotNone(xy)
        pos = QPoint(round(xy[0]), round(xy[1]))
        self.assertIs(self.viewport.pick_group(pos.x(), pos.y()), self.slab)
        self._click_viewport(pos)
        self.assertIs(self.viewport.active_tool, tool)
        self.assertIs(self.controller.sticky.tool, tool)
        self.assertTrue(self.controller.sticky.waiting)

    def test_host_slab_selection_clears_after_edit_space_and_empty_click(self):
        """The slab opening overlay is derived from the host slab selection."""
        from OpenTrace_BIM.host import host_tool
        vp = self.viewport
        self.window.show()
        APP.processEvents()
        self.window.activateWindow()
        vp.setFocus()
        APP.processEvents()

        self.assertIn(self.slab, self.scene.selection)
        self._first_commit()
        self.assertIsNone(vp.extension_pick,
                          "Slab openings use the host's native slab selection.")
        self.assertEqual(selected_slabs(self.scene), [self.slab])
        QTest.keyClick(vp, Qt.Key_Space)
        APP.processEvents()
        self.assertIs(vp.active_tool, host_tool(self.app, "select"))

        self._click_viewport(self._blank_pixel())
        self.assertNotIn(self.slab, self.scene.selection)
        self.assertEqual(selected_slabs(self.scene), [],
                         "The plugin must follow the host's cleared selection.")

    def test_choosing_another_function_replaces_the_sticky_one(self):
        self._first_commit()
        self.controller._edit_slab = self.slab
        self.controller._edit_kind = "opening_edge"
        self.controller._edit_index = (0, 1)
        self.controller._edit_anchor = QVector3D(3.15, 2.5, 0)
        self.controller.begin_curve_edge()
        self.assertIs(self.controller.sticky.tool, self.controller.opening_curve_tool)
        self.assertFalse(self.controller.sticky.waiting)
        self._click_tool((3.25, 2.5, 0))
        self.assertTrue(self.controller.sticky.waiting)
        self.assertIs(self.viewport.active_tool, self.controller.opening_curve_tool)


if __name__ == "__main__":
    unittest.main()
