# SPDX-License-Identifier: GPL-3.0-or-later
"""Wall openings edited like slab openings, on straight and curved walls.

Runs the real tools against IngeTrazo's Scene and History; the viewport is a
front-view stand-in (x → right, z → up), so clicks are world points.
"""
import math
import unittest
from types import SimpleNamespace

from PySide6.QtCore import QPointF
from PySide6.QtGui import QVector3D
from core.history import History
from core.scene import Scene

from OpenTrace_BIM import model
from OpenTrace_BIM.door_window_commands import CreateHostedFill, _fill_record
from OpenTrace_BIM.wall_face import WallFace
from OpenTrace_BIM.wall_opening_edit import (
    CurveWallOpeningEdgeTool, MoveWallOpeningTool, MoveWallOpeningVertexTool,
    PushWallOpeningEdgeTool,
)
from OpenTrace_BIM.wall_opening_place import (PRESETS, DrawWallOpeningTool,
                                              PlaceWallOpeningTool, opening_record)


class Viewport:
    snap_threshold_px = 10.0
    extension_pick = None

    def __init__(self, scene, wall_under_cursor=None):
        self.scene = scene
        self.history = History(scene)
        self._wall = wall_under_cursor

    def notify_scene_changed(self):
        pass

    def update(self):
        pass

    def pick_group(self, x, y):
        return self._wall

    def _world_to_pixel(self, p):
        return (p.x() * 100.0, -p.z() * 100.0)


class Controller:
    def __init__(self):
        self.messages, self.finished, self.selected = [], [], []

    def message(self, text, error=False):
        self.messages.append((text, error))

    def edit_finished(self, wall, oid):
        self.finished.append((wall, oid))

    def select_opening(self, wall, oid):
        self.selected.append((wall, oid))

    def return_to_select(self):
        pass


def ctx(viewport, world):
    pixel = viewport._world_to_pixel(world)
    return SimpleNamespace(viewport=viewport, world=QVector3D(world), snap=None,
                           screen=QPointF(*pixel), modifiers=None)


def straight(openings=()):
    wall = model.make_wall_segment(QVector3D(0, 0, 0), QVector3D(5, 0, 0),
                                   dict(model.DEFAULTS, length=5.0, openings=list(openings)))
    scene = Scene()
    scene.groups.append(wall)
    return scene, wall


def curved(openings=()):
    wall = model.make_arc_wall(QVector3D(0, 0, 0), QVector3D(8, 0, 0), 2.0,
                               dict(model.DEFAULTS, openings=list(openings)))
    scene = Scene()
    scene.groups.append(wall)
    return scene, wall


RECT = {"id": "a", "kind": "rect", "position": 2.5, "width": 1.0, "sill": 0.9, "height": 1.2}


def opening(wall, oid="a"):
    return next(o for o in model.read_wall(wall)["openings"] if o["id"] == oid)


class WallFaceTests(unittest.TestCase):
    def test_sheet_and_world_round_trip(self):
        for build in (straight, curved):
            _scene, wall = build()
            face = WallFace(wall)
            for s, z in ((0.5, 0.3), (2.0, 1.7), (face.length - 0.2, 2.5)):
                back = face.sheet(face.world(QVector3D(s, z, 0)))
                self.assertAlmostEqual(back.x(), s, places=5)
                self.assertAlmostEqual(back.y(), z, places=5)

    def test_outline_follows_the_curve_not_its_chord(self):
        _scene, wall = curved()
        face = WallFace(wall)
        centre = model.arc_center_world(wall)
        top = [QVector3D(2.0, 2.0, 0), QVector3D(4.0, 2.0, 0)]
        from OpenTrace_BIM.wall_opening_edit import sheet_lines
        radii = [math.hypot(p.x() - centre.x(), p.y() - centre.y())
                 for a, b in sheet_lines(face, [tuple(top)]) for p in (a, b)]
        self.assertGreater(len(radii), 4)
        self.assertLess(max(radii) - min(radii), 1e-3)


