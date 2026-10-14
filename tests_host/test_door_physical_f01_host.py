# SPDX-License-Identifier: GPL-3.0-or-later
"""Real host meshes for physically dimensioned single-swing F01 doors."""
import copy
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QVector3D
from core.scene import Scene
from formats import igz

from OpenTrace_BIM.commands import EditWall
from OpenTrace_BIM.door_window_core import normalize_fill, wallhole_size
from OpenTrace_BIM.door_window_commands import CreateHostedFill, EditHostedFill
from OpenTrace_BIM.door_window_geometry import build_fill_parts
from OpenTrace_BIM.model import DEFAULTS, KEY, make_wall_segment, read_wall


def spec(**kw):
    data = {"schema": 2, "f01_layout": "physical", "kind": "door",
            "id": "door-a", "host_id": "wall-a", "opening_id": "opening-a",
            "position": 3.0, "anchor": "center", "width": 0.80,
            "height": 2.10, "frame_thickness": 0.04}
    data.update(kw)
    return data


def bounds(part):
    coords = [(v.position.x(), v.position.y(), v.position.z())
              for v in part.mesh.vertices]
    return tuple((min(v[i] for v in coords), max(v[i] for v in coords))
                 for i in range(3))


def named(parts, name):
    return next(p for p in parts if p.name == name)


