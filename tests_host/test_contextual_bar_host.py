# SPDX-License-Identifier: GPL-3.0-or-later
"""The options bar follows the active tool and never chooses a tool."""
import os
import tempfile
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QPointF, QSettings, Qt
from PySide6.QtGui import QAction, QVector3D
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QToolButton

QCoreApplication.setOrganizationName("OpenTraceTests")
QCoreApplication.setApplicationName("contextual-bar")
QSettings.setDefaultFormat(QSettings.IniFormat)
_SETTINGS_DIR = tempfile.mkdtemp(prefix="opentrace-tests-settings-")
for _scope in (QSettings.UserScope, QSettings.SystemScope):
    QSettings.setPath(QSettings.IniFormat, _scope, _SETTINGS_DIR)

APP = QApplication.instance() or QApplication([])
_SHARED = {}

GEOMETRIES = ("single", "rect_diagonal", "rect_base_width", "arc_normal", "arc_center", "arc_three")


def shared_window():
    """One real window with the plugin for the whole file (several crash offscreen Qt)."""
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


class BarTests(unittest.TestCase):
    def setUp(self):
        from OpenTrace_BIM.host import activate_select
        self.window, self.app = shared_window()
        self.wall = self.window._arquitetura_parametrica_controller
        self.suite = self.window._arquitetura_parametrica_suite_panel
        self.bar = self.suite.context_bar
        self.openings = self.wall.openings
        activate_select(self.app)

    def tearDown(self):
        from OpenTrace_BIM.host import activate_select
        activate_select(self.app)

    def ctx(self, world):
        return SimpleNamespace(viewport=self.window.viewport, world=QVector3D(world),
                               snap=None, screen=QPointF(0, 0), modifiers=Qt.NoModifier)

    def new_wall(self, length=8.0):
        from OpenTrace_BIM import model
        scene = self.window.viewport.scene
        wall = model.make_wall_segment(QVector3D(0, 0, 0), QVector3D(length, 0, 0),
                                       dict(model.DEFAULTS, length=length))
        scene.groups.append(wall)
        self.addCleanup(scene.groups.remove, wall)
        scene.version += 1
        return wall

    def size_controls(self, tool, key):
        return next(c for c in self.bar._size_controls if c[2] is tool and c[4] == key)

    def test_bar_page_follows_active_tool(self):
        from OpenTrace_BIM.host import activate_select
        for action, key in zip(self.openings.tool_actions, ("opening", "door", "window")):
            activate_select(self.app)
            action.trigger()
            self.bar.refresh()
            self.assertEqual(self.bar._context_key(), key)
            self.assertIs(self.bar.stack.currentWidget(), self.bar.pages[key][0])
        activate_select(self.app)
        self.wall.action.trigger()
        self.bar.refresh()
        self.assertEqual(self.bar._context_key(), "wall")

    def test_bar_never_changes_tool(self):
        from OpenTrace_BIM import host, wall_opening_ui
        forbidden = mock.Mock(side_effect=AssertionError("the bar chose a tool"))
        tools = (self.openings.opening_tool, self.openings.door_tool, self.openings.window_tool)
        keys = ("opening", "door", "window")
        with mock.patch.object(host, "activate_tool", forbidden), \
                mock.patch.object(wall_opening_ui, "activate_tool", forbidden):
            for action, tool, key in zip(self.openings.tool_actions, tools, keys):
                self.window._activate_tool("select")
                self.window._activate_tool(self.key_of(action))
                self.bar.refresh()
                page = self.bar.pages[key][0]
                for button in page.findChildren(QToolButton):
                    if button.isEnabled():
                        button.click()
                        self.assertIs(self.window.viewport.active_tool, tool, button.accessibleName())
                for spin in page.findChildren(QDoubleSpinBox):
                    if spin.isEnabled():
                        spin.setValue(min(spin.maximum(), spin.value() + 0.1))
                        self.assertIs(self.window.viewport.active_tool, tool)
        forbidden.assert_not_called()
        self.openings.opening_tool.set_shape("rect")

    def key_of(self, action):
        return next(k for k, a in self.window._tool_actions.items() if a is action)

    def test_opening_fields_are_the_tool_sizes(self):
        self.window._activate_tool(self.key_of(self.openings.tool_actions[0]))
        tool = self.openings.opening_tool
        tool.set_shape("rect")
        spin = self.size_controls(tool.place, "width")[0]
        spin.setValue(1.37)
        self.assertAlmostEqual(tool.place.sizes["rect"]["width"], 1.37)
        tool.place.sizes["rect"]["width"] = 0.77
        self.bar.refresh()
        self.assertAlmostEqual(spin.value(), 0.77)

    def test_square_and_circle_lock_height(self):
        from OpenTrace_BIM import model
        from OpenTrace_BIM.i18n import t
        from OpenTrace_BIM.wall_face import WallFace
        wall = self.new_wall()
        face = WallFace(wall)
        scene = self.window.viewport.scene
        self.window._activate_tool(self.key_of(self.openings.tool_actions[0]))
        tool = self.openings.opening_tool
        for shape in ("square", "circle"):
            with self.subTest(shape=shape):
                tool.set_shape(shape)
                self.bar.refresh()
                width, title, _t, _k, _key = self.size_controls(tool.place, "width")
                height = self.size_controls(tool.place, "height")[0]
                self.assertFalse(height.isEnabled())
                width.setValue(0.55)
                self.bar.refresh()
                self.assertAlmostEqual(height.value(), 0.55)
                self.assertEqual(title.text(), t("Diâmetro") if shape == "circle" else t("Largura"))
                tool.on_click(self.ctx(face.world(QVector3D(3.0, 1.0, 0))))
                item = model.read_wall(wall)["openings"][-1]
                if shape == "square":
                    self.assertAlmostEqual(item["width"], item["height"])
                else:
                    s = [p[0] for p in item["polygon"]]
                    z = [p[1] for p in item["polygon"]]
                    self.assertAlmostEqual(max(s) - min(s), max(z) - min(z))
                self.assertTrue(self.window.viewport.history.undo())
        tool.set_shape("rect")

    def test_free_shape_disables_fields(self):
        self.window._activate_tool(self.key_of(self.openings.tool_actions[0]))
        tool = self.openings.opening_tool
        tool.set_shape("free")
        self.bar.refresh()
        for key in ("width", "height", "sill"):
            self.assertFalse(self.size_controls(tool.place, key)[0].isEnabled(), key)
        tool.set_shape("rect")
        self.bar.refresh()
        self.assertTrue(self.size_controls(tool.place, "width")[0].isEnabled())

    def test_wall_geometry_changes_without_changing_tool(self):
        from OpenTrace_BIM import model
        scene = self.window.viewport.scene
        history = self.window.viewport.history
        self.wall.action.trigger()
        tool = self.window.viewport.active_tool
        self.assertIs(tool, self.wall.draw_tool)
        for geometry in GEOMETRIES:
            self.wall.choose_geometry(geometry)
            self.assertIs(self.window.viewport.active_tool, tool)
            self.assertEqual(tool.geometry, geometry)

        base = self.wall.defaults["base"]
        before = len(scene.groups)

        def click(x, y):
            self.window.viewport.active_tool.on_click(self.ctx(QVector3D(x, y, base)))

        self.wall.choose_geometry("arc_three")
        for x, y in ((0, 0), (2, 1), (4, 0)):
            click(x, y)
        curved = scene.groups[-1]
        self.assertEqual(len(scene.groups), before + 1)
        self.assertEqual(model.wall_path_kind(curved), "arc")
        self.assertIs(self.window.viewport.active_tool, tool)

        self.wall.choose_geometry("single")
        for x, y in ((0, 5), (4, 5)):
            click(x, y)
        straight = scene.groups[-1]
        self.assertEqual(len(scene.groups), before + 2)
        self.assertEqual(model.wall_path_kind(straight), "line")
        self.assertTrue(history.undo())
        self.assertTrue(history.undo())
        self.assertEqual(len(scene.groups), before)

    def test_no_curve_wall_action_left(self):
        self.assertFalse(hasattr(self.wall, "curve_action"))
        self.assertNotIn("arquitetura_parametrica_curved_wall", self.window._tools)
        self.assertEqual(
            [a.text() for a in self.wall.wall_type_menu.actions() if not a.isSeparator()],
            [self.wall.simple_wall_action.text(), self.wall.composite_wall_action.text()])
        for action in self.window.findChildren(QAction):
            self.assertNotIn(action.text().lower(), ("parede curva", "curved wall"))
        for button in self.window.findChildren(QToolButton):
            self.assertNotIn("parede curva", button.toolTip().lower())
        self.assertNotIn("wall_curve", self.bar.pages)
        wall_actions = self.suite._actions_for("wall", self.wall)
        self.assertEqual(wall_actions, [self.wall.simple_wall_action, self.wall.composite_wall_action])

    def test_opening_anchor_from_bar(self):
        from OpenTrace_BIM import model
        from OpenTrace_BIM.wall_face import WallFace
        wall = self.new_wall()
        self.window._activate_tool(self.key_of(self.openings.tool_actions[0]))
        tool = self.openings.opening_tool
        tool.set_shape("rect")
        self.bar.refresh()
        page = self.bar.pages["opening"][0]
        left = next(b for b in page.findChildren(QToolButton)
                    if b.accessibleName() == "Left anchor")
        left.click()
        self.assertEqual(tool.place.anchor, "left")
        self.addCleanup(setattr, tool.place, "anchor", "center")
        self.assertIs(self.window.viewport.active_tool, tool)
        face = WallFace(wall)
        tool.on_click(self.ctx(face.world(QVector3D(3.0, 1.0, 0))))
        item = model.read_wall(wall)["openings"][0]
        self.assertAlmostEqual(item["position"] - item["width"] / 2.0, 3.0)
        self.assertTrue(self.window.viewport.history.undo())
        tool.set_shape("free")
        self.bar.refresh()
        for button in self.bar._opening_anchor_buttons:
            self.assertFalse(button.isEnabled())
        tool.set_shape("rect")
        self.bar.refresh()

    def test_door_window_floor_sill_is_zero(self):
        for key, tool, kind in (
            (1, self.openings.door_tool, "door"),
            (2, self.openings.window_tool, "window"),
        ):
            self.window._activate_tool(self.key_of(self.openings.tool_actions[key]))
            self.bar.refresh()
            sill = self.size_controls(tool, "sill")[0]
            self.assertEqual(sill.minimum(), 0.0)
            previous = tool.sizes[kind]["sill"]
            try:
                sill.setValue(0.0)
                self.assertEqual(tool.sizes[kind]["sill"], 0.0)
            finally:
                tool.sizes[kind]["sill"] = previous
        self.bar.refresh()

    def test_door_anchor_from_bar(self):
        from OpenTrace_BIM import model
        from OpenTrace_BIM.door_window_commands import _fill_record
        from OpenTrace_BIM.wall_face import WallFace
        wall = self.new_wall()
        scene = self.window.viewport.scene
        self.window._activate_tool(self.key_of(self.openings.tool_actions[1]))
        self.bar.refresh()
        page = self.bar.pages["door"][0]
        left = next(b for b in page.findChildren(QToolButton) if b.accessibleName() == "Left anchor")
        left.click()
        self.assertEqual(self.openings.door_tool.anchor, "left")
        self.addCleanup(setattr, self.openings.door_tool, "anchor", "center")
        face = WallFace(wall)
        self.window.viewport.active_tool.on_click(self.ctx(face.world(QVector3D(3.0, 1.0, 0))))
        fills = [g for g in scene.groups if _fill_record(g)]
        self.assertEqual(len(fills), 1)
        self.assertEqual(_fill_record(fills[0])["params"]["anchor"], "left")
        item = model.read_wall(wall)["openings"][0]
        self.assertAlmostEqual(item["position"] - item["width"] / 2.0, 3.0, places=6)
        self.assertTrue(self.window.viewport.history.undo())


if __name__ == "__main__":
    unittest.main()
