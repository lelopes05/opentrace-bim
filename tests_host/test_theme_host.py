# SPDX-License-Identifier: GPL-3.0-or-later
"""Design tokens against the actual IngeTrazo palettes; no plugin mocks."""
import unittest

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication
from views.theme import dark_palette, light_palette

from OpenTrace_BIM.style import ThemeWatcher, contrast, qss, tokens


APP = QApplication.instance() or QApplication([])


class ThemeHostTests(unittest.TestCase):
    def test_tokens_meet_contrast_in_both_themes(self):
        for palette in (dark_palette(), light_palette()):
            with self.subTest(theme=palette.color(palette.Window).name()):
                result = tokens(palette)
                for ground in ("panel", "field"):
                    for fg in ("text", "text-muted"):
                        self.assertGreaterEqual(
                            contrast(result[fg], result[ground]), 4.5,
                            f"{fg} against {ground}")
                    self.assertGreaterEqual(
                        contrast(result["border"], result[ground]), 3.0,
                        f"border against {ground}")
                self.assertEqual(result["panel"], palette.color(palette.Window))
                self.assertEqual(result["field"], palette.color(palette.Base))

    def test_qss_uses_tokens(self):
        palette = dark_palette()
        css = qss("QWidget { background: {panel}; color: {text}; }", palette)
        self.assertIn(tokens(palette)["panel"].name(), css)
        self.assertIn(tokens(palette)["text"].name(), css)

    def test_theme_watcher_emits_once_per_application_change(self):
        old = APP.palette()
        watcher = ThemeWatcher()
        counter = []
        watcher.changed.connect(lambda: counter.append(True))
        try:
            APP.setPalette(dark_palette())
            APP.processEvents()
            counter.clear()
            APP.setPalette(light_palette())
            APP.processEvents()
            self.assertEqual(counter, [True])
        finally:
            APP.setPalette(old)
            APP.processEvents()
            watcher.deleteLater()
            APP.processEvents()
            APP._opentrace_theme_watcher = None


if __name__ == "__main__":
    unittest.main()
