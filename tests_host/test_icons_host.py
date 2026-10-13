# SPDX-License-Identifier: GPL-3.0-or-later
"""Rendered icons under real Qt and IngeTrazo palettes, not mocked imports."""
import gc
import unittest

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from views.theme import dark_palette, light_palette

from OpenTrace_BIM.icons import _NAMES, icon, pixmap
from OpenTrace_BIM.style import contrast, tokens

APP = QApplication.instance() or QApplication([])


def tearDownModule():
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
        APP.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()

    @classmethod
    def setUpClass(cls):
        # Keep native QPalette values alive while the same icon is repainted.
        # Recreating host palettes on every pixel-level assertion destabilizes
        # PySide6/Shiboken on the offscreen Qt runner.
        cls.dark = dark_palette()
        cls.light = light_palette()

    @classmethod
    def tearDownClass(cls):
        del cls.dark, cls.light
        APP.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()
        gc.collect()

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


if __name__ == "__main__":
    unittest.main()