class F01GeometryHostTests(unittest.TestCase):
    def test_leaf_is_real_800mm_and_assembly_966mm(self):
        parts = build_fill_parts(spec(), wall_thickness=0.15)
        leaf = named(parts, "Folha de abrir")
        lo, hi = bounds(leaf)[0]
        self.assertAlmostEqual(hi - lo, 0.800, places=6)
        self.assertAlmostEqual(lo, 0.083, places=6)
        self.assertAlmostEqual(bounds(named(parts,"Marco esquerdo"))[0][0],
                               0.04, places=6)
        self.assertAlmostEqual(bounds(named(parts,"Marco direito"))[0][1],
                               0.926, places=6)
        self.assertAlmostEqual(wallhole_size(spec())[0], 0.966)
        for label in ("Alizar A esquerdo", "Alizar B esquerdo",
                      "Face A da folha", "Face B da folha"):
            self.assertIn(label, [p.name for p in parts])

    def test_manual_jamb_face_alignment_recess_and_suppressed_trim(self):
        parts = build_fill_parts(spec(frame_depth_mode="manual",
                   frame_depth=0.15, host_face="right", frame_recess=0.02,
                   trim_back_enabled=False), wall_thickness=0.40)
        y0, y1 = bounds(named(parts, "Marco esquerdo"))[1]
        self.assertAlmostEqual(y0, 0.03, places=6)
        self.assertAlmostEqual(y1, 0.18, places=6)
        self.assertIn("Alizar A esquerdo", [p.name for p in parts])
        self.assertNotIn("Alizar B esquerdo", [p.name for p in parts])

    def test_three_variants_have_distinct_manifold_children(self):
        parts = {}
        for variant in ("plain", "grooved", "panelled"):
            parts[variant] = build_fill_parts(
                spec(leaf_variant=variant), wall_thickness=0.20)
            leaf = named(parts[variant], "Folha de abrir")
            self.assertAlmostEqual(bounds(leaf)[0][1] -
                                   bounds(leaf)[0][0], 0.8, places=6)
        self.assertFalse(any(p.name.startswith("Friso ") or
                             p.name.startswith("Almofada ")
                             for p in parts["plain"]))
        self.assertTrue(any(p.name.startswith("Friso ") for p in parts["grooved"]))
        self.assertTrue(any(p.name.startswith("Almofada ") for p in parts["panelled"]))

    def test_independent_materials_round_trip_and_history(self):
        wall = make_wall_segment(QVector3D(0, 0, 0), QVector3D(7, 0, 0),
                                 dict(DEFAULTS, length=7.0))
        scene = Scene()
        scene.groups.append(wall)
        raw = spec(host_id=wall.uid,
                   material_leaf_front={"color": [230, 180, 140]},
                   material_leaf_back={"color": [25, 50, 90]},
                   material_frame={"color": [120, 75, 40]},
                   material_trim_front={"color": [210, 210, 210]},
                   material_trim_back={"color": [65, 65, 65]})
        create=CreateHostedFill(scene, wall, raw)
        create.do(scene)
        door=create.group
        uid=door.uid
        guid=door.ifc["global_id"]
        opening=copy.deepcopy(read_wall(wall)["openings"][0])
        parts=door.children
        self.assertNotEqual(named(parts,"Face A da folha").material,
                            named(parts,"Face B da folha").material)
        self.assertNotEqual(named(parts,"Alizar A esquerdo").material,
                            named(parts,"Alizar B esquerdo").material)
        edit=EditHostedFill(scene, wall, door, {
            "leaf_variant": "panelled", "frame_depth_mode": "manual",
            "frame_depth": 0.16, "host_face": "right",
            "frame_recess": 0.01, "trim_back_enabled": False,
        })
        edit.do(scene)
        self.assertEqual(door.uid, uid)
        self.assertEqual(door.ifc["global_id"], guid)
        self.assertEqual(read_wall(wall)["openings"][0], opening)
        self.assertEqual(door.ext[KEY]["params"]["leaf_variant"], "panelled")
        self.assertFalse(any(p.name.startswith("Alizar B")
                             for p in door.children))
        edit.undo(scene)
        self.assertEqual(door.ext[KEY]["params"]["leaf_variant"], "plain")
        self.assertTrue(any(p.name.startswith("Alizar B")
                            for p in door.children))
        edit.do(scene)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"f01.igz"
            igz.save_scene(scene,path)
            reopened=Scene()
            igz.load_into(reopened,path)
        loaded=next(g for g in reopened.groups if g.uid==uid)
        saved=normalize_fill(loaded.ext[KEY]["params"])
        self.assertEqual(saved["leaf_variant"], "panelled")
        self.assertEqual(saved["frame_depth_mode"], "manual")
        self.assertEqual(saved["host_face"], "right")
        self.assertFalse(saved["trim_back_enabled"])
        self.assertEqual(saved["material_leaf_front"], raw["material_leaf_front"])
        self.assertEqual(saved["material_leaf_back"], raw["material_leaf_back"])
        self.assertEqual(loaded.ifc["global_id"], guid)
        self.assertEqual(read_wall(next(g for g in reopened.groups
                                        if g.uid==wall.uid))["openings"][0], opening)

    def test_manual_depth_follows_wall_face_after_thickness_undo(self):
        wall=make_wall_segment(QVector3D(0,0,0), QVector3D(7,0,0),
                               dict(DEFAULTS, length=7.0, alignment="left"))
        scene=Scene();scene.groups.append(wall)
        create=CreateHostedFill(scene,wall,spec(
            host_id=wall.uid, frame_depth_mode="manual", frame_depth=0.12,
            frame_recess=0.02, host_face="left"))
        create.do(scene)
        door=create.group
        before=door.children[0]
        station=door.ext[KEY]["params"]["position"]
        changed=read_wall(wall)
        changed["thickness"]=0.30
        edit=EditWall(scene,wall,changed)
        edit.do(scene)
        self.assertEqual(door.ext[KEY]["params"]["position"], station)
        self.assertIsNot(door.children[0],before)
        self.assertAlmostEqual(bounds(named(door.children,
                                             "Marco esquerdo"))[1][1]-
                               bounds(named(door.children,
                                             "Marco esquerdo"))[1][0], 0.12)
        grown=tuple(bounds(named(door.children, "Marco esquerdo"))[1])
        edit.undo(scene)
        self.assertEqual(door.ext[KEY]["params"]["position"], station)
        self.assertNotEqual(grown,tuple(bounds(named(door.children,
                                                  "Marco esquerdo"))[1]))
        edit.do(scene)
        self.assertEqual(tuple(bounds(named(door.children,
                                            "Marco esquerdo"))[1]),grown)


if __name__ == "__main__":
    unittest.main()
