# SPDX-License-Identifier: GPL-3.0-or-later
"""Real host layer/IFC defaults, selection edits, persistence and undo/redo."""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication
from core.layers import Layer, layer_of
from core.scene import Scene
from formats import igz
from views.main_window import MainWindow
from views.extension_api import ExtensionApp
from OpenTrace_BIM import setup
from OpenTrace_BIM.commands import CreateWall
from OpenTrace_BIM.model import DEFAULTS, make_wall_segment
from OpenTrace_BIM.host import activate_select, activate_wall
from OpenTrace_BIM.creation_properties import creation_defaults


class ObjectPropertiesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])
        cls.window = MainWindow()
        cls.app = ExtensionApp(cls.window, "OpenTrace_BIM")
        setup(cls.app)
        cls.suite = cls.window._arquitetura_parametrica_suite_panel
        cls.panel = cls.suite.object_properties

    @classmethod
    def tearDownClass(cls):
        cls.window.deleteLater()
        cls.qt.processEvents()

    def setUp(self):
        activate_select(self.app)
        scene = self.app.scene
        scene.groups.clear()
        scene.selection.clear()
        creation_defaults(scene).clear()
        scene.layers[:] = [Layer("Layer 0"), Layer("Architecture"), Layer("Structure")]
        self.panel._signature = None

    def wall(self, y=0):
        return make_wall_segment(QVector3D(0,y,0), QVector3D(5,y,0), dict(DEFAULTS,length=5))

    def test_creation_defaults_mirror_and_survive_redo_and_igz(self):
        activate_wall(self.app)
        self.panel.assign_layer("Architecture")
        self.panel.system.setText("Project classification")
        self.panel.code.setText("W-01")
        self.panel.apply_ifc()
        bar = self.window._arquitetura_parametrica_overlay_dock.bar
        self.assertEqual(bar.layer_combo.currentData(), "Architecture")
        group = self.wall()
        command = CreateWall(group)
        command.do(self.app.scene)
        self.assertEqual(layer_of(group), "Architecture")
        self.assertEqual(group.ifc["classification_code"], "W-01")
        original = copy.deepcopy(group.ifc)
        command.undo(self.app.scene)
        self.panel.assign_layer("Structure")
        command.do(self.app.scene)
        self.assertEqual(layer_of(group), "Architecture")
        self.assertEqual(group.ifc, original)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"layers.igz"
            igz.save_scene(self.app.scene, path)
            restored = Scene()
            igz.load_into(restored, path)
            self.assertEqual(layer_of(restored.groups[0]), "Architecture")
            self.assertEqual(restored.groups[0].ifc, original)

    def test_mixed_selection_layer_edit_undo_and_ifc_edit_undo(self):
        scene = self.app.scene
        a, b = self.wall(), self.wall(3)
        CreateWall(a).do(scene)
        CreateWall(b).do(scene)
        b.layer = "Structure"
        scene.selection.update((a,b))
        self.panel.refresh()
        self.assertIsNone(self.panel.layer.currentData())
        self.panel.assign_layer("Architecture")
        self.assertEqual([layer_of(g) for g in (a,b)], ["Architecture"]*2)
        self.app.viewport.history.undo()
        self.assertEqual([layer_of(g) for g in (a,b)], ["Layer 0", "Structure"])
        scene.selection.clear()
        scene.selection.add(a)
        self.panel.refresh()
        original = copy.deepcopy(a.ifc)
        self.panel.system.setText("Custom")
        self.panel.code.setText("A01")
        self.panel.apply_ifc()
        self.assertEqual(a.ifc["classification_code"], "A01")
        self.assertEqual(a.ifc["global_id"], original["global_id"])
        self.app.viewport.history.undo()
        self.assertEqual(a.ifc, original)
        self.assertFalse(creation_defaults(scene))

    def test_locked_selection_cannot_be_edited(self):
        group = self.wall()
        CreateWall(group).do(self.app.scene)
        group.layer = "Structure"
        self.app.scene.layer("Structure").locked = True
        self.app.scene.selection.add(group)
        self.panel.refresh()
        self.assertFalse(self.panel.layer.isEnabled())
        self.panel.assign_layer("Architecture")
        self.assertEqual(layer_of(group), "Structure")

    def test_hosted_door_keeps_independent_layer_and_ifc_on_regeneration(self):
        from OpenTrace_BIM.door_window_commands import CreateHostedFill, EditHostedFill
        scene = self.app.scene
        wall = self.wall()
        CreateWall(wall).do(scene)
        creation_defaults(scene)["door"] = {"layer": "Architecture", "ifc": {
            "classification_system": "Project", "classification_code": "D01"}}
        command = CreateHostedFill(scene, wall, {
            "schema": 2, "kind": "door", "id": "door-test", "opening_id": "opening-test",
            "host_id": wall.uid, "position": 2.5, "width": .8, "height": 2.1})
        command.do(scene)
        door = command.group
        self.assertEqual(layer_of(wall), "Layer 0")
        self.assertEqual(layer_of(door), "Architecture")
        self.assertEqual(door.ifc["classification_code"], "D01")
        edit = EditHostedFill(scene, wall, door, {"width": .9})
        edit.do(scene)
        self.assertEqual(layer_of(door), "Architecture")
        self.assertEqual(door.ifc["classification_code"], "D01")
        edit.undo(scene)
        command.undo(scene)
        creation_defaults(scene)["door"]["layer"] = "Structure"
        command.do(scene)
        self.assertEqual(layer_of(door), "Architecture")

    def test_deleted_default_layer_falls_back_to_native_default(self):
        creation_defaults(self.app.scene)["wall"] = {"layer": "Deleted"}
        group = self.wall()
        CreateWall(group).do(self.app.scene)
        self.assertEqual(layer_of(group), "Layer 0")
