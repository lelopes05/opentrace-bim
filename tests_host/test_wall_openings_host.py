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
from PySide6.QtWidgets import QApplication
from core.history import History
from core.scene import Scene

from OpenTrace_BIM import model
from OpenTrace_BIM.door_window_commands import CreateHostedFill, _fill_record
from OpenTrace_BIM.wall_face import WallFace
from OpenTrace_BIM.wall_opening_edit import (
    InsertWallOpeningVertexTool, CurveWallOpeningEdgeTool, MoveWallOpeningTool, MoveWallOpeningVertexTool,
    PushWallOpeningEdgeTool,
)
from OpenTrace_BIM.wall_opening_place import (PRESETS, DrawWallOpeningTool,
                                              PlaceWallOpeningTool, WallOpeningTool,
                                              opening_record)


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


APP = QApplication.instance() or QApplication([])  # edits hand back through QTimer

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
        APP.processEvents()
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
        self.assertEqual(item["kind"], "polygon", ctl.messages)
        self.assertEqual([e["type"] for e in item["edges"]].count("arc"), 1)

    def test_insert_vertex_on_a_vertical_edge(self):
        D = {"id": "a", "kind": "polygon",
             "polygon": [[1.0, 0.9], [2.0, 0.9], [2.0, 2.1], [1.0, 2.1]],
             "edges": [{"type": "line"}, {"type": "arc", "sagitta": -0.5},
                       {"type": "line"}, {"type": "line"}]}
        for item in (RECT, D):
            scene, wall = straight([item])
            pts = [QVector3D(s, z, 0) for s, z in
                   ([[2.0, 0.9], [3.0, 0.9], [3.0, 2.1], [2.0, 2.1]] if item is RECT
                    else item["polygon"])]
            left_mid = (pts[3] + pts[0]) * 0.5
            vp, ctl, tool, face = self.arm(InsertWallOpeningVertexTool, scene, wall,
                                           ("a", 3), left_mid)
            click = (pts[3] * 0.65 + pts[0] * 0.35)
            tool.on_hover(ctx(vp, face.world(click)))
            tool.on_click(ctx(vp, face.world(click)))
            self.assertEqual(len(opening(wall)["polygon"]), 5, ctl.messages)

    def test_curved_wall_round_opening_mesh_is_closed(self):
        D = {"id": "a", "kind": "polygon",
             "polygon": [[3.0, 0.9], [4.0, 0.9], [4.0, 2.1], [3.0, 2.1]],
             "edges": [{"type": "line"}, {"type": "arc", "sagitta": -0.5},
                       {"type": "line"}, {"type": "line"}]}
        square = dict(D, edges=[{"type": "line"}] * 4)
        for shape, alignment in ((square, "left"), (D, "left"), (D, "center")):
            wall = model.make_arc_wall(QVector3D(0, 0, 0), QVector3D(8, 0, 0), 2.0,
                                       dict(model.DEFAULTS, alignment=alignment, openings=[shape]))
            for body in wall.children:
                open_edges = [e for e in body.mesh.edges if len(e.faces) != 2]
                detail = [(round(e.v0.position.x(), 3), round(e.v1.position.x(), 3),
                           round(e.v0.position.z(), 2),
                           [f.attrs.get(model.FACE_KEY) for f in e.faces]) for e in open_edges]
                if open_edges:
                    face = WallFace(wall)
                    spans = []
                    for f in body.mesh.faces:
                        if f.attrs.get(model.FACE_KEY) != "bottom":
                            continue
                        st = sorted(round(face.station(v.position), 4) for v in f.loop)
                        spans.append((st[0], st[-1], len(f.loop)))
                    spans.sort()
                    near = [sp for sp in spans if 3.3 < sp[0] < 4.6]
                    detail.append(("bottom spans", near))
                self.assertEqual(open_edges, [], (shape is D, alignment, detail))

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
        tool.set_kind("circle")
        tool.on_click(ctx(vp, face.world(QVector3D(2.0, 1.0, 0))))
        tool.set_kind("door")
        tool.anchor = "left"
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

            # The toolbar path: the button activates the placement tool and the
            # REAL viewport finds the wall under the cursor.
            from OpenTrace_BIM.wall_opening_place import wall_under_cursor
            ctl = window._arquitetura_parametrica_controller
            ctl.openings.tool_actions[0].trigger()
            self.assertIs(window.viewport.active_tool, ctl.openings.opening_tool)
            real = window.viewport
            pixel = real._world_to_pixel(face.world(QVector3D(2.5, 1.5, 0)))
            self.assertIsNotNone(pixel, "test wall is off screen")
            found = wall_under_cursor(real, SimpleNamespace(
                screen=QPointF(*pixel), world=face.world(QVector3D(2.5, 1.5, 0))))
            self.assertIs(found, wall)
        finally:
            window.deleteLater()
            qt.processEvents()


OPENING_KEYS = ("opentrace_wall_opening_tool", "opentrace_wall_door_tool",
                "opentrace_wall_window_tool")


