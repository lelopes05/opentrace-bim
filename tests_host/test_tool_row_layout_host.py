# SPDX-License-Identifier: GPL-3.0-or-later
"""A layout saved by an older version must not squeeze the OpenTrace toolbars."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QSettings, Qt
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


class OldSavedLayoutTests(unittest.TestCase):
    def test_old_saved_layout_does_not_squeeze_the_bars(self):
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

        window.resize(1500, 900)
        window.show()
        APP.processEvents()
        window.load_extensions()
        APP.processEvents()

        self.assertEqual(window._extension_load_errors, {})
        row = window._arquitetura_parametrica_tool_row
        bar = window._arquitetura_parametrica_controller.toolbar
        self.assertIsNotNone(row, window._arquitetura_parametrica_startup_errors)
        self.assertTrue(window.toolBarBreak(row))
        self.assertTrue(window.toolBarBreak(bar))
        host = [tb for tb in window.findChildren(QToolBar)
                if tb not in (row, bar) and tb.isVisible()
                and window.toolBarArea(tb) == Qt.TopToolBarArea]
        self.assertTrue(host)
        for toolbar in host:
            self.assertLess(toolbar.geometry().y(), row.geometry().y(), toolbar.objectName())
        self.assertLessEqual(row.geometry().bottom(), bar.geometry().y())


if __name__ == "__main__":
    unittest.main()
