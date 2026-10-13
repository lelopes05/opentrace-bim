# SPDX-License-Identifier: GPL-3.0-or-later
"""Rendered icons under real Qt and IngeTrazo palettes, not mocked imports."""
import gc
import os
from pathlib import Path
import unittest

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication
from views.theme import dark_palette, light_palette

from OpenTrace_BIM.icons import _NAMES, icon, pixmap
from OpenTrace_BIM.style import contrast, tokens

APP = QApplication.instance() or QApplication([])


def tearDownModule():
    # Release the standalone test application's Python owner while Qt modules
    # and its event loop are still alive, instead of during interpreter exit.
    global APP
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    APP.processEvents()
    # All host-test files run in separate processes; dispose their owned Qt
    # application before the CPython finalizer unloads the binding modules.
    from shiboken6 import delete
    delete(APP)
    APP = None
    gc.collect()


def rgba_key(pm):
    image = pm.toImage()
    return tuple(image.pixel(x, y) for y in range(image.height())
                 for x in range(image.width()))


def opaque_mean(pm):
    image = pm.toImage()
    # pixelColor() allocates a PySide QColor wrapper per pixel; thousands of
    # short-lived wrappers can destabilize Shiboken during Python teardown.
    # QImage.pixel() returns the equivalent ARGB integer without Qt wrappers.
    pixels = [image.pixel(x, y)
              for y in range(image.height())
              for x in range(image.width())]
    opaque = [value for value in pixels if (value >> 24) >= 224]
    if not opaque:
        raise AssertionError("No opaque stroke pixels detected.")
    count = len(opaque)
    return QColor(round(sum((v >> 16) & 255 for v in opaque) / count),
                  round(sum((v >> 8) & 255 for v in opaque) / count),
                  round(sum(v & 255 for v in opaque) / count))


class IconHostTests(unittest.TestCase):
    def tearDown(self):
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()

    @classmethod
    def setUpClass(cls):
        # Keep native QPalette values alive while the same icon is repainted.
        # Recreating host palettes on every pixel-level assertion destabilizes
        # PySide6/Shiboken on the offscreen Qt runner.
        cls.dark = dark_palette()
        cls.light = light_palette()

    def test_every_named_icon_works_at_three_sizes(self):
        self.assertEqual(len(_NAMES), len(set(_NAMES)))
        palette = self.dark
        for name in _NAMES:
            for size in (16, 20, 24):
                with self.subTest(name=name, size=size):
                    picture = icon(name, size, palette=palette)
                    self.assertFalse(picture.isNull())
                    self.assertFalse(pixmap(name, size, palette=palette).isNull())

    def test_24px_icons_are_visually_distinct(self):
        pictures = {}
        for name in _NAMES:
            key = rgba_key(pixmap(name, 24, palette=self.dark))
            self.assertNotIn(key, pictures,
                             f"{name} is indistinguishable from {pictures.get(key)}")
            pictures[key] = name

    def test_opaque_average_contrast_in_both_themes(self):
        for palette in (self.dark, self.light):
            for name in _NAMES:
                with self.subTest(name=name, theme=tokens(palette)["panel"].name()):
                    mean = opaque_mean(pixmap(name, 24, palette=palette))
                    self.assertGreaterEqual(
                        contrast(mean, tokens(palette)["panel"]), 3.0)

    def test_normal_differs_from_marked(self):
        for name in _NAMES:
            self.assertNotEqual(
                rgba_key(pixmap(name, 24, "normal", self.dark)),
                rgba_key(pixmap(name, 24, "marked", self.dark)),
                name)

    def test_16px_stroke_is_at_least_1_point_3_pixels(self):
        image = pixmap("anchor_center", 16, palette=self.dark).toImage()
        # Above the anchor rectangle: only its central vertical stroke.
        coverage = sum(image.pixelColor(x, 3).alpha() / 255 for x in range(5, 12))
        self.assertGreaterEqual(coverage, 1.3)

    def test_ci_icon_sheet(self):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            self.skipTest("Icon sheet is generated only on the CI runner.")
        palettes = (("Escuro", self.dark), ("Claro", self.light))
        states = ("normal", "active", "marked", "disabled")
        row_height, cell_width, label_width = 38, 47, 135
        width = label_width + len(palettes) * len(states) * cell_width
        height = 45 + row_height * len(_NAMES)
        # Keep the CI-only contact sheet on a CPU image; no giant
        # platform QPixmap should survive the offscreen test renderer.
        sheet = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        sheet.fill(QColor("#FFFFFF"))
        p = QPainter(sheet)
        font = QFont(APP.font())
        font.setPixelSize(10)
        p.setFont(font)
        p.setPen(QColor("#111111"))
        for theme_index, (heading, pal) in enumerate(palettes):
            for state_index, state in enumerate(states):
                x = label_width + (theme_index * len(states) + state_index) * cell_width
                p.drawText(x, 22, heading[:1] + " " + state[:5])
        for index, name in enumerate(_NAMES):
            y = 45 + index * row_height
            p.setPen(QColor("#111111"))
            p.drawText(4, y + 22, name)
            for ti, (_name, pal) in enumerate(palettes):
                for si, state in enumerate(states):
                    x = label_width + (ti * len(states) + si) * cell_width
                    p.fillRect(x, y, cell_width, row_height,
                               tokens(pal)["panel"])
                    p.drawPixmap(x + 11, y + 7, pixmap(name, 24, state, pal))
        p.end()
        sheet_path = Path(__file__).resolve().parents[1] / "docs" / "icons_sheet.png"
        self.assertTrue(sheet.save(str(sheet_path), "PNG"))


if __name__ == "__main__":
    unittest.main()
