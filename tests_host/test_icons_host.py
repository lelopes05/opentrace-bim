# SPDX-License-Identifier: GPL-3.0-or-later
"""Rendered icons under real Qt and IngeTrazo palettes, not mocked imports."""
import gc
import os
from pathlib import Path
import unittest

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QPixmapCache
from PySide6.QtWidgets import QApplication
from views.theme import dark_palette, light_palette

from OpenTrace_BIM.icons import _NAMES, icon, pixmap
from OpenTrace_BIM.style import contrast, tokens

APP = QApplication.instance() or QApplication([])


def tearDownModule():
    # Explicitly release cached C++ painter paths before Python shuts down.
    # Native Qt wrappers freed by interpreter GC can crash Shiboken offscreen.
    from OpenTrace_BIM.icons import _parts
    _parts.cache_clear()
    # Avoid leaving native palette / image references until interpreter shutdown.
    IconHostTests.dark = None
    IconHostTests.light = None
    QPixmapCache.clear()
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    APP.processEvents()
    gc.collect()


def rgba_key(pm):
    image = pm.toImage()
    return tuple(image.pixel(x, y) for y in range(image.height())
                 for x in range(image.width()))


def opaque_mean(pm):
    image = pm.toImage()
    colours = [image.pixelColor(x, y)
               for y in range(image.height())
               for x in range(image.width())
               if image.pixelColor(x, y).alpha() >= 224]
    if not colours:
        raise AssertionError("No opaque stroke pixels detected.")
    return QColor(round(sum(v.red() for v in colours) / len(colours)),
                  round(sum(v.green() for v in colours) / len(colours)),
                  round(sum(v.blue() for v in colours) / len(colours)))


class IconHostTests(unittest.TestCase):
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
        sheet = QPixmap(width, height)
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
