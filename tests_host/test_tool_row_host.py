# SPDX-License-Identifier: GPL-3.0-or-later
"""The tool row: one fixed line of tools above the options bar."""
import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QSettings, QSize, Qt
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
        for action in self.row.actions():
            widget = self.row.widgetForAction(action)
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
        self.assertEqual(self.row.objectName(), "opentrace_tools_toolbar")
        self.assertIs(self.row.widgetForAction(self.row.actions()[0]), self.wall.wall_menu_button)

    def test_tool_row_is_its_own_line_above_the_bar(self):
        self.show_window()
        w, row, bar = self.window, self.row, self.wall.toolbar
        self.assertEqual(bar.objectName(), "opentrace_options_toolbar")
        self.assertTrue(w.toolBarBreak(row))
        self.assertTrue(w.toolBarBreak(bar))
        self.assertLess(row.geometry().y(), bar.geometry().y())
        host = [tb for tb in w.findChildren(QToolBar)
                if tb not in (row, bar) and tb.isVisible()
                and w.toolBarArea(tb) == Qt.TopToolBarArea]
        self.assertTrue(host)
        for toolbar in host:
            self.assertLess(toolbar.geometry().y(), row.geometry().y(), toolbar.objectName())

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
        fresh = ToolRow(self.window, stand_in, None, None, None, None)
        self.assertTrue(fresh.compact)
        self.assertEqual(fresh.iconSize(), QSize(16, 16))
        fresh.setParent(None)
        fresh.deleteLater()

        row.compact_button.click()
        APP.processEvents()
        self.assertFalse(row.compact)
        self.assertFalse(QSettings().value(COMPACT_KEY, True, type=bool))
        self.assertEqual(row.sizeHint().height(), normal_height)

    def test_tool_row_survives_restore_state(self):
        self.show_window()
        w = self.window

        def layout():
            bars = sorted((tb for tb in w.findChildren(QToolBar)
                           if tb.isVisible() and w.toolBarArea(tb) == Qt.TopToolBarArea),
                          key=lambda tb: (tb.geometry().y(), tb.geometry().x()))
            return ([tb.objectName() for tb in bars], w.toolBarBreak(self.row),
                    w.toolBarBreak(self.wall.toolbar), self.entries())

        before = layout()
        w.restoreState(w.saveState())
        APP.processEvents()
        self.assertEqual(layout(), before)


if __name__ == "__main__":
    unittest.main()
