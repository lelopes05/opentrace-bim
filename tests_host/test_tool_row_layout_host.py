# SPDX-License-Identifier: GPL-3.0-or-later
"""A layout saved by an older version must not move the OpenTrace panels."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QPoint, QRect, QSettings, Qt
from PySide6.QtWidgets import QApplication, QToolBar

QCoreApplication.setOrganizationName("OpenTraceTests")
QCoreApplication.setApplicationName("tool-row-layout")
QSettings.setDefaultFormat(QSettings.IniFormat)
_SETTINGS_DIR = tempfile.mkdtemp(prefix="opentrace-tests-settings-")
for _scope in (QSettings.UserScope, QSettings.SystemScope):
    QSettings.setPath(QSettings.IniFormat, _scope, _SETTINGS_DIR)

APP = QApplication.instance() or QApplication([])
OLD_BAR_NAME = "arquitetura_parametrica_toolbar"


def install_plugin_in_user_dir():
    """Copy the package where the host looks for user plugins (XDG_DATA_HOME)."""
    data = tempfile.mkdtemp(prefix="opentrace-tests-plugins-")
    os.environ["XDG_DATA_HOME"] = data
    root = Path(__file__).resolve().parents[1] / "OpenTrace_BIM"
    shutil.copytree(root, Path(data) / "ingetrazo" / "plugins" / "OpenTrace_BIM",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def host_layout(window):
    """Name, area and break of every toolbar the host manages, in screen order."""
    bars = sorted((tb for tb in window.findChildren(QToolBar)
                   if window.toolBarArea(tb) != Qt.NoToolBarArea and tb.isVisible()),
                  key=lambda tb: (tb.geometry().y(), tb.geometry().x()))
    return [(tb.objectName(), window.toolBarArea(tb), window.toolBarBreak(tb)) for tb in bars]


class OldSavedLayoutTests(unittest.TestCase):
    def test_old_saved_layout_does_not_move_panels(self):
        from views.main_window import MainWindow
        install_plugin_in_user_dir()
        window = MainWindow(defer_extensions=True)
        self.addCleanup(lambda: (window.deleteLater(), APP.processEvents()))

        # What an older version saved: the plugin toolbar on the host's own line.
        old = QToolBar("old", window)
        old.setObjectName(OLD_BAR_NAME)
        old.addAction("tool")
        window.addToolBar(Qt.TopToolBarArea, old)
        self.assertFalse(window.toolBarBreak(old))
        QSettings().setValue("ui/window_state", window.saveState())
        window.removeToolBar(old)
        old.deleteLater()

        # A window that has not loaded the plugin yet shows the host alone.
        window.resize(1500, 900)
        window.show()
        APP.processEvents()
        without_plugin = host_layout(window)
        self.assertTrue(without_plugin)

        window.load_extensions()
        APP.processEvents()

        self.assertEqual(window._extension_load_errors, {})
        row = window._arquitetura_parametrica_tool_row
        self.assertIsNotNone(row, window._arquitetura_parametrica_startup_errors)
        bar = window._arquitetura_parametrica_suite_panel.context_bar
        names = {entry[0] for entry in without_plugin}
        self.assertEqual([e for e in host_layout(window) if e[0] in names], without_plugin)

        viewport = window.viewport
        rows = QRect(row.mapTo(viewport, QPoint(0, 0)), row.size())
        bars = QRect(bar.mapTo(viewport, QPoint(0, 0)), bar.size())
        self.assertEqual(rows.x(), 8)
        self.assertLess(rows.y(), bars.y())
        for rect in (rows, bars):
            self.assertTrue(viewport.rect().contains(rect), rect)


if __name__ == "__main__":
    unittest.main()
