# SPDX-License-Identifier: GPL-3.0-or-later
"""No stray dock tab bar appears while a modal dialog is open at start-up.

Leandro's print (13/10): with "Escolher Template de Layers" open, a second row
of tabs (Properties, BIM, Terrain, AI) floated under the toolbars.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QPoint, QRect, QSettings, Qt
from PySide6.QtWidgets import QApplication, QDialog, QDockWidget, QTabBar

QCoreApplication.setOrganizationName("OpenTraceTests")
QCoreApplication.setApplicationName("startup-tabs")
QSettings.setDefaultFormat(QSettings.IniFormat)
_SETTINGS_DIR = tempfile.mkdtemp(prefix="opentrace-tests-settings-")
for _scope in (QSettings.UserScope, QSettings.SystemScope):
    QSettings.setPath(QSettings.IniFormat, _scope, _SETTINGS_DIR)

APP = QApplication.instance() or QApplication([])


def stray_tab_bars(window):
    """Visible tab bars above the central widget or not touching any visible dock."""
    central_top = window.centralWidget().mapTo(window, QPoint(0, 0)).y()
    docks = [d for d in window.findChildren(QDockWidget)
             if d.isVisible() and not d.isFloating()]
    stray = []
    for bar in window.findChildren(QTabBar):
        if not bar.isVisible():
            continue
        rect = QRect(bar.mapTo(window, QPoint(0, 0)), bar.size())
        beside_a_dock = any(
            rect.intersects(d.geometry().adjusted(0, -rect.height() - 2, 0, rect.height() + 2))
            for d in docks)
        if rect.top() < central_top or not beside_a_dock:
            stray.append((bar.objectName(), rect.getRect()))
    return stray


class StartupTabsTests(unittest.TestCase):
    def test_no_stray_tab_bar_while_a_modal_dialog_is_open(self):
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

        dialog = QDialog(window)
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.open()
        APP.processEvents()
        window.load_extensions()
        APP.processEvents()

        self.assertEqual(window._extension_load_errors, {})
        self.assertIsNotNone(window._arquitetura_parametrica_tool_row)
        self.assertEqual(stray_tab_bars(window), [])
        dialog.close()


if __name__ == "__main__":
    unittest.main()
