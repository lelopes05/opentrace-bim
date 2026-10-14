# SPDX-License-Identifier: GPL-3.0-or-later
"""P1a hosted F01 door: real IngeTrazo window, history, .igz and IFC4."""
import gc
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication
from core.scene import Scene
from formats import igz

from OpenTrace_BIM.door_window_commands import EditHostedFill, _fill_record
from OpenTrace_BIM.door_window_core import station_span, wallhole_size, wallhole_span
from OpenTrace_BIM.host import activate_select, activate_tool
from OpenTrace_BIM.ifc_export import export_ifc
from OpenTrace_BIM.model import DEFAULTS, KEY, make_wall_segment, read_wall
from OpenTrace_BIM.wall_face import WallFace


APP = QApplication.instance() or QApplication([])


class DoorP1aHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from views.extension_api import ExtensionApp
        from views.main_window import MainWindow
        from OpenTrace_BIM import setup

        cls.window = MainWindow()
        cls.app = ExtensionApp(cls.window, "OpenTrace_BIM")
        setup(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.window.deleteLater()
        APP.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()
        del cls.app
        del cls.window
        gc.collect()

    def setUp(self):
        self.viewport = self.window.viewport
        self.scene = self.viewport.scene
        self.baseline = list(self.scene.groups)
        self.wall = make_wall_segment(
            QVector3D(0, 0, 0), QVector3D(8, 0, 0),
            dict(DEFAULTS, length=8.0))
        self.scene.groups.append(self.wall)
        self.scene.version += 1
        self.tool = self.window._arquitetura_parametrica_controller.openings.door_tool
        self.saved_size = dict(self.tool.sizes["door"])
        self.saved_anchor = self.tool.anchor
        self.tool.sizes["door"].update(width=0.80, height=2.10, sill=0.0)
        self.tool.anchor = "center"

    def tearDown(self):
        activate_select(self.app)
        self.app.release_pick()
        self.tool.sizes["door"].update(self.saved_size)
        self.tool.anchor = self.saved_anchor
        self.scene.selection.clear()
        self.scene.groups[:] = [g for g in self.scene.groups
                                if any(g is before for before in self.baseline)]
        self.scene.version += 1
        APP.processEvents()

    def _place(self, station=3.0, anchor="center"):
        self.tool.anchor = anchor
        activate_select(self.app)
        activate_tool(self.app, "opentrace_wall_door_tool")
        self.assertIs(self.viewport.active_tool, self.tool)
        point = WallFace(self.wall).world(QVector3D(station, 1.0, 0))
        self.tool.on_click(SimpleNamespace(
            viewport=self.viewport, world=point, screen=QPointF(0, 0),
            snap=None, modifiers=Qt.NoModifier))
        openings = read_wall(self.wall)["openings"]
        self.assertEqual(len(openings), 1)
        fills = [g for g in self.scene.groups if _fill_record(g) is not None
                 and _fill_record(g).get("host_id") == self.wall.uid]
        self.assertEqual(len(fills), 1)
        return openings[0], fills[0]

    def _opening(self):
        return read_wall(self.wall)["openings"][0]

    @staticmethod
    def _geometry_min_x(group):
        return min(v.position.x() for face in group.children[0].mesh.faces
                   for v in face.loop)

    def test_real_click_creates_schema2_rough_cut_and_one_undo(self):
        opening, group = self._place()
        params = group.ext[KEY]["params"]
        self.assertEqual(params["schema"], 2)
        self.assertEqual(group.ext[KEY]["schema"], 2)
        self.assertEqual(params["family_key"], "swing_single")
        self.assertEqual((params["plan_angle"], params["model_angle"]), (90, 0))
        self.assertAlmostEqual(params["width"], 0.80, places=6)
        self.assertEqual(params["f01_layout"], "physical")
        self.assertAlmostEqual(params["frame_thickness"], 0.04, places=6)
        self.assertAlmostEqual(params["operating_gap_left"], 0.003, places=6)
        self.assertAlmostEqual(opening["width"], 0.966, places=6)
        self.assertAlmostEqual(opening["height"], 2.183, places=6)
        self.assertAlmostEqual(self._geometry_min_x(group), 0.04, places=6)
        self.assertEqual(opening["source_id"], params["id"])
        self.assertTrue(self.viewport.history.undo())
        self.assertEqual(read_wall(self.wall)["openings"], [])
        self.assertNotIn(group, self.scene.groups)
        self.assertTrue(self.viewport.history.redo())
        self.assertIn(group, self.scene.groups)
        self.assertAlmostEqual(self._opening()["width"], 0.966, places=6)

    def test_resize_command_preserves_center_and_left_rough_anchor(self):
        _, group = self._place()
        params = group.ext[KEY]["params"]
        self.assertAlmostEqual(params["position"], 3.0, places=6)
        self.viewport.history.execute(
            EditHostedFill(self.scene, self.wall, group, {"width": 1.00}))
        cut = self._opening()
        self.assertAlmostEqual(cut["width"], 1.166, places=6)
        self.assertAlmostEqual(cut["position"], 3.0, places=6)
        self.assertAlmostEqual(group.ext[KEY]["params"]["width"], 1.00, places=6)
        self.assertTrue(self.viewport.history.undo())
        self.assertAlmostEqual(self._opening()["width"], 0.966, places=6)

        old = group.ext[KEY]["params"]
        rough_left, _ = wallhole_span(old)
        self.viewport.history.execute(
            EditHostedFill(self.scene, self.wall, group, {
                "anchor": "left", "position": rough_left}))
        left_before = self._opening()["position"] - self._opening()["width"] / 2
        self.assertAlmostEqual(left_before, rough_left, places=6)
        self.viewport.history.execute(
            EditHostedFill(self.scene, self.wall, group, {"width": 1.10}))
        updated = group.ext[KEY]["params"]
        cut = self._opening()
        self.assertEqual(updated["anchor"], "left")
        self.assertAlmostEqual(updated["position"], rough_left, places=6)
        self.assertAlmostEqual(cut["width"], 1.266, places=6)
        self.assertAlmostEqual(cut["position"] - cut["width"] / 2,
                               left_before, places=6)
        self.assertAlmostEqual(station_span(updated)[0], rough_left + 0.083,
                               places=6)
        self.assertTrue(self.viewport.history.undo())
        self.assertAlmostEqual(self._opening()["width"], 0.966, places=6)

    def test_cursor_side_selects_finished_wall_face_without_station_shift(self):
        for side, expected in (("near", "left"), ("far", "right")):
            with self.subTest(side=side):
                activate_select(self.app)
                activate_tool(self.app, "opentrace_wall_door_tool")
                wall_face = WallFace(self.wall)
                point = wall_face.world(QVector3D(3.0, 1.0, 0), side)
                self.tool.on_click(SimpleNamespace(
                    viewport=self.viewport, world=point, screen=QPointF(0, 0),
                    snap=None, modifiers=Qt.NoModifier))
                current = read_wall(self.wall)["openings"][0]
                group = next(g for g in self.scene.groups if _fill_record(g)
                             and _fill_record(g).get("host_id") == self.wall.uid)
                self.assertEqual(group.ext[KEY]["params"]["host_face"], expected)
                self.assertAlmostEqual(current["position"], 3.0, places=6)
                self.assertTrue(self.viewport.history.undo())
                self.assertEqual(read_wall(self.wall)["openings"], [])

    def test_schema2_door_survives_igz_save_and_reload(self):
        opening, group = self._place(anchor="left")
        expected_params = group.ext[KEY]["params"].copy()
        expected_rough = wallhole_size(expected_params)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "door-p1a.igz"
            igz.save_scene(self.scene, path)
            reopened = Scene()
            igz.load_into(reopened, path)
        loaded_wall = next(g for g in reopened.groups if g.uid == self.wall.uid)
        loaded_door = next(g for g in reopened.groups if g.uid == group.uid)
        actual = loaded_door.ext[KEY]["params"]
        self.assertEqual(actual, expected_params)
        self.assertEqual(loaded_door.ext[KEY]["schema"], 2)
        new_opening = read_wall(loaded_wall)["openings"][0]
        self.assertEqual(new_opening, opening)
        self.assertAlmostEqual(new_opening["width"], expected_rough[0], places=6)
        self.assertAlmostEqual(new_opening["height"], expected_rough[1], places=6)

    @staticmethod
    def _step_entities(text):
        return dict(re.findall(r"^#(\d+)=(.*);$", text, re.MULTILINE))

    def _assert_exported_ifc(self, text, opening, group, operation):
        rows = self._step_entities(text)
        doors = [(n, v) for n, v in rows.items() if v.startswith("IFCDOOR(")]
        self.assertEqual(len(doors), 1)
        door_id, door_row = doors[0]
        data = door_row[len("IFCDOOR("):-1].split(",")
        self.assertAlmostEqual(float(data[8]), opening["height"], places=6)
        self.assertAlmostEqual(float(data[9]), opening["width"], places=6)
        self.assertEqual(data[10], ".DOOR.")
        self.assertEqual(data[11], f".{operation}.")
        self.assertEqual(len([v for v in rows.values()
                              if v.startswith("IFCOPENINGELEMENT(")]), 1)
        self.assertEqual(len([v for v in rows.values()
                              if v.startswith("IFCRELVOIDSELEMENT(")]), 1)
        fills = [v for v in rows.values() if v.startswith("IFCRELFILLSELEMENT(")]
        self.assertEqual(len(fills), 1)
        self.assertIn(f"#{door_id}", fills[0])

        psets = [(n, v) for n, v in rows.items()
                 if v.startswith("IFCPROPERTYSET(") and "'OpenTrace_Door'" in v]
        self.assertEqual(len(psets), 1)
        pset_id, pset_row = psets[0]
        self.assertTrue(any(v.startswith("IFCRELDEFINESBYPROPERTIES(")
                            and f"#{door_id}" in v and v.endswith(f",#{pset_id})")
                            for v in rows.values()))
        refs = re.findall(r"#(\d+)", pset_row.split("'OpenTrace_Door'", 1)[1])
        props = {}
        for ref in refs:
            raw = rows[ref]
            match = re.fullmatch(
                r"IFCPROPERTYSINGLEVALUE\('([^']+)',\$,"
                r"IFC(?:REAL|INTEGER|LABEL)\(([^()]*)\),\$\)", raw)
            self.assertIsNotNone(match, raw)
            props[match[1]] = match[2].strip("'")
        spec = group.ext[KEY]["params"]
        expected = {
            "LeafWidth": spec["width"], "LeafHeight": spec["height"],
            "ClearanceLeft": 0.04, "ClearanceRight": 0.04,
            "ClearanceTop": 0.04, "ClearanceBottom": 0.0,
            "PlanAngle": 90.0, "ModelAngle": 0.0,
        }
        for key, value in expected.items():
            self.assertAlmostEqual(float(props[key]), value, places=6)
        self.assertEqual(props["Family"], "F01 swing_single")
        self.assertEqual(props["Schema"], "2")

    def test_ifc_round_trip_reads_rough_size_operation_and_pset(self):
        opening, group = self._place()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "door-p1a.ifc"
            export_ifc(self.app, path, data={
                "export": {"profile": "opentrace",
                           "include_opening_relations": True,
                           "include_property_sets": True}})
            text = path.read_text(encoding="utf-8")
        self._assert_exported_ifc(text, opening, group, "SINGLE_SWING_LEFT")

        self.viewport.history.execute(
            EditHostedFill(self.scene, self.wall, group, {"swing": -1}))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "door-reversed.ifc"
            export_ifc(self.app, path, data={
                "export": {"profile": "opentrace",
                           "include_opening_relations": True,
                           "include_property_sets": True}})
            text = path.read_text(encoding="utf-8")
        self._assert_exported_ifc(
            text, self._opening(), group, "SINGLE_SWING_RIGHT")


if __name__ == "__main__":
    unittest.main()