class EditToolTests(unittest.TestCase):
    def arm(self, tool_cls, scene, wall, token, sheet_anchor):
        vp = Viewport(scene)
        ctl = Controller()
        tool = tool_cls(ctl)
        face = WallFace(wall)
        tool.arm(wall, token, face.world(sheet_anchor))
        return vp, ctl, tool, face

    def test_push_edge_keeps_a_rectangle_and_undoes(self):
        scene, wall = straight([RECT])
        vp, ctl, tool, face = self.arm(PushWallOpeningEdgeTool, scene, wall, ("a", 1),
                                       QVector3D(3.0, 1.5, 0))
        tool.on_click(ctx(vp, face.world(QVector3D(3.3, 1.5, 0))))
        item = opening(wall)
        self.assertEqual(item["kind"], "rect")
        self.assertAlmostEqual(item["width"], 1.3, places=6)
        self.assertAlmostEqual(item["position"], 2.65, places=6)
        self.assertEqual(ctl.finished, [(wall, "a")])
        vp.history.undo()
        self.assertAlmostEqual(opening(wall)["width"], 1.0, places=6)

    def test_moving_one_corner_turns_a_free_opening_into_a_polygon(self):
        scene, wall = straight([RECT])
        vp, ctl, tool, face = self.arm(MoveWallOpeningVertexTool, scene, wall, ("a", 2),
                                       QVector3D(3.0, 2.1, 0))
        tool.on_hover(ctx(vp, face.world(QVector3D(3.2, 2.4, 0))))
        tool.on_click(ctx(vp, face.world(QVector3D(3.2, 2.4, 0))))
        item = opening(wall)
        self.assertEqual(item["kind"], "polygon")
        self.assertEqual(item["id"], "a")
        self.assertIn([3.2, 2.4], [[round(s, 6), round(z, 6)] for s, z in item["polygon"]])

    def test_curved_edge_cuts_the_wall(self):
        scene, wall = curved([dict(RECT, position=4.0)])
        values = model.read_wall(wall)
        from OpenTrace_BIM.wall_opening_edit import outline
        pts, _specs = outline(wall, values, values["openings"][0])
        mid_top = (pts[2] + pts[3]) * 0.5
        vp, ctl, tool, face = self.arm(CurveWallOpeningEdgeTool, scene, wall, ("a", 2), mid_top)
        tool.on_click(ctx(vp, face.world(mid_top + QVector3D(0, 0.25, 0))))
        item = opening(wall)
        self.assertEqual(item["kind"], "polygon")
        self.assertEqual([e["type"] for e in item["edges"]].count("arc"), 1)
        self.assertFalse([m for m in ctl.messages if m[1]])

    def test_door_keeps_its_rectangle(self):
        scene, wall = straight()
        create = CreateHostedFill(scene, wall, {
            "id": "door", "host_id": wall.uid, "opening_id": "a", "kind": "door",
            "anchor": "center", "position": 2.5, "width": 0.9, "height": 2.1, "sill": 0.0})
        create.do(scene)
        vp, ctl, tool, face = self.arm(MoveWallOpeningVertexTool, scene, wall, ("a", 2),
                                       QVector3D(2.95, 2.1, 0))
        tool.on_click(ctx(vp, face.world(QVector3D(3.1, 2.3, 0))))
        self.assertEqual(opening(wall)["kind"], "rect")
        self.assertTrue(any(error for _t, error in ctl.messages))
        # Pushing the head up resizes the door itself.
        vp, ctl, tool, face = self.arm(PushWallOpeningEdgeTool, scene, wall, ("a", 2),
                                       QVector3D(2.5, 2.1, 0))
        tool.on_click(ctx(vp, face.world(QVector3D(2.5, 2.2, 0))))
        params = _fill_record(create.group)["params"]
        self.assertAlmostEqual(params["height"], 2.2, places=6)
        self.assertAlmostEqual(opening(wall)["height"], 2.2, places=6)

    def test_move_slides_along_a_curved_wall(self):
        scene, wall = curved([dict(RECT, position=3.0)])
        vp = Viewport(scene)
        ctl = Controller()
        tool = MoveWallOpeningTool(ctl)
        face = WallFace(wall)
        tool.arm(wall, "a", face.world(QVector3D(3.0, 1.5, 0)))
        tool.on_click(ctx(vp, face.world(QVector3D(4.0, 1.7, 0))))
        item = opening(wall)
        self.assertAlmostEqual(item["position"], 4.0, places=3)
        self.assertAlmostEqual(item["sill"], 1.1, places=6)


