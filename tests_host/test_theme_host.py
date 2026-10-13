# SPDX-License-Identifier: GPL-3.0-or-later
"""Design tokens against the actual IngeTrazo palettes; no plugin mocks."""
import gc
import unittest

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
from views.theme import dark_palette, light_palette

from OpenTrace_BIM.style import ThemeWatcher, contrast, qss, tokens


APP = QApplication.instance() or QApplication([])


def tearDownModule():
    gc.collect()


class ThemeHostTests(unittest.TestCase):
    def tearDown(self):
        watcher = getattr(self, "_watcher", None)
        if watcher is not None:
            APP.setPalette(self._old_palette)
            APP.processEvents()
            watcher.changed.disconnect(self._on_change)
            watcher.close()
            self._watcher = None
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()

    def test_tokens_meet_contrast_in_both_themes(self):
        for palette in (dark_palette(), light_palette()):
            with self.subTest(theme=palette.color(QPalette.Window).name()):
                result = tokens(palette)
                for ground in ("panel", "field"):
                    for fg in ("text", "text-muted"):
                        self.assertGreaterEqual(
                            contrast(result[fg], result[ground]), 4.5,
                            f"{fg} against {ground}")
                    self.assertGreaterEqual(
                        contrast(result["border"], result[ground]), 3.0,
                        f"border against {ground}")
                self.assertEqual(result["panel"], palette.color(QPalette.Window))
                self.assertEqual(result["field"], palette.color(QPalette.Base))

    def test_qss_uses_tokens(self):
        palette = dark_palette()
        css = qss("QFrame { background: {panel}; border: 1px solid {border}; }", palette)
        self.assertEqual(css, (
            f'QFrame {{ background: {tokens(palette)["panel"].name()}; '
            f'border: 1px solid {tokens(palette)["border"].name()}; }}'))
        with self.assertRaisesRegex(KeyError, "missing-token"):
            qss("QFrame { color: {missing-token}; }", palette)

    def test_theme_watcher_emits_once_per_application_change(self):
        self._old_palette = APP.palette()
        self._watcher = ThemeWatcher()
        counter = []

        def on_change():
            counter.append(True)

        self._on_change = on_change
        self._watcher.changed.connect(self._on_change)
        self.assertIs(self._watcher.parent(), APP)
        self.assertIs(APP._opentrace_theme_watcher, self._watcher)
        APP.setPalette(dark_palette())
        APP.processEvents()
        counter.clear()
        APP.setPalette(light_palette())
        APP.processEvents()
        self.assertEqual(counter, [True])


if __name__ == "__main__":
    unittest.main()
