# SPDX-License-Identifier: GPL-3.0-or-later
"""Visual 6b/7b contracts with the real IngeTrazo host and Qt widgets."""
import gc
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QApplication, QDoubleSpinBox, QGraphicsDropShadowEffect, QToolButton,
)
from PySide6.QtTest import QTest
from views.theme import dark_palette, light_palette

from OpenTrace_BIM.style import SIZES, tokens

QCoreApplication.setOrganizationName("OpenTraceTests")
QCoreApplication.setApplicationName("visual-host")
QSettings.setDefaultFormat(QSettings.IniFormat)
_SETTINGS_DIR = tempfile.mkdtemp(prefix="opentrace-tests-settings-")
for _scope in (QSettings.UserScope, QSettings.SystemScope):
    QSettings.setPath(QSettings.IniFormat, _scope, _SETTINGS_DIR)

APP = QApplication.instance() or QApplication([])
_SHARED = {}


def shared_window():
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
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    APP.processEvents()
    gc.collect()


def icon_pixels(button, size):
    image = button.icon().pixmap(size, size).toImage()
    return bytes(image.bits())


class VisualHostTests(unittest.TestCase):
    def setUp(self):
        from OpenTrace_BIM.host import activate_select
        self.window, self.app = shared_window()
        self.old_palette = APP.palette()
        self.row = self.window._arquitetura_parametrica_tool_row
        self.overlay = self.window._arquitetura_parametrica_overlay_dock
        self.bar = self.overlay.bar
        self.suite = self.window._arquitetura_parametrica_suite_panel
        self.wall = self.window._arquitetura_parametrica_controller
        activate_select(self.app)

    def tearDown(self):
        from OpenTrace_BIM.host import activate_select
        APP.setPalette(self.old_palette)
        APP.processEvents()
        activate_select(self.app)
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()

    def _set_theme(self, palette):
        APP.setPalette(palette)
        APP.processEvents()

    def test_active_tool_uses_petrol_on_both_palettes(self):
        self.wall.action.trigger()
        self.assertTrue(self.wall.action.isChecked())
        for palette in (dark_palette(), light_palette()):
            with self.subTest(theme=palette.color(QPalette.Window).name()):
                self._set_theme(palette)
                petrol = tokens(palette)["petrol"].name()
                edge = tokens(palette)["petrol-edge"].name()
                css = self.row.toolbar.styleSheet()
                self.assertIn("background: " + petrol, css)
                self.assertIn("border: 1px solid " + edge, css)
                self.assertTrue(self.row._icon_entries[0][1].isChecked())
                self.assertFalse(self.row._icon_entries[0][0].icon().isNull())
                self.assertIn("color: " + tokens(palette)["on-petrol"].name(), css)

    def test_marked_options_use_orange_border(self):
        self.wall.action.trigger()
        self.bar.refresh()
        for palette in (dark_palette(), light_palette()):
            self._set_theme(palette)
            left = self.bar.findChild(QToolButton, "opentrace_opt_wall_reference_left")
            center = self.bar.findChild(QToolButton, "opentrace_opt_wall_reference_center")
            left.click()
            self.bar.refresh()
            self.assertTrue(left.isChecked())
            self.assertFalse(center.isChecked())
            css = self.bar.styleSheet()
            self.assertIn("QToolButton:checked", css)
            self.assertIn("border: 2px solid " + tokens(palette)["orange"].name(), css)
            self.assertIn("QToolButton { background: " + tokens(palette)["panel-raised"].name()
                          + "; border: 0px;", css)
            center.click()
            self.assertTrue(center.isChecked())
            self.assertFalse(left.isChecked())
        self.wall.alignment.setCurrentIndex(self.wall.alignment.findData("left"))
        self.bar.refresh()

    def test_theme_changes_all_surfaces_without_restart(self):
        self._set_theme(dark_palette())
        dark = (self.row.toolbar.styleSheet(), self.bar.styleSheet(),
                self.suite.panel.styleSheet())
        self._set_theme(light_palette())
        light = (self.row.toolbar.styleSheet(), self.bar.styleSheet(),
                 self.suite.panel.styleSheet())
        for old, new in zip(dark, light):
            self.assertNotEqual(old, new)
        self.assertIs(self.overlay.bar, self.bar)
        self.assertIsNotNone(self.overlay._theme_watcher)

    def test_panel_shadow_design_contract(self):
        for palette, alpha in ((dark_palette(), SIZES["panel-shadow-dark-alpha"]),
                               (light_palette(), SIZES["panel-shadow-light-alpha"])):
            self._set_theme(palette)
            for frame in (self.row, self.overlay.options_frame):
                with self.subTest(panel=frame.objectName(), alpha=alpha):
                    effect = frame.graphicsEffect()
                    self.assertIsInstance(effect, QGraphicsDropShadowEffect)
                    self.assertAlmostEqual(effect.offset().y(), SIZES["panel-shadow-y"])
                    self.assertAlmostEqual(effect.blurRadius(), SIZES["panel-shadow-blur"])
                    self.assertAlmostEqual(effect.color().alphaF(), alpha, places=2)
        self.assertIsNone(self.suite.panel.graphicsEffect())

    def test_distinct_design_icons_in_row_and_segmented_groups(self):
        self._set_theme(dark_palette())
        self.row.set_compact(False)
        size = SIZES["icon-24"]
        row_icons = [button for button, _action, _name in self.row._icon_entries]
        self.assertTrue(all(not button.icon().isNull() for button in row_icons))
        self.assertEqual(len({icon_pixels(button, size) for button in row_icons}),
                         len(row_icons))
        self.row.set_compact(True)
        compact = SIZES["icon-16"]
        self.assertTrue(all(not button.icon().isNull() for button in row_icons))
        self.assertEqual(len({icon_pixels(button, compact) for button in row_icons}),
                         len(row_icons))
        self.row.set_compact(False)

        groups = (
            ("wall", "opentrace_opt_wall_geometry_", 6),
            ("wall", "opentrace_opt_wall_reference_", 3),
            ("wall", "opentrace_opt_wall_type_", 2),
            ("opening", "opentrace_opt_opening_shape_", 4),
            ("opening", "opentrace_opt_opening_anchor_", 3),
            ("beam", "opentrace_opt_beam_reference_", 3),
        )
        for page, prefix, count in groups:
            with self.subTest(group=prefix):
                buttons = [b for b in self.bar.pages[page][0].findChildren(QToolButton)
                           if b.objectName().startswith(prefix)]
                self.assertEqual(len(buttons), count)
                self.assertTrue(all(not b.icon().isNull() for b in buttons))
                self.assertEqual(len({icon_pixels(b, SIZES["icon-20"]) for b in buttons}),
                                 len(buttons))

    def test_segmented_focus_and_fields_return_to_viewport(self):
        self.window.resize(1500, 900)
        self.window.show()
        APP.processEvents()
        self.wall.action.trigger()
        self.bar.refresh()
        viewport = self.window.viewport
        buttons = [b for b in self.bar.pages["wall"][0].findChildren(QToolButton)
                   if b.objectName().startswith("opentrace_opt_")]
        self.assertTrue(buttons)
        self.assertTrue(all(b.focusPolicy() == Qt.NoFocus for b in buttons))
        self.window.activateWindow()
        viewport.setFocus()
        APP.processEvents()
        for button in buttons:
            QTest.mouseClick(button, Qt.LeftButton)
            APP.processEvents()
            self.assertTrue(viewport.hasFocus(), button.objectName())
        spin = next(s for s in self.bar.pages["wall"][0].findChildren(QDoubleSpinBox)
                    if s.isEnabled() and not s.isReadOnly())
        for key in (Qt.Key_Return, Qt.Key_Escape):
            spin.setFocus()
            APP.processEvents()
            self.assertTrue(spin.hasFocus())
            QTest.keyClick(spin, key)
            APP.processEvents()
            self.assertTrue(viewport.hasFocus())


if __name__ == "__main__":
    unittest.main()