class PlacementTests(unittest.TestCase):
    def test_one_click_places_on_the_wall_under_the_cursor(self):
        scene, wall = straight()
        vp = Viewport(scene, wall_under_cursor=wall)
        ctl = Controller()
        tool = PlaceWallOpeningTool(ctl)
        tool.prepare("rect")
        face = WallFace(wall)
        tool.on_click(ctx(vp, face.world(QVector3D(3.0, 1.0, 0))))
        item = model.read_wall(wall)["openings"][0]
        self.assertAlmostEqual(item["position"], 3.0, places=6)
        self.assertAlmostEqual(item["sill"], PRESETS["rect"]["sill"])
        self.assertEqual(ctl.selected, [(wall, item["id"])])

    def test_circle_and_door_presets(self):
        scene, wall = curved()
        vp = Viewport(scene, wall_under_cursor=wall)
        ctl = Controller()
        tool = PlaceWallOpeningTool(ctl)
        face = WallFace(wall)
        tool.prepare("circle")
        tool.on_click(ctx(vp, face.world(QVector3D(2.0, 1.0, 0))))
        tool.prepare("door", "left")
        tool.on_click(ctx(vp, face.world(QVector3D(5.0, 1.0, 0))))
        self.assertFalse([m for m in ctl.messages if m[1]], ctl.messages)
        ops = model.read_wall(wall)["openings"]
        self.assertEqual([o["kind"] for o in ops], ["polygon", "rect"])
        self.assertEqual([e["type"] for e in ops[0]["edges"]], ["arc"] * 4)
        self.assertAlmostEqual(ops[1]["position"] - ops[1]["width"] / 2, 5.0, places=3)
        self.assertEqual(sum(1 for g in scene.groups if _fill_record(g)), 1)

    def test_circle_record_is_a_closed_round_cut(self):
        item = opening_record("circle", 1.0, PRESETS["circle"])
        scene, wall = straight([item])
        stations = [s for s, _z in model.read_wall(wall)["openings"][0]["polygon"]]
        self.assertAlmostEqual(min(stations), 1.0)
        self.assertAlmostEqual(max(stations), 1.0 + PRESETS["circle"]["width"])

    def test_free_opening_is_drawn_corner_by_corner(self):
        scene, wall = straight()
        vp = Viewport(scene, wall_under_cursor=wall)
        ctl = Controller()
        tool = DrawWallOpeningTool(ctl)
        tool.on_activate(vp)
        face = WallFace(wall)
        corners = [(1.0, 0.5), (2.0, 0.5), (1.5, 1.5)]
        for s, z in corners + corners[:1]:
            tool.on_click(ctx(vp, face.world(QVector3D(s, z, 0))))
        item = model.read_wall(wall)["openings"][0]
        self.assertEqual(item["kind"], "polygon")
        self.assertEqual(len(item["polygon"]), 3)


class SelectionTests(unittest.TestCase):
    def test_one_click_picks_any_opening_without_selecting_its_wall(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from views.main_window import MainWindow
        from views.extension_api import ExtensionApp
        from OpenTrace_BIM import setup
        qt = QApplication.instance() or QApplication([])
        window = MainWindow()
        try:
            setup(ExtensionApp(window, "OpenTrace_BIM"))
            editor = window._arquitetura_parametrica_controller.openings
            scene = window.viewport.scene
            _s, wall = straight([RECT, {"id": "b", "kind": "rect", "position": 4.2,
                                        "width": 0.6, "sill": 1.0, "height": 1.0}])
            scene.groups.append(wall)
            scene.version += 1
            vp = Viewport(scene)
            face = WallFace(wall)
            px, py = vp._world_to_pixel(face.world(QVector3D(2.5, 0.9, 0)))
            self.assertEqual(editor._pick(vp, px, py), (wall.uid, "a"))
            px, py = vp._world_to_pixel(face.world(QVector3D(4.2, 1.5, 0)))
            self.assertEqual(editor._pick(vp, px, py), (wall.uid, "b"))  # inside the hole
            px, py = vp._world_to_pixel(face.world(QVector3D(0.5, 0.5, 0)))
            self.assertIsNone(editor._pick(vp, px, py))
        finally:
            window.deleteLater()
            qt.processEvents()


if __name__ == "__main__":
    unittest.main()
