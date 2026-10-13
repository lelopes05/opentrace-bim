# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression: saved layout with the old toolbar must not squeeze new rows."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class OldToolbarLayoutTests(unittest.TestCase):
    def test_old_saved_layout_does_not_squeeze_the_bars(self):
        from PySide6.QtCore import QSettings, Qt
        from PySide6.QtWidgets import QApplication, QMainWindow, QToolBar
        from views.main_window import MainWindow
        from OpenTrace_BIM import setup

        qt = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            QSettings.setDefaultFormat(QSettings.IniFormat)
            QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, directory)
            old = QMainWindow()
            legacy = QToolBar("Old Architecture", old)
            legacy.setObjectName("arquitetura_parametrica_toolbar")
            old.addToolBar(Qt.TopToolBarArea, legacy)
            QSettings().setValue("ui/window_state", old.saveState())
            old.deleteLater()
            qt.processEvents()

            window = MainWindow(defer_extensions=True)
            try:
                window.show()
                qt.processEvents()
                plugin = SimpleNamespace(stem="OpenTrace_BIM", setup=setup,
                                         tools=[], path=Path("OpenTrace_BIM"))
                with patch("core.extensions.discover_plugins", return_value=([plugin], [])):
                    window.load_extensions()
                qt.processEvents()
                row = window._arquitetura_parametrica_tool_row
                bar = window._arquitetura_parametrica_controller.toolbar
                self.assertTrue(window.toolBarBreak(row))
                self.assertTrue(window.toolBarBreak(bar))
                self.assertLess(row.y(), bar.y())
            finally:
                window.deleteLater()
                qt.processEvents()
