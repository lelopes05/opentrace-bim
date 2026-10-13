# SPDX-License-Identifier: GPL-3.0-or-later
"""The viewport overlay owns both contextual panels, not host toolbars."""
import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QPoint, QSettings, QSize, Qt
from PySide6.QtWidgets import QApplication, QToolBar, QToolButton
from PySide6.QtTest import QTest

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
        self.assertEqual(self.row.objectName(), "opentrace_tools_row")
        self.assertIs(self.row.toolbar.widgetForAction(self.row.toolbar.actions()[0]), self.wall.wall_menu_button)

    def test_brand_and_help_live_in_tool_row(self):
        from PySide6.QtWidgets import QLabel
        suite = self.window._arquitetura_parametrica_suite_panel
        self.assertIs(self.row.brand.parentWidget(), self.row)
        self.assertEqual(self.row.brand.text(), "OpenTrace BIM")
        self.assertIs(
            self.row.findChild(QLabel, "opentrace_tool_brand"), self.row.brand)
        self.assertIs(self.row.help_button.parentWidget(), self.row)
        self.assertEqual(self.row.help_button.text(), "?")
        self.assertIsNone(suite.context_bar.findChild(QToolButton, "opentrace_context_help"))
        self.row.help_button.click()
        self.assertIsNotNone(suite._help_dialog)
        suite._help_dialog.close()

    def test_panels_are_not_host_toolbars(self):
        w = self.window
        strip = self.row.toolbar
        overlay = w._arquitetura_parametrica_overlay_dock
        self.assertIs(overlay.parentWidget(), w.viewport)
        self.assertIs(strip.parentWidget(), self.row)
        self.assertIs(overlay.bar.overlay_dock, overlay)
        self.assertIs(overlay.bar, w._arquitetura_parametrica_suite_panel.context_bar)
        self.assertEqual(w.toolBarArea(strip), Qt.NoToolBarArea)
        plugin_strips = [tb for tb in w.findChildren(QToolBar)
                         if tb.objectName().startswith("opentrace_")]
        self.assertEqual(plugin_strips, [strip])
        for tb in plugin_strips:
            self.assertEqual(w.toolBarArea(tb), Qt.NoToolBarArea)
        layer_strip = w.findChild(QToolBar, "layerCombinationsBottomBar")
        self.assertIsNotNone(layer_strip)
        self.assertEqual(w.toolBarArea(layer_strip), Qt.BottomToolBarArea)
        names = [tb.objectName() for tb in w.findChildren(QToolBar)]
        self.assertNotIn("opentrace_options_toolbar", names)
        self.assertNotIn("opentrace_tools_toolbar", names)
        self.assertNotIn(b"opentrace_", bytes(w.saveState()))

    def test_panels_stacked_top_left_inside_viewport(self):
        self.show_window()
        self.wall.action.trigger()
        overlay = self.window._arquitetura_parametrica_overlay_dock
        overlay.bar.refresh()
        self.assertFalse(overlay.options_frame.isHidden())
        row = self.row
        frame = overlay.options_frame
        viewport = self.window.viewport
        row_origin = row.mapTo(viewport, QPoint(0, 0))
        bar_origin = frame.mapTo(viewport, QPoint(0, 0))
        self.assertEqual(overlay.pos(), QPoint(8, 8))
        self.assertEqual(row_origin.x(), 8)
        self.assertEqual(bar_origin.x(), 8)
        self.assertLess(row_origin.y(), bar_origin.y())
        for panel in (row, frame):
            top = panel.mapTo(viewport, QPoint(0, 0))
            self.assertGreaterEqual(top.x(), 0)
            self.assertGreaterEqual(top.y(), 0)
            self.assertLessEqual(top.x() + panel.width(), viewport.width())
            self.assertLessEqual(top.y() + panel.height(), viewport.height())

    def test_context_options_only_with_active_creation_tool(self):
        from OpenTrace_BIM.host import activate_select
        self.show_window()
        overlay = self.window._arquitetura_parametrica_overlay_dock
        bar = overlay.bar
        activate_select(self.app)
        bar.refresh()
        self.assertTrue(overlay.options_frame.isHidden())
        for action in (self.wall.action, *self.wall.openings.tool_actions):
            action.trigger()
            bar.refresh()
            self.assertFalse(overlay.options_frame.isHidden(), action.text())
            activate_select(self.app)
            bar.refresh()
            self.assertTrue(overlay.options_frame.isHidden(), action.text())

    def assert_overlay_heights(self):
        """All visible panels must match their fresh Qt layout size hints."""
        overlay = self.window._arquitetura_parametrica_overlay_dock
        APP.processEvents()
        actual_height = overlay.height()
        expected_height = overlay.sizeHint().height()
        if actual_height != expected_height:
            diagnostic = dict(
                actual=actual_height, expected=expected_height,
                frame_hidden=overlay.options_frame.isHidden(),
                frame_height=overlay.options_frame.height(),
                frame_hint=overlay.options_frame.sizeHint().height(),
                row_height=self.row.height(),
                row_hint=self.row.sizeHint().height(),
                context=overlay.bar._context_key(),
                queued=overlay._layout_request_queued,
                busy=overlay._repositioning,
            )
            overlay.reposition()
            diagnostic["after_direct_reposition"] = overlay.height()
            self.fail(f"Overlay failed to track size hints: {diagnostic}")
        self.assertEqual(self.row.height(), self.row.sizeHint().height())
        if not overlay.options_frame.isHidden():
            self.assertEqual(
                overlay.options_frame.height(),
                overlay.options_frame.sizeHint().height())
            self.assertEqual(
                overlay.bar.height(), overlay.bar.sizeHint().height())

    def test_hidden_content_changed_then_shown_recomputes_height(self):
        from OpenTrace_BIM.host import activate_select
        self.show_window()
        bar = self.window._arquitetura_parametrica_overlay_dock.bar
        self.wall.openings.tool_actions[0].trigger()
        bar.refresh()
        self.assert_overlay_heights()
        activate_select(self.app)
        bar.refresh()
        self.assertTrue(bar.overlay_dock.options_frame.isHidden())
        self.assert_overlay_heights()
        # Switch its internal content while hidden, then return to same tool.
        self.wall.openings.opening_tool.set_shape("circle")
        self.wall.openings.tool_actions[0].trigger()
        bar.refresh()
        self.assertFalse(bar.overlay_dock.options_frame.isHidden())
        self.assert_overlay_heights()
        self.wall.openings.opening_tool.set_shape("rect")
        bar.refresh()
        self.assert_overlay_heights()
        activate_select(self.app)

    def test_collapse_expand_recomputes_height(self):
        self.show_window()
        self.wall.action.trigger()
        bar = self.window._arquitetura_parametrica_overlay_dock.bar
        bar.refresh()
        self.assert_overlay_heights()
        bar.toggle_collapsed()
        self.assertTrue(bar._collapsed)
        self.assert_overlay_heights()
        bar.toggle_collapsed()
        self.assertFalse(bar._collapsed)
        self.assert_overlay_heights()

    def test_compact_tool_row_recomputes_height(self):
        self.show_window()
        self.wall.action.trigger()
        self.window._arquitetura_parametrica_overlay_dock.bar.refresh()
        original = self.row.compact
        try:
            self.row.set_compact(not original)
            self.assert_overlay_heights()
            self.row.set_compact(original)
            self.assert_overlay_heights()
        finally:
            self.row.set_compact(original)

    def test_panels_follow_viewport_resize(self):
        self.show_window()
        w = self.window
        overlay = w._arquitetura_parametrica_overlay_dock
        # Force the native toolbar overflow, without modifying its actions.
        w.resize(630, 900)
        APP.processEvents()
        self.assertEqual(overlay.x(), 8)
        self.assertLessEqual(overlay.x() + overlay.width(), w.viewport.width())
        self.assertLessEqual(overlay.options_frame.width(), w.viewport.width() - 16)
        extension = self.row.toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
        self.assertIsNotNone(extension, "Qt's native toolbar overflow button must exist")
        self.assertTrue(extension.isVisible(), "The tool strip must overflow in a narrow viewport")
        w.resize(1500, 900)
        APP.processEvents()

    def test_click_on_panel_does_not_reach_tool(self):
        from OpenTrace_BIM.host import activate_select
        self.show_window()
        self.wall.action.trigger()
        tool = self.window.viewport.active_tool
        recorded = []
        original = tool.on_click
        def observe(*args, **kwargs):
            recorded.append((args, kwargs))
            return original(*args, **kwargs)
        tool.on_click = observe
        try:
            frame = self.window._arquitetura_parametrica_overlay_dock.options_frame
            QTest.mouseClick(frame, Qt.LeftButton, pos=QPoint(2, 2))
            QTest.mouseDClick(self.row, Qt.LeftButton, pos=QPoint(2, 2))
            APP.processEvents()
            self.assertEqual(recorded, [])
        finally:
            tool.on_click = original
            activate_select(self.app)

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
        self.assertEqual(fresh.toolbar.iconSize(), QSize(16, 16))
        fresh.setParent(None)
        fresh.deleteLater()

        row.compact_button.click()
        APP.processEvents()
        self.assertFalse(row.compact)
        self.assertFalse(QSettings().value(COMPACT_KEY, True, type=bool))
        self.assertEqual(row.sizeHint().height(), normal_height)

    def test_host_restore_state_cannot_reposition_overlay(self):
        self.show_window()
        w = self.window
        overlay = w._arquitetura_parametrica_overlay_dock
        old = overlay.pos()
        state = w.saveState()
        self.assertTrue(w.restoreState(state))
        APP.processEvents()
        self.assertEqual(overlay.pos(), old)
        self.assertIs(overlay.parentWidget(), w.viewport)
        self.assertEqual(w.toolBarArea(self.row.toolbar), Qt.NoToolBarArea)


if __name__ == "__main__":
    unittest.main()
