# SPDX-License-Identifier: GPL-3.0-or-later
"""Real IngeTrazo host contract for OpenTrace's persistent step messages."""
import gc
import unittest
from types import SimpleNamespace

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from OpenTrace_BIM.host import (
    activate_beam, activate_column, activate_select, activate_slab, activate_wall,
)
from OpenTrace_BIM.step_guide import STEP_HOLD_MS, step_text
from OpenTrace_BIM import model

APP = QApplication.instance() or QApplication([])
_SHARED = {}


def shared_window():
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
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()
    gc.collect()


class GuideHostTests(unittest.TestCase):
    def setUp(self):
        self.window, self.app = shared_window()
        self.viewport = self.app.viewport
        self.scene = self.viewport.scene
        self.original_groups = tuple(self.scene.groups)
        self.wall = self.window._arquitetura_parametrica_controller
        self.slab = self.window._arquitetura_parametrica_slab_controller
        self.column = self.window._arquitetura_parametrica_column_controller
        self.beam = self.window._arquitetura_parametrica_beam_controller
        activate_select(self.app)
        self.scene.clear_selection()
        APP.processEvents()

    def tearDown(self):
        activate_select(self.app)
        self.wall.openings.clear_sticky()
        self.slab.clear_sticky()
        self.app.release_pick()
        self.wall.draw_tool.set_geometry("single")
        self.slab.tool.set_mode("diagonal")
        self.scene.clear_selection()
        for group in list(self.scene.groups):
            if group not in self.original_groups:
                self.scene.groups.remove(group)
        self.scene.version += 1
        APP.processEvents()

    def click(self, xyz):
        q = QVector3D(*xyz)
        ctx = SimpleNamespace(
            viewport=self.viewport, world=q, snap=None, screen=QPointF(0, 0),
            modifiers=Qt.NoModifier)
        self.viewport.active_tool.on_click(ctx)
        APP.processEvents()

    def assert_step(self, identifier):
        current = self.window.statusBar().currentMessage()
        expected = step_text(identifier)
        self.assertIn(expected, current, (identifier, current))
        self.assertEqual(self.viewport.active_tool.status_clause(), expected)

    def test_wall_six_geometries_first_second_and_created(self):
        cases = (
            ("single", "wall.segment.start", "wall.segment.end",
             ((0, 0, 0), (4, 0, 0)), "wall.segment.created"),
            ("rect_diagonal", "wall.rect_diag.choose", "wall.rect_diag.after_first",
             ((0, 0, 0), (4, 3, 0)), "wall.rect_diag.created"),
            ("rect_base_width", "wall.rect_base.choose", "wall.rect_base.after_first",
             ((0, 0, 0), (4, 0, 0), (4, 3, 0)), "wall.rect_base.created"),
            ("arc_normal", "wall.arc_normal.start", "wall.arc_normal.second",
             ((0, 0, 0), (4, 0, 0), (2, 1, 0)), "wall.arc_normal.created"),
            ("arc_center", "wall.arc_center.choose", "wall.arc_center.after_first",
             ((0, 0, 0), (2, 0, 0), (0, 2, 0)), "wall.arc_normal.created"),
            ("arc_three", "wall.arc_three.choose", "wall.arc_three.after_first",
             ((0, 0, 0), (2, 1, 0), (4, 0, 0)), "wall.arc_normal.created"),
        )
        for geometry, start, second, points, created in cases:
            with self.subTest(geometry=geometry):
                activate_wall(self.app)
                self.wall.choose_geometry(geometry)
                self.assert_step(start)
                self.click(points[0])
                self.assert_step(second)
                if geometry == "rect_base_width":
                    self.click(points[1])
                    self.assert_step("wall.rect_base.width")
                    self.click(points[2])
                elif geometry == "arc_normal":
                    self.click(points[1])
                    self.assert_step("wall.arc_normal.bulge")
                    self.click(points[2])
                elif geometry == "arc_center":
                    self.click(points[1])
                    self.assert_step("wall.arc_center.end")
                    self.click(points[2])
                elif geometry == "arc_three":
                    self.click(points[1])
                    self.assert_step("wall.arc_three.end")
                    self.click(points[2])
                else:
                    self.click(points[1])
                self.assert_step(created)
                self.assertEqual(self.wall.draw_tool.geometry, geometry)
                activate_select(self.app)
                for group in list(self.scene.groups):
                    if group not in self.original_groups:
                        self.scene.groups.remove(group)
                self.scene.version += 1

    def test_slab_method_persists_after_commit(self):
        activate_slab(self.app)
        tool = self.slab.tool
        tool.set_mode(tool.MODE_BASE_WIDTH)
        self.assert_step("slab.create.start")
        self.click((0, 0, 0))
        self.assert_step("slab.base.choose")
        self.click((4, 0, 0))
        self.assert_step("slab.base.width")
        self.click((4, 3, 0))
        self.assert_step("slab.diagonal.created")
        self.assertEqual(tool.mode, tool.MODE_BASE_WIDTH)
        self.click((6, 0, 0))
        self.assert_step("slab.base.choose")

    def test_column_and_beam_click_steps(self):
        activate_column(self.app)
        self.assert_step("column.start")
        self.click((0, 0, 0))
        self.assert_step("column.created")
        activate_beam(self.app)
        self.assert_step("beam.start")
        self.click((3, 0, 0))
        self.assert_step("beam.end")
        self.click((6, 0, 0))
        self.assert_step("beam.created")

    def test_old_wall_radials_removed_and_centre_starts_at_centre(self):
        self.assertFalse(hasattr(self.wall, "straight_mode_palette"))
        self.assertFalse(hasattr(self.wall, "curve_mode_palette"))
        activate_wall(self.app)
        self.wall.choose_geometry("arc_center")
        self.assert_step("wall.arc_center.choose")
        self.click((0, 0, 0))
        self.assert_step("wall.arc_center.after_first")

    def test_error_restores_previous_step(self):
        activate_wall(self.app)
        self.wall.choose_geometry("single")
        self.click((0, 0, 0))
        self.assert_step("wall.segment.end")
        self.assertFalse(self.wall.draw_tool.on_value(self.viewport, -3.0))
        self.assert_step("wall.segment.end")

    def test_opening_placement_and_next_target(self):
        from OpenTrace_BIM.host import activate_tool
        from OpenTrace_BIM.wall_face import WallFace
        from OpenTrace_BIM.wall_opening_ui import OPENING_TOOL_KEY
        wall = model.make_wall_segment(
            QVector3D(0, 0, 0), QVector3D(5, 0, 0),
            dict(model.DEFAULTS, length=5.0, openings=[]))
        self.scene.groups.append(wall)
        face = WallFace(wall)
        activate_tool(self.app, OPENING_TOOL_KEY)
        self.assert_step("opening.rect.hover")
        world = face.world(QVector3D(2, 1.4, 0), "near")
        ctx = SimpleNamespace(
            viewport=self.viewport, world=world, snap=None,
            screen=QPointF(0, 0), modifiers=Qt.NoModifier)
        self.viewport.active_tool.on_hover(ctx)
        self.viewport.active_tool.on_click(ctx)
        APP.processEvents()
        self.assert_step("opening.rect.placed")
        self.assertEqual(len(model.read_wall(wall)["openings"]), 1)

    def test_continuous_wall_opening_edit_announces_next_target(self):
        from OpenTrace_BIM.wall_face import WallFace
        opening = {
            "id": "guide-a", "kind": "rect", "position": 2.5,
            "width": 1.0, "height": 1.2, "sill": 0.9,
        }
        wall = model.make_wall_segment(
            QVector3D(0, 0, 0), QVector3D(5, 0, 0),
            dict(model.DEFAULTS, length=5.0, openings=[opening]))
        self.scene.groups.append(wall)
        face = WallFace(wall)
        editor = self.wall.openings
        editor._radial_target = (
            wall, "guide-a", "edge", 1,
            face.world(QVector3D(3, 1.5, 0)))
        editor._run("offset")
        self.assert_step("wall_opening.edit.offset")
        point = face.world(QVector3D(3.2, 1.5, 0))
        self.click((point.x(), point.y(), point.z()))
        APP.processEvents()
        self.assertTrue(editor.sticky.waiting)
        self.assert_step("wall_opening.edit.after")

    def test_continuous_slab_opening_edit_announces_next_target(self):
        from OpenTrace_BIM.slab_model import DEFAULTS, make_slab
        slab = make_slab(
            [QVector3D(0, 0, 0), QVector3D(8, 0, 0),
             QVector3D(8, 6, 0), QVector3D(0, 6, 0)],
            dict(DEFAULTS),
            openings=[{
                "id": "guide-a",
                "polygon": [[2, 2, 0], [3, 2, 0],
                            [3, 3, 0], [2, 3, 0]],
                "edges": [{"type": "line"} for _ in range(4)],
            }])
        self.scene.groups.append(slab)
        self.scene.selection.add(slab)
        ctl = self.slab
        ctl._edit_slab = slab
        ctl._edit_kind = "opening_edge"
        ctl._edit_index = (0, 1)
        ctl._edit_anchor = QVector3D(3, 2.5, 0)
        ctl.begin_offset()
        self.assert_step("slab_opening.edit.offset")
        self.click((3.15, 2.5, 0))
        APP.processEvents()
        self.assertTrue(ctl.sticky.waiting)
        self.assert_step("slab_opening.edit.after")

    def test_hint_outlives_fifteen_seconds_and_closes_cleanly(self):
        self.assertEqual(STEP_HOLD_MS, 600000)
        activate_beam(self.app)
        self.assert_step("beam.start")
        QTest.qWait(15010)
        self.assert_step("beam.start")
        activate_select(self.app)
        self.assertNotIn(step_text("beam.start"),
                         self.window.statusBar().currentMessage())


if __name__ == "__main__":
    unittest.main()
