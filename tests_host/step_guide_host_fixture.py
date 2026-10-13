# SPDX-License-Identifier: GPL-3.0-or-later
"""Single-host fixture for isolated opening prompt integration checks."""
import gc
import unittest
from types import SimpleNamespace
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication
from OpenTrace_BIM import model
from OpenTrace_BIM.host import activate_select
from OpenTrace_BIM.step_guide import step_text

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


def teardown_window():
    window = _SHARED.pop("window", None)
    _SHARED.clear()
    if window is not None:
        window.deleteLater()
        APP.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()
    gc.collect()


class OpeningGuideHostCase(unittest.TestCase):
    def setUp(self):
        self.window, self.app = shared_window()
        self.viewport = self.app.viewport
        self.scene = self.viewport.scene
        self.original_groups = tuple(self.scene.groups)
        self.wall = self.window._arquitetura_parametrica_controller
        self.slab = self.window._arquitetura_parametrica_slab_controller
        activate_select(self.app)
        self.scene.clear_selection()
        APP.processEvents()

    def tearDown(self):
        activate_select(self.app)
        self.wall.openings.clear_sticky()
        self.slab.clear_sticky()
        self.app.release_pick()
        self.scene.clear_selection()
        for group in list(self.scene.groups):
            if group not in self.original_groups:
                self.scene.groups.remove(group)
        self.scene.version += 1
        APP.processEvents()

    def click(self, xyz):
        q = QVector3D(*xyz)
        ctx = SimpleNamespace(
            viewport=self.viewport, world=q, snap=None,
            screen=QPointF(0, 0), modifiers=Qt.NoModifier)
        self.viewport.active_tool.on_click(ctx)
        APP.processEvents()

    def assert_step(self, identifier):
        expected = step_text(identifier)
        self.assertIn(expected, self.window.statusBar().currentMessage())
        self.assertEqual(self.viewport.active_tool.status_clause(), expected)
