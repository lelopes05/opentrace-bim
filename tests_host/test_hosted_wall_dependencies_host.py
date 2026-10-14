# SPDX-License-Identifier: GPL-3.0-or-later
"""P-A1 regression: hosted frames follow thickness edits, including Undo/Redo."""
import copy
import unittest

from PySide6.QtGui import QVector3D
from core.scene import Scene

from OpenTrace_BIM.commands import EditWall
from OpenTrace_BIM.door_window_commands import CreateHostedFill
from OpenTrace_BIM.door_window_geometry import place_fill_on_wall
from OpenTrace_BIM.model import (
    DEFAULTS, KEY, make_arc_wall, make_wall_segment, read_wall, wall_offsets,
)


def jamb_depth(fill):
    jamb = next(part for part in fill.children if part.name == "Marco esquerdo")
    ys = [v.position.y() for v in jamb.mesh.vertices]
    return max(ys) - min(ys)


def origin(fill):
    return fill.xform.map(QVector3D(0, 0, 0))


class HostedWallDependencyTests(unittest.TestCase):
    def test_wall_thickness_regenerates_doors_and_windows_in_one_history_step(self):
        for curved in (False, True):
            for composite in (False, True):
                for kind in ("door", "window"):
                    with self.subTest(curved=curved, composite=composite, kind=kind):
                        settings = dict(DEFAULTS, alignment="left")
                        if composite:
                            settings.update(structure="composite", layers=[
                                {"id": "core", "name": "Core", "role": "core",
                                 "thickness": 0.10},
                                {"id": "finish", "name": "Finish", "role": "finish",
                                 "thickness": 0.02},
                            ])
                        a, b = QVector3D(0, 0, 0), QVector3D(8, 0, 0)
                        wall = (make_arc_wall(a, b, 1.0, settings) if curved
                                else make_wall_segment(a, b, settings))
                        scene = Scene()
                        scene.groups.append(wall)
                        spec = {"id": "fill-1", "opening_id": "opening-1",
                                "host_id": wall.uid, "kind": kind,
                                "position": 3.5, "anchor": "center"}
                        if kind == "door":
                            spec.update(width=0.90, height=2.10, sill=0.0)
                        create = CreateHostedFill(scene, wall, spec)
                        create.do(scene)
                        fill = create.group
                        params = copy.deepcopy(fill.ext[KEY]["params"])
                        opening = copy.deepcopy(read_wall(wall)["openings"])
                        first_origin, first_depth = origin(fill), jamb_depth(fill)
                        identity = (fill.uid, fill.ifc["global_id"],
                                    wall.uid, opening[0]["ifc_global_id"])
                        before_frame = fill.children[0]

                        changed = read_wall(wall)
                        if composite:
                            changed["layers"][1]["thickness"] = 0.18
                        else:
                            changed["thickness"] = 0.30
                        edit = EditWall(scene, wall, changed)
                        edit.do(scene)

                        low, high = wall_offsets(read_wall(wall))
                        self.assertAlmostEqual(jamb_depth(fill), high - low)
                        self.assertNotAlmostEqual(first_depth, high - low)
                        self.assertIs(scene.groups[1], fill)
                        self.assertIsNot(fill.children[0], before_frame)
                        self.assertEqual(fill.ext[KEY]["params"], params)
                        self.assertEqual(read_wall(wall)["openings"], opening)
                        self.assertEqual(
                            (fill.uid, fill.ifc["global_id"], wall.uid,
                             read_wall(wall)["openings"][0]["ifc_global_id"]), identity)
                        expected = place_fill_on_wall(params, wall)
                        self.assertLess((origin(fill) - origin(expected)).length(), 1e-6)
                        grown_origin = origin(fill)
                        # Only the normal (wall-thickness) direction may change.
                        # This detects sliding along either straight or curved
                        # reference paths, not merely a match to rebuilt mesh.
                        from OpenTrace_BIM.model import (
                            _path_cumulative, _point_on_path_distance, path_world,
                        )
                        from OpenTrace_BIM.door_window_core import (
                            wallhole_span, station_span,
                        )
                        points, distances = _path_cumulative(path_world(wall))
                        left, right = (wallhole_span(params) if kind == "door"
                                       else station_span(params))
                        start = _point_on_path_distance(points, distances, left)
                        end = _point_on_path_distance(points, distances, right)
                        tangent = (end-start).normalized()
                        delta = grown_origin-first_origin
                        self.assertAlmostEqual(
                            QVector3D.dotProduct(delta, tangent), 0.0, places=6,
                            msg="thickness edit moved the fill along its station")

                        edit.undo(scene)
                        self.assertAlmostEqual(jamb_depth(fill), first_depth)
                        self.assertLess((origin(fill) - first_origin).length(), 1e-6)
                        self.assertEqual(fill.ext[KEY]["params"], params)
                        self.assertEqual(read_wall(wall)["openings"], opening)

                        edit.do(scene)
                        self.assertAlmostEqual(jamb_depth(fill), high - low)
                        self.assertLess((origin(fill) - grown_origin).length(), 1e-6)
                        self.assertEqual(
                            (fill.uid, fill.ifc["global_id"], wall.uid,
                             read_wall(wall)["openings"][0]["ifc_global_id"]), identity)


if __name__ == "__main__":
    unittest.main()
