# SPDX-License-Identifier: GPL-3.0-or-later
"""The tool row and the options bar: floating panels over the 3D view."""
import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest import mock

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QRect, QSettings, QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolBar, QToolButton

# Settings of their own: the compact state is written by these tests.
QCoreApplication.setOrganizationName("OpenTraceTests")
QCoreApplication.setApplicationName("tool-row")
QSettings.setDefaultFormat(QSettings.IniFormat)
_SETTINGS_DIR = tempfile.mkdtemp(prefix="opentrace-tests-settings-")
for _scope in (QSettings.UserScope, QSettings.SystemScope):
    QSettings.setPath(QSettings.IniFormat, _scope, _SETTINGS_DIR)

APP = QApplication.instance() or QApplication([])
_SHARED = {}


def shared_window():
    """One real window with the plugin for the whole file (several crash offscreen Qt)."""
    if not _SHARED:
        from views.extension_api import ExtensionApp
        from views.main_window import MainWindow
        from OpenTrace_BIM import setup
        window = MainWindow()
        app = ExtensionApp(window, "OpenTrace_BIM")
        setup(app)
        _SHARED.update(window=window, app=app)
    return _SHARED["window"], _SHARED["app"]


def tearDownModule():
    window = _SHARED.pop("window", None)
    _SHARED.clear()
    if window is not None:
        window.deleteLater()
        APP.processEvents()


