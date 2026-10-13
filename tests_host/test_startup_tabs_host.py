# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression: tab bars must not duplicate during deferred/modal startup."""
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class StartupDockTabsTests(unittest.TestCase):
    def test_no_duplicate_tabs_during_modal_startup(self):
        from PySide6.QtWidgets import QApplication, QDialog, QTabBar
        from views.main_window import MainWindow
        from OpenTrace_BIM import setup

        qt = QApplication.instance() or QApplication([])
        window = MainWindow(defer_extensions=True)
        dialog = QDialog(window)
        try:
            window.show()
            dialog.setWindowTitle("Escolher Template de Layers")
            dialog.setModal(True)
            dialog.open()
            qt.processEvents()
            plugin = SimpleNamespace(stem="OpenTrace_BIM", setup=setup,
                                     tools=[], path=Path("OpenTrace_BIM"))
            with patch("core.extensions.discover_plugins", return_value=([plugin], [])):
                window.load_extensions()
            qt.processEvents()
            central = window.centralWidget()
            central_top = central.mapTo(window, central.rect().topLeft()).y()
            ghosts = [tab for tab in window.findChildren(QTabBar)
                      if tab.isVisibleTo(window)
                      and tab.mapTo(window, tab.rect().topLeft()).y() < central_top]
            self.assertFalse(ghosts,
                [(tab.objectName(), tab.tabText(0), tab.y()) for tab in ghosts])
        finally:
            dialog.close()
            window.deleteLater()
            qt.processEvents()
