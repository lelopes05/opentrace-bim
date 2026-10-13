# SPDX-License-Identifier: GPL-3.0-or-later
"""ToolRow restores compact state from QSettings in an independent Qt process."""
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class ToolRowSettingsTests(unittest.TestCase):
    def test_new_tool_row_reads_persisted_compact_state(self):
        from types import SimpleNamespace
        from PySide6.QtCore import QSettings, Qt
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QApplication, QMainWindow, QToolBar, QToolButton
        from OpenTrace_BIM.tool_row import ToolRow

        qt = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            QSettings.setDefaultFormat(QSettings.IniFormat)
            QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, directory)
            QSettings().setValue(ToolRow.SETTINGS_KEY, True)
            win = QMainWindow()
            try:
                bar = QToolBar(win)
                bar.setObjectName("options")
                win.addToolBar(bar)
                action = QAction("Wall", win)
                button = QToolButton(win)
                button.setDefaultAction(action)
                wall = SimpleNamespace(toolbar=bar, wall_menu_button=button,
                                       action=action, openings=SimpleNamespace(tool_actions=()))
                row = ToolRow(SimpleNamespace(window=win), wall,
                              None, None, None, None)
                self.assertTrue(row._compact)
                self.assertEqual(row.toolButtonStyle(), Qt.ToolButtonIconOnly)
                self.assertEqual(row.iconSize().width(), 16)
                row.collapse_button.click()
                self.assertFalse(QSettings().value(ToolRow.SETTINGS_KEY, True, type=bool))
            finally:
                win.deleteLater()
                qt.processEvents()
