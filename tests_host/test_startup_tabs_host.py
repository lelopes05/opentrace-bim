# SPDX-License-Identifier: GPL-3.0-or-later
"""No stray dock tab bar appears at start-up with the real plugin.

Leandro's print (13/10): with "Escolher Template de Layers" open, a second row
of tabs (Properties, BIM, Terrain, AI) floated under the toolbars. That
window belongs to the plugin (layer_combinations); it now opens without a
timer and without blocking the event loop.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QPoint, QRect, QSettings
from PySide6.QtWidgets import QApplication, QDialog, QDockWidget, QTabBar

QCoreApplication.setOrganizationName("OpenTraceTests")
QCoreApplication.setApplicationName("startup-tabs")
QSettings.setDefaultFormat(QSettings.IniFormat)
_SETTINGS_DIR = tempfile.mkdtemp(prefix="opentrace-tests-settings-")
for _scope in (QSettings.UserScope, QSettings.SystemScope):
    QSettings.setPath(QSettings.IniFormat, _scope, _SETTINGS_DIR)

APP = QApplication.instance() or QApplication([])


def stray_tab_bars(window):
    """Dock tab bars on screen that are above the central widget or touch no visible dock."""
    central_top = window.centralWidget().mapTo(window, QPoint(0, 0)).y()
    docks = [d for d in window.findChildren(QDockWidget)
             if d.isVisible() and not d.isFloating()]
    titles = {d.windowTitle() for d in window.findChildren(QDockWidget)}
    stray = []
    for bar in window.findChildren(QTabBar):
        texts = {bar.tabText(i) for i in range(bar.count())}
        if not bar.isVisible() or not texts or not texts <= titles:
            continue
        rect = QRect(bar.mapTo(window, QPoint(0, 0)), bar.size())
        if not window.rect().intersects(rect):
            continue
        beside_a_dock = any(
            rect.intersects(d.geometry().adjusted(0, -rect.height() - 2, 0, rect.height() + 2))
            for d in docks)
        if rect.top() < central_top or not beside_a_dock:
            stray.append((bar.objectName(), sorted(texts), rect.getRect()))
    return stray


class StartupTabsTests(unittest.TestCase):
    def test_no_stray_tab_bar_at_startup_with_real_plugin(self):
        from views.main_window import MainWindow
        data = tempfile.mkdtemp(prefix="opentrace-tests-plugins-")
        os.environ["XDG_DATA_HOME"] = data
        shutil.copytree(Path(__file__).resolve().parents[1] / "OpenTrace_BIM",
                        Path(data) / "ingetrazo" / "plugins" / "OpenTrace_BIM",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        window = MainWindow(defer_extensions=True)
        self.addCleanup(lambda: (window.deleteLater(), APP.processEvents()))
        window.resize(1500, 900)
        window.show()
        APP.processEvents()

        window.load_extensions()
        APP.processEvents()

        self.assertEqual(window._extension_load_errors, {})
        self.assertIsNotNone(window._arquitetura_parametrica_tool_row)
        self.assertIsNotNone(getattr(window, "_layer_combinations_service", None))
        self.assertEqual(stray_tab_bars(window), [])
        for dialog in window.findChildren(QDialog):
            dialog.reject()
        APP.processEvents()


if __name__ == "__main__":
    unittest.main()
