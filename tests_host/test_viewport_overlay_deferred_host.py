# SPDX-License-Identifier: GPL-3.0-or-later
"""Deferred startup against the real plugin installed into a temporary user directory."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtWidgets import QApplication, QTabBar, QToolBar, QToolButton
from views.main_window import MainWindow

APP = QApplication.instance() or QApplication([])


class DeferredOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temp = tempfile.TemporaryDirectory(prefix="opentrace-overlay-plugin-")
        cls._old_xdg = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = cls._temp.name
        from core.extensions import user_plugins_dir
        plugins = user_plugins_dir()
        plugins.mkdir(parents=True, exist_ok=True)
        source = Path(__file__).resolve().parents[1] / "OpenTrace_BIM"
        shutil.copytree(source, plugins / "OpenTrace_BIM",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        cls.window = MainWindow(defer_extensions=True)
        w = cls.window
        w.resize(1400, 850)
        w.show()
        APP.processEvents()

        # A real legacy QMainWindow state containing the abandoned toolbar name.
        old = QToolBar("Legacy architecture toolbar", w)
        old.setObjectName("arquitetura_parametrica_toolbar")
        old.addAction("Previous architecture controls")
        w.addToolBar(Qt.TopToolBarArea, old)
        cls.legacy_state = w.saveState()
        cls.host_bars = {
            bar.objectName(): w.toolBarArea(bar)
            for bar in w.findChildren(QToolBar)
            if bar is not old and w.toolBarArea(bar) != Qt.NoToolBarArea
        }
        w.removeToolBar(old)
        old.setParent(None)
        old.deleteLater()
        APP.processEvents()

        QSettings().setValue("ui/window_state", cls.legacy_state)
        w.load_extensions()  # Real discovery, import and setup: no plugin mocks.
        for _ in range(5):
            APP.processEvents()

    @classmethod
    def tearDownClass(cls):
        initial = getattr(cls.window, "_opentrace_bundled_layer_combinations_app", None)
        if initial is not None:
            controller = getattr(cls.window, "_layer_combinations_service", None)
            # The chooser can remain open without blocking the test process.
            for dlg in QApplication.topLevelWidgets():
                if dlg.windowTitle() == "Escolher Template de Camadas":
                    dlg.reject()
        QSettings().remove("ui/window_state")
        cls.window.deleteLater()
        APP.processEvents()
        if cls._old_xdg is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = cls._old_xdg
        cls._temp.cleanup()

    def test_old_saved_layout_does_not_move_panels(self):
        w = self.window
        suite = getattr(w, "_arquitetura_parametrica_suite_panel", None)
        self.assertIsNotNone(suite, getattr(w, "_extension_load_errors", None))
        overlay = w._arquitetura_parametrica_overlay_dock
        self.assertIsNotNone(overlay)
        self.assertIs(overlay.parentWidget(), w.viewport)
        self.assertEqual(overlay.pos(), QPoint(8, 8))
        # The contextual options panel opens only for an active modelling tool.
        w._arquitetura_parametrica_controller.action.trigger()
        overlay.bar.refresh()
        self.assertFalse(overlay.options_frame.isHidden())
        self.assertLess(
            overlay.row.mapTo(w.viewport, QPoint(0, 0)).y(),
            overlay.options_frame.mapTo(w.viewport, QPoint(0, 0)).y())
        for name, area in self.host_bars.items():
            toolbar = w.findChild(QToolBar, name)
            self.assertIsNotNone(toolbar, name)
            self.assertEqual(w.toolBarArea(toolbar), area, name)
        self.assertEqual(w.toolBarArea(overlay.row.toolbar), Qt.NoToolBarArea)
        self.assertNotIn(b"opentrace_", bytes(w.saveState()))

    def test_no_stray_tab_bar_at_startup_with_real_plugin(self):
        w = self.window
        self.assertIsNotNone(getattr(w, "_layer_combinations_service", None))
        viewport = w.viewport
        # The first-run layer template chooser may be visible, but cannot
        # block the host's keyboard shortcuts with WindowModal.
        choosers = [
            dialog for dialog in QApplication.topLevelWidgets()
            if dialog.windowTitle() == "Escolher Template de Camadas"
        ]
        for chooser in choosers:
            self.assertEqual(chooser.windowModality(), Qt.NonModal)
            self.assertFalse(chooser.isModal())
        self.assertIsNone(APP.activeModalWidget())
        vp_left = viewport.mapTo(w, QPoint(0, 0)).x()
        vp_right = vp_left + viewport.width()
        vp_top = viewport.mapTo(w, QPoint(0, 0)).y()
        # A detached host dock-tab strip overlays the top of the model space.
        loose = []
        for bar in w.findChildren(QTabBar):
            if not bar.isVisible():
                continue
            top = bar.mapTo(w, QPoint(0, 0))
            horizontal_overlap = top.x() < vp_right and top.x() + bar.width() > vp_left
            if horizontal_overlap and top.y() < vp_top and top.y() + bar.height() >= vp_top - 50:
                loose.append(bar.objectName() or repr(bar))
        self.assertEqual(loose, [])