class ToolRowTests(unittest.TestCase):
    def setUp(self):
        self.window, self.app = shared_window()
        self.wall = self.window._arquitetura_parametrica_controller
        self.row = self.window._arquitetura_parametrica_tool_row
        self.assertIsNotNone(self.row, self.window._arquitetura_parametrica_startup_errors)

    def entries(self):
        """The row's actions in order, None for a separator, without the fold button."""
        out = []
        for action in self.row.toolbar.actions():
            widget = self.row.toolbar.widgetForAction(action)
            if action.isSeparator():
                out.append(None)
            elif widget is self.row.compact_button:
                continue
            elif isinstance(widget, QToolButton) and widget.defaultAction() is not None:
                out.append(widget.defaultAction())
            else:
                out.append(action)
        return out

    def show_window(self):
        self.window.resize(1500, 900)
        self.window.show()
        APP.processEvents()

    def test_tool_row_order(self):
        from OpenTrace_BIM.i18n import t
        w = self.window
        slab = w._arquitetura_parametrica_slab_controller
        column = w._arquitetura_parametrica_column_controller
        beam = w._arquitetura_parametrica_beam_controller
        profile = w._arquitetura_parametrica_profile_controller
        expected = [self.wall.action, slab.action, column.action, beam.action, None,
                    *self.wall.openings.tool_actions, None, profile.action]
        self.assertEqual(self.entries(), expected)
        self.assertEqual(
            [a.text() if a is not None else "" for a in self.entries()],
            [t("Parede paramétrica"), t("Laje paramétrica"), t("Pilar paramétrico"),
             t("Viga paramétrica"), "", t("Abertura"), t("Porta"), t("Janela"), "",
             t("Perfil Complexo…")])
        self.assertIs(self.row.toolbar.widgetForAction(self.row.toolbar.actions()[0]),
                      self.wall.wall_menu_button)

    def panel_rect(self, panel):
        viewport = self.window.viewport
        return QRect(panel.mapTo(viewport, QPoint(0, 0)), panel.size())

    def test_panels_are_not_host_toolbars(self):
        w = self.window
        saved = bytes(w.saveState())
        plugin_bars = [tb for tb in w.findChildren(QToolBar)
                       if self.row.isAncestorOf(tb)]
        self.assertIn(self.row.toolbar, plugin_bars)
        for toolbar in plugin_bars:
            self.assertEqual(w.toolBarArea(toolbar), Qt.NoToolBarArea)
        for encoding in ("utf-8", "utf-16-be"):
            self.assertNotIn("opentrace_".encode(encoding), saved)

    def test_panels_stacked_top_left_inside_viewport(self):
        self.show_window()
        viewport = self.window.viewport
        bar = self.window._arquitetura_parametrica_suite_panel.context_bar
        row_rect, bar_rect = self.panel_rect(self.row), self.panel_rect(bar)
        self.assertLess(row_rect.y(), bar_rect.y())
        self.assertEqual(row_rect.x(), 8)
        for rect in (row_rect, bar_rect):
            self.assertTrue(viewport.rect().contains(rect), rect)

    def test_panels_follow_viewport_resize(self):
        self.show_window()
        viewport = self.window.viewport
        bar = self.window._arquitetura_parametrica_suite_panel.context_bar
        self.row.set_compact(False)
        self.window.resize(600, 700)
        APP.processEvents()
        self.assertLess(viewport.width() - 16, self.row.sizeHint().width())
        for panel in (self.row, bar):
            self.assertTrue(viewport.rect().contains(self.panel_rect(panel)), panel.objectName())
        extension = self.row.toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
        self.assertTrue(extension.isVisible())
        self.window.resize(1500, 900)
        APP.processEvents()

    def test_click_on_panel_does_not_reach_tool(self):
        from OpenTrace_BIM.host import activate_select
        self.show_window()
        viewport = self.window.viewport
        bar = self.window._arquitetura_parametrica_suite_panel.context_bar
        reached = []

        class Spy(QObject):
            def eventFilter(self, watched, event):
                if event.type() == QEvent.MouseButtonPress:
                    reached.append(watched)
                return False

        spy = Spy(viewport)
        viewport.installEventFilter(spy)
        self.wall.action.trigger()
        tool = self.wall.draw_tool
        with mock.patch.object(tool, "on_click") as clicked:
            for panel in (self.row, bar):
                QTest.mouseClick(panel, Qt.LeftButton, pos=QPoint(1, 1))
        viewport.removeEventFilter(spy)
        activate_select(self.app)
        clicked.assert_not_called()
        self.assertEqual(reached, [])

    def test_tool_row_actions_activate_tools(self):
        from OpenTrace_BIM.host import activate_select
        w = self.window
        key_of = {action: key for key, action in w._tool_actions.items()}
        triggered = 0
        for action in self.entries():
            if action is None or action not in key_of:
                continue
            activate_select(self.app)
            action.trigger()
            self.assertIs(w.viewport.active_tool, w._tools[key_of[action]], action.text())
            triggered += 1
        self.assertEqual(triggered, 7)  # wall, slab, column, beam, opening, door, window
        activate_select(self.app)

    def test_tool_row_compact(self):
        from OpenTrace_BIM.tool_row import COMPACT_KEY, ToolRow
        row = self.row
        if row.compact:
            row.compact_button.click()
        APP.processEvents()
        normal_height = row.sizeHint().height()
        for button in row._buttons:
            self.assertEqual(button.toolButtonStyle(), Qt.ToolButtonTextBesideIcon)
            self.assertEqual(button.iconSize(), QSize(24, 24))

        row.compact_button.click()
        APP.processEvents()
        for button in row._buttons:
            self.assertEqual(button.toolButtonStyle(), Qt.ToolButtonIconOnly)
            self.assertEqual(button.iconSize(), QSize(16, 16))
        self.assertLess(row.sizeHint().height(), normal_height)
        self.assertTrue(QSettings().value(COMPACT_KEY, False, type=bool))

        # A new row reads the saved state.
        stand_in = SimpleNamespace(wall_menu_button=QToolButton(),
                                   openings=SimpleNamespace(tool_actions=()))
        fresh = ToolRow(stand_in, None, None, None, None)
        self.assertTrue(fresh.compact)
        self.assertEqual(fresh.toolbar.iconSize(), QSize(16, 16))
        fresh.deleteLater()

        row.compact_button.click()
        APP.processEvents()
        self.assertFalse(row.compact)
        self.assertFalse(QSettings().value(COMPACT_KEY, True, type=bool))
        self.assertEqual(row.sizeHint().height(), normal_height)

    def test_panels_survive_restore_state(self):
        self.show_window()
        before = (self.panel_rect(self.row), self.entries())
        self.window.restoreState(self.window.saveState())
        APP.processEvents()
        self.assertEqual((self.panel_rect(self.row), self.entries()), before)


if __name__ == "__main__":
    unittest.main()