class OpeningToolTests(unittest.TestCase):
    """Opening, Door and Window are host tools, started only by the menu and tool row."""

    def setUp(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from views.extension_api import ExtensionApp
        from views.main_window import MainWindow
        from OpenTrace_BIM import setup
        self.window = MainWindow()
        self.addCleanup(self._close)
        self.app = ExtensionApp(self.window, "OpenTrace_BIM")
        setup(self.app)
        self.ctl = self.window._arquitetura_parametrica_controller
        self.editor = self.ctl.openings

    def _close(self):
        self.window.deleteLater()
        APP.processEvents()

    def _activate(self, key):
        from OpenTrace_BIM.host import activate_tool
        activate_tool(self.app, key)

    def test_opening_tools_are_host_tools(self):
        from OpenTrace_BIM.host import host_tool
        expected = (WallOpeningTool, PlaceWallOpeningTool, PlaceWallOpeningTool)
        for key, cls in zip(OPENING_KEYS, expected):
            self.assertIsInstance(self.window._tools[key], cls)
            action = self.window._tool_actions[key]
            self.assertIn(action, self.window._tool_group.actions())
            self.assertTrue(action.isCheckable())
            self.assertFalse(action.shortcut().toString(), "tools have no keyboard shortcut")
            self._activate(key)
            self.assertTrue(action.isChecked())
            self.assertIs(self.window.viewport.active_tool, host_tool(self.app, key))
        self.assertEqual(self.window._tools[OPENING_KEYS[1]].kind, "door")
        self.assertEqual(self.window._tools[OPENING_KEYS[2]].kind, "window")
        self.assertEqual(self.window._tools[OPENING_KEYS[1]].anchor, "center")
        for old in ("opentrace_wall_opening_place", "opentrace_wall_opening_draw"):
            self.assertNotIn(old, self.window._tools)

    def test_opening_tools_are_in_menu_and_f3(self):
        from OpenTrace_BIM.i18n import t
        from views.command_search import commands
        found = {c.action: c for c in commands(self.window)}
        folder = f"{t('Ferramentas arquitetônicas')} ▸ {t('Vãos')}"
        for action, title in zip(self.editor.tool_actions, ("Abertura", "Porta", "Janela")):
            command = found[action]
            self.assertEqual(command.name, t(title))
            self.assertTrue(command.path.endswith(folder), command.path)

    def test_opening_shape_change_keeps_host_tool(self):
        tool = self.editor.opening_tool
        log = []
        for label, inner in (("place", tool.place), ("draw", tool.draw)):
            for event in ("on_activate", "on_deactivate"):
                original = getattr(inner, event)
                setattr(inner, event,
                        lambda viewport, _o=original, _e=(label, event): (log.append(_e), _o(viewport)))
        self._activate(OPENING_KEYS[0])
        self.assertEqual(log, [("place", "on_activate")])
        previous = "place"
        for shape in ("square", "circle", "free", "rect"):
            log.clear()
            tool.set_shape(shape)
            current = "draw" if shape == "free" else "place"
            self.assertEqual(log, [(previous, "on_deactivate"), (current, "on_activate")])
            self.assertIs(self.window.viewport.active_tool, tool)
            self.assertTrue(self.window._tool_actions[OPENING_KEYS[0]].isChecked())
            if shape != "free":
                self.assertEqual(tool.place.kind, shape)
            previous = current

    def test_each_opening_tool_places_on_real_wall(self):
        scene = self.window.viewport.scene
        history = self.window.viewport.history
        wall = model.make_wall_segment(QVector3D(0, 0, 0), QVector3D(8, 0, 0),
                                       dict(model.DEFAULTS, length=8.0))
        scene.groups.append(wall)
        scene.version += 1
        face = WallFace(wall)

        def click():
            viewport = self.window.viewport
            world = face.world(QVector3D(3.0, 1.0, 0))
            viewport.active_tool.on_click(SimpleNamespace(
                viewport=viewport, world=world, snap=None, screen=QPointF(0, 0), modifiers=None))

        def fills():
            return [g for g in scene.groups if _fill_record(g)]

        for key, shape in ((OPENING_KEYS[0], "rect"), (OPENING_KEYS[0], "square"),
                           (OPENING_KEYS[0], "circle"), (OPENING_KEYS[1], None),
                           (OPENING_KEYS[2], None)):
            with self.subTest(key=key, shape=shape):
                self._activate(key)
                if shape is not None:
                    self.window._tools[key].set_shape(shape)
                click()
                items = model.read_wall(wall)["openings"]
                self.assertEqual(len(items), 1)
                item = items[0]
                if shape == "circle":
                    self.assertEqual(item["kind"], "polygon")
                    self.assertEqual([e["type"] for e in item["edges"]], ["arc"] * 4)
                else:
                    kind = shape or self.window._tools[key].kind
                    self.assertEqual(item["kind"], "rect")
                    self.assertAlmostEqual(item["width"], PRESETS[kind]["width"])
                    self.assertAlmostEqual(item["height"], PRESETS[kind]["height"])
                    self.assertAlmostEqual(item["position"], 3.0, places=6)
                if shape is None:
                    self.assertEqual(len(fills()), 1)
                    self.assertEqual(item["source_id"], _fill_record(fills()[0])["id"])
                else:
                    self.assertEqual(fills(), [])
                self.assertEqual(self.editor.active, (wall, item["id"]))
                self.assertIs(self.window.viewport.active_tool, self.window._tools[key])
                self.assertTrue(history.undo())  # one step undoes opening and fill together
                self.assertEqual(model.read_wall(wall).get("openings", []), [])
                self.assertEqual(fills(), [])

    def test_no_widget_outside_toolrow_and_menu_starts_an_opening(self):
        from PySide6.QtWidgets import QToolButton
        for name in ("begin_hosted_fill", "begin_wall_polygon_from_toolbar",
                     "opening_toolbar_action", "opening_toolbar_menu",
                     "opening_toolbar_button", "opening_btn"):
            self.assertFalse(hasattr(self.ctl, name), name)
        for name in ("begin_place", "begin_draw", "place_tool", "draw_tool"):
            self.assertFalse(hasattr(self.editor, name), name)
        actions = set(self.editor.tool_actions)
        suite = self.window._arquitetura_parametrica_suite_panel
        for root in (self.ctl.toolbar, suite.panel):
            for button in root.findChildren(QToolButton):
                self.assertNotIn(button.defaultAction(), actions)


if __name__ == "__main__":
    unittest.main()

