# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage 2: toolbar order, persistence and the IngeTrazo 0.5.8 startup."""
import os
import subprocess
import sys
import textwrap
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class ToolRowHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        from views.main_window import MainWindow
        from views.extension_api import ExtensionApp
        from OpenTrace_BIM import setup

        cls.qt = QApplication.instance() or QApplication([])
        cls.window = MainWindow(defer_extensions=True)
        cls.window.show()
        cls.qt.processEvents()
        setup(ExtensionApp(cls.window, "OpenTrace_BIM"))
        cls.qt.processEvents()
        cls.wall = cls.window._arquitetura_parametrica_controller
        cls.row = cls.window._arquitetura_parametrica_tool_row

    @classmethod
    def tearDownClass(cls):
        cls.window.deleteLater()
        cls.qt.processEvents()

    def test_tool_row_order(self):
        from OpenTrace_BIM.i18n import t
        actions = self.row.actions()
        self.assertEqual([a.text() if not a.isSeparator() else "<separator>"
                          for a in actions[:-1]],
                         [t("Parede"), t("Laje"), t("Pilar"), t("Viga"),
                          "<separator>", t("Abertura"), t("Porta"),
                          t("Janela"), "<separator>", t("Perfil Complexo…")])
        self.assertIs(self.row.wall_button, self.wall.wall_menu_button)
        self.assertIs(self.row.wall_button.menu(), self.wall.wall_type_menu)
        self.assertEqual(self.row.objectName(), "opentrace_tools_toolbar")
        self.assertEqual(self.wall.toolbar.objectName(), "opentrace_options_toolbar")
        self.assertFalse(self.row.isMovable())
        self.assertFalse(self.row.isFloatable())

    def test_tool_row_is_its_own_line_above_the_bar(self):
        from PySide6.QtCore import Qt
        self.qt.processEvents()
        self.assertTrue(self.window.toolBarBreak(self.row))
        self.assertTrue(self.window.toolBarBreak(self.wall.toolbar))
        self.assertLess(self.row.mapTo(self.window, self.row.rect().topLeft()).y(),
                        self.wall.toolbar.mapTo(self.window, self.wall.toolbar.rect().topLeft()).y())
        for tool_bar in self.window.toolbars.values():
            if (self.window.toolBarArea(tool_bar) == Qt.TopToolBarArea
                    and tool_bar.isVisibleTo(self.window)):
                self.assertLess(
                    tool_bar.mapTo(self.window, tool_bar.rect().topLeft()).y(),
                    self.row.mapTo(self.window, self.row.rect().topLeft()).y())

    def test_tool_row_actions_activate_tools(self):
        from OpenTrace_BIM.host import WALL_TOOL_KEY, SLAB_TOOL_KEY, COLUMN_TOOL_KEY, BEAM_TOOL_KEY
        from OpenTrace_BIM.wall_opening_ui import OPENING_TOOL_KEY, DOOR_TOOL_KEY, WINDOW_TOOL_KEY
        tool_actions = [
            (WALL_TOOL_KEY, self.wall.action),
            (SLAB_TOOL_KEY, self.window._arquitetura_parametrica_slab_controller.action),
            (COLUMN_TOOL_KEY, self.window._arquitetura_parametrica_column_controller.action),
            (BEAM_TOOL_KEY, self.window._arquitetura_parametrica_beam_controller.action),
            (OPENING_TOOL_KEY, self.wall.openings.tool_actions[0]),
            (DOOR_TOOL_KEY, self.wall.openings.tool_actions[1]),
            (WINDOW_TOOL_KEY, self.wall.openings.tool_actions[2]),
        ]
        for key, action in tool_actions:
            with self.subTest(tool=key):
                self.assertIn(action, self.row.tool_actions)
                action.trigger()
                self.assertIs(self.window.viewport.active_tool, self.window._tools[key])
                self.assertTrue(action.isChecked())

    def test_tool_row_compact(self):
        from PySide6.QtCore import QSettings, Qt
        from OpenTrace_BIM.tool_row import ToolRow
        original = QSettings().value(ToolRow.SETTINGS_KEY)
        try:
            self.row.set_compact(False)
            initial = self.row.sizeHint().height()
            self.row.collapse_button.click()
            self.assertTrue(self.row._compact)
            self.assertEqual(self.row.toolButtonStyle(), Qt.ToolButtonIconOnly)
            self.assertEqual(self.row.iconSize().width(), 16)
            self.assertLess(self.row.sizeHint().height(), initial)
            self.row.collapse_button.click()
            self.assertEqual(self.row.toolButtonStyle(), Qt.ToolButtonTextBesideIcon)
            self.assertEqual(self.row.iconSize().width(), 24)
            # Construct a second independent row without altering a second MainWindow.
            from PySide6.QtWidgets import QMainWindow, QToolBar, QToolButton
            from types import SimpleNamespace
            probe = QMainWindow()
            options = QToolBar(probe)
            probe.addToolBar(options)
            wall = SimpleNamespace(toolbar=options, wall_menu_button=QToolButton(probe),
                                   action=self.wall.action, openings=self.wall.openings)
            fresh = ToolRow(SimpleNamespace(window=probe), wall, None, None, None, None)
            self.assertFalse(fresh._compact)
            fresh.deleteLater()
            probe.deleteLater()
        finally:
            if original is None:
                QSettings().remove(ToolRow.SETTINGS_KEY)
            else:
                QSettings().setValue(ToolRow.SETTINGS_KEY, original)
            self.row.set_compact(False, persist=False)

    def test_tool_row_survives_restore_state(self):
        self.qt.processEvents()
        current = self.window.saveState()
        self.assertTrue(self.window.restoreState(current))
        self.qt.processEvents()
        self.assertTrue(self.window.toolBarBreak(self.row))
        self.assertTrue(self.window.toolBarBreak(self.wall.toolbar))
        self.assertLess(self.row.y(), self.wall.toolbar.y())

    @staticmethod
    def _child(script):
        result = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(script)],
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True, text=True, timeout=100)
        if result.returncode:
            raise AssertionError(result.stdout + "\n" + result.stderr)

    def test_old_saved_layout_does_not_squeeze_the_bars(self):
        self._child("""
            import tempfile
            from pathlib import Path
            from types import SimpleNamespace
            from unittest.mock import patch
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
                old.addToolBar(Qt.TopToolBarArea, legacy)  # no toolbar break
                QSettings().setValue("ui/window_state", old.saveState())
                old.deleteLater()
                qt.processEvents()
                window = MainWindow(defer_extensions=True)
                window.show()
                qt.processEvents()
                plugin = SimpleNamespace(stem="OpenTrace_BIM",
                    setup=setup, tools=[], path=Path("OpenTrace_BIM"))
                with patch("core.extensions.discover_plugins", return_value=([plugin], [])):
                    window.load_extensions()
                qt.processEvents()
                row = window._arquitetura_parametrica_tool_row
                bar = window._arquitetura_parametrica_controller.toolbar
                assert window.toolBarBreak(row)
                assert window.toolBarBreak(bar)
                assert row.y() < bar.y()
                window.deleteLater()
                qt.processEvents()
        """)

    def test_no_duplicate_tabs_during_modal_startup(self):
        # Test the reported "Properties, BIM, Terrain, AI" ghost tab strip.
        self._child("""
            from pathlib import Path
            from types import SimpleNamespace
            from unittest.mock import patch
            from PySide6.QtWidgets import QApplication, QDialog, QTabBar
            from views.main_window import MainWindow
            from OpenTrace_BIM import setup

            qt = QApplication.instance() or QApplication([])
            window = MainWindow(defer_extensions=True)
            window.show()
            dialog = QDialog(window)
            dialog.setWindowTitle("Escolher Template de Layers")
            dialog.setModal(True)
            dialog.open()
            qt.processEvents()
            plugin = SimpleNamespace(stem="OpenTrace_BIM",
                setup=setup, tools=[], path=Path("OpenTrace_BIM"))
            with patch("core.extensions.discover_plugins", return_value=([plugin], [])):
                window.load_extensions()
            qt.processEvents()
            central_top = window.centralWidget().mapTo(window, window.centralWidget().rect().topLeft()).y()
            ghosts = [tab for tab in window.findChildren(QTabBar)
                      if tab.isVisibleTo(window)
                      and tab.mapTo(window, tab.rect().topLeft()).y() < central_top]
            assert not ghosts, [(tab.objectName(), tab.tabText(0), tab.y()) for tab in ghosts]
            dialog.close()
            window.deleteLater()
            qt.processEvents()
        """)
