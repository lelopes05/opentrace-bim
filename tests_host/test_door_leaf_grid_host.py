# SPDX-License-Identifier: GPL-3.0-or-later
"""Host integration of glazed/solid/ventilated F01 leafs and history."""
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication
from core.scene import Scene
from formats import igz

from OpenTrace_BIM.door_window_geometry import build_fill_parts
from OpenTrace_BIM.door_window_core import wallhole_size
from OpenTrace_BIM.door_window_commands import CreateHostedFill, EditHostedFill
from OpenTrace_BIM.door_leaf_editor import DoorLeafGridDialog
from OpenTrace_BIM.model import DEFAULTS, KEY, make_wall_segment, read_wall


def door(**kw):
    data = {"schema": 2, "f01_layout": "physical", "kind": "door",
            "id": "door-grid", "host_id": "wall-grid",
            "opening_id": "opening-grid", "position": 3.0,
            "width": 0.90, "height": 2.1, "leaf_variant": "grid"}
    data.update(kw)
    return data


class DoorLeafGridHostTests(unittest.TestCase):
    def test_actual_glass_open_panels_and_hinge_rotation(self):
        grid = {"columns": 2, "rows": 2,
                "cell_types": ["glass", "solid", "louver", "open"]}
        data = door(leaf_grid=grid, model_angle=0)
        parts = build_fill_parts(data, wall_thickness=0.15)
        self.assertFalse(any(p.name == "Folha de abrir" for p in parts))
        self.assertTrue(any(p.name.startswith("Painel 1-1") for p in parts))
        self.assertTrue(any(p.name.startswith("Painel 1-2") for p in parts))
        self.assertFalse(any(p.name.startswith("Painel 2-2") for p in parts))
        self.assertTrue(any("régua" in p.name for p in parts))
        glass = next(p for p in parts if
                     p.ext.get("opentrace_component") == "leaf_glass")
        ys = [v.position.y() for v in glass.mesh.vertices]
        self.assertAlmostEqual(max(ys)-min(ys), 0.008, places=5)
        self.assertLess(glass.material["opacity"], 1)
        turned = build_fill_parts(
            dict(data, model_angle=90), wall_thickness=0.15)
        original = next(p for p in parts if p.name == "Montante lateral E")
        rotated = next(p for p in turned if p.name == "Montante lateral E")
        before = [(v.position.x(), v.position.y())
                  for v in original.mesh.vertices]
        after = [(v.position.x(), v.position.y())
                 for v in rotated.mesh.vertices]
        self.assertNotEqual(before, after)

    def test_history_and_igz_keep_leaf_design_and_wall_opening(self):
        wall = make_wall_segment(
            QVector3D(0, 0, 0), QVector3D(7, 0, 0),
            dict(DEFAULTS, length=7.0))
        scene = Scene()
        scene.groups.append(wall)
        created = CreateHostedFill(scene, wall, door(host_id=wall.uid))
        created.do(scene)
        obj = created.group
        original_children = [p.name for p in obj.children]
        original_uid = obj.uid
        original_guid = obj.ifc["global_id"]
        original_opening = read_wall(wall)["openings"][0].copy()
        edited = EditHostedFill(scene, wall, obj, {
            "leaf_grid": {
                "columns": 2, "rows": 2,
                "cell_types": ["glass", "solid", "louver", "open"],
            },
            "material_leaf_glass": {"mat": "glass-test",
                                     "opacity": 0.4},
        })
        edited.do(scene)
        self.assertEqual(obj.uid, original_uid)
        self.assertEqual(obj.ifc["global_id"], original_guid)
        self.assertEqual(read_wall(wall)["openings"][0], original_opening)
        self.assertEqual(obj.ext[KEY]["params"]["leaf_grid"]["rows"], 2)
        self.assertTrue(any("régua" in p.name for p in obj.children))
        edited.undo(scene)
        self.assertEqual([p.name for p in obj.children], original_children)
        edited.do(scene)
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname)/"leaf-grid.igz"
            igz.save_scene(scene, path)
            loaded = Scene()
            igz.load_into(loaded, path)
        recovered = next(item for item in loaded.groups
                         if item.uid == original_uid)
        self.assertEqual(
            recovered.ext[KEY]["params"]["leaf_grid"]["cell_types"],
            ["glass", "solid", "louver", "open"])
        self.assertEqual(recovered.ifc["global_id"], original_guid)
        self.assertAlmostEqual(wallhole_size(
            recovered.ext[KEY]["params"])[0],
            wallhole_size(door())[0])

    def test_editor_is_instance_only_and_returns_valid_grid(self):
        app = QApplication.instance() or QApplication([])
        from OpenTrace_BIM.door_window_core import normalize_fill
        editor = DoorLeafGridDialog(normalize_fill(door()))
        editor._dimensions["rows"].setValue(2)
        editor._dimensions["columns"].setValue(2)
        self.assertEqual(len(editor.result_grid()["cell_types"]), 4)
        editor.reject()
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
