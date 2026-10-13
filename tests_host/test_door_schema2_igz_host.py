# SPDX-License-Identifier: GPL-3.0-or-later
"""Schema-1 door .igz round-trip and independent 2D/3D geometry on the real host."""
import copy
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QVector3D
from core.scene import Scene
from formats import igz

from OpenTrace_BIM.door_window_commands import CreateHostedFill, EditHostedFill
from OpenTrace_BIM.door_window_core import (
    normalize_fill, opening_request, door_leaf_plan,
)
from OpenTrace_BIM.door_window_geometry import build_fill_parts
from OpenTrace_BIM.model import DEFAULTS, KEY, make_wall_segment, read_wall


def vertices(part):
    return tuple(tuple(v.position.toTuple()) for face in part.mesh.faces
                 for v in face.loop)


class DoorSchema2HostTests(unittest.TestCase):
    def test_model_angle_does_not_follow_plan_angle(self):
        base = {"schema": 2, "id": "door", "kind": "door", "host_id": "wall",
                "opening_id": "opening", "position": 2.0}
        closed = build_fill_parts(dict(base, plan_angle=90, model_angle=0))[-1]
        other_plan = build_fill_parts(dict(base, plan_angle=15, model_angle=0))[-1]
        opened = build_fill_parts(dict(base, plan_angle=90, model_angle=45))[-1]
        self.assertEqual(vertices(closed), vertices(other_plan))
        self.assertNotEqual(vertices(closed), vertices(opened))
        self.assertEqual(door_leaf_plan(dict(base, plan_angle=90, model_angle=0)),
                         door_leaf_plan(dict(base, plan_angle=90, model_angle=45)))

    def test_schema1_igz_reopens_migrates_and_undoes(self):
        wall = make_wall_segment(
            QVector3D(0, 0, 0), QVector3D(5, 0, 0),
            dict(DEFAULTS, length=5.0))
        scene = Scene()
        scene.groups.append(wall)
        legacy = {"schema": 1, "id": "door-legacy", "kind": "door",
                  "host_id": wall.uid, "opening_id": "opening-legacy",
                  "ifc_global_id": "DoorGuidExisting", "position": 2.0,
                  "anchor": "center", "width": 0.9, "height": 2.1,
                  "sill": 0.2, "open_angle": 45, "extension": {"keep": True}}
        create = CreateHostedFill(scene, wall, legacy)
        create.do(scene)
        old_cut = copy.deepcopy(read_wall(wall)["openings"][0])
        original_guid = create.group.ifc["global_id"]
        original_uid = create.group.uid
        # Represent a real saved schema-1 project rather than falsely
        # claiming the constructor itself still emits schema-1 records.
        create.group.ext[KEY]["params"] = copy.deepcopy(legacy)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy-door.igz"
            igz.save_scene(scene, path)
            reopened = Scene()
            igz.load_into(reopened, path)

        loaded_wall = next(g for g in reopened.groups if g.uid == wall.uid)
        loaded_door = next(g for g in reopened.groups if g.uid == original_uid)
        self.assertEqual(loaded_door.ext[KEY]["params"]["schema"], 1)
        migrated = normalize_fill(loaded_door.ext[KEY]["params"])
        self.assertEqual(migrated["schema"], 2)
        self.assertEqual(migrated["plan_angle"], 45)
        self.assertEqual(migrated["model_angle"], 45)
        self.assertEqual(migrated["extension"], {"keep": True})
        self.assertEqual(migrated["ifc_global_id"], original_guid)
        self.assertEqual(read_wall(loaded_wall)["openings"][0], old_cut)
        expected_cut = opening_request(migrated, opening_guid=old_cut["ifc_global_id"])
        self.assertEqual(expected_cut["position"], old_cut["position"])
        self.assertEqual(expected_cut["width"], old_cut["width"])
        self.assertEqual(expected_cut["height"], old_cut["height"])

        migrate = EditHostedFill(reopened, loaded_wall, loaded_door, {})
        migrate.do(reopened)
        self.assertEqual(loaded_door.ext[KEY]["params"]["schema"], 2)
        self.assertEqual(read_wall(loaded_wall)["openings"][0], old_cut)
        self.assertEqual(loaded_door.uid, original_uid)
        self.assertEqual(loaded_door.ifc["global_id"], original_guid)
        migrate.undo(reopened)
        self.assertEqual(loaded_door.ext[KEY]["params"]["schema"], 1)
        self.assertEqual(read_wall(loaded_wall)["openings"][0], old_cut)
        migrate.do(reopened)
        self.assertEqual(loaded_door.ext[KEY]["params"]["schema"], 2)


if __name__ == "__main__":
    unittest.main()
