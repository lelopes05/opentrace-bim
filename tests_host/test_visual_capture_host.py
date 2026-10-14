# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture ACTUAL host widgets for visual review, in isolated locale processes.

No plugin mocks, module patching, image simulation or product-code changes.
Run once per host language via OPENTRACE_VISUAL_LANG=en|pt-BR.
The GitHub Actions job runs the two languages in separate Python processes
because multiple MainWindow lifetimes can crash offscreen Qt at shutdown.
"""
from __future__ import annotations

import gc
import json
import os
from pathlib import Path
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QLabel
from core.i18n import current_language, set_language
from views.theme import dark_palette, light_palette

APP = QApplication.instance() or QApplication([])
_SHARED = {}
LANG = os.environ.get("OPENTRACE_VISUAL_LANG", "")


def shared_window():
    if not _SHARED:
        from views.extension_api import ExtensionApp
        from views.main_window import MainWindow
        from OpenTrace_BIM import setup

        set_language(LANG)
        window = MainWindow(defer_extensions=True)
        window.resize(1750, 940)
        window.show()
        APP.processEvents()
        app = ExtensionApp(window, "OpenTrace_BIM")
        setup(app)
        APP.processEvents()
        _SHARED.update(window=window, app=app)
    return _SHARED["window"], _SHARED["app"]


def tearDownModule():
    window = _SHARED.pop("window", None)
    _SHARED.clear()
    if window is not None:
        window.deleteLater()
        APP.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()
    gc.collect()


@unittest.skipUnless(LANG in ("en", "pt-BR"), "Captures run in their separate CI job")
class ActualHostVisualCaptureTests(unittest.TestCase):
    def test_actual_row_bar_and_sidebar_in_both_themes(self):
        window, app = shared_window()
        self.assertEqual(current_language(), LANG)
        self.assertFalse(window._arquitetura_parametrica_startup_errors)

        overlay = window._arquitetura_parametrica_overlay_dock
        row = window._arquitetura_parametrica_tool_row
        suite = window._arquitetura_parametrica_suite_panel
        self.assertIsNotNone(overlay)
        self.assertIsNotNone(row)
        self.assertIsNotNone(suite)
        bar = overlay.bar
        row.set_compact(False)
        APP.processEvents()

        wall = window._arquitetura_parametrica_controller
        openings = wall.openings.tool_actions
        actions = (
            ("wall", wall.action),
            ("slab", window._arquitetura_parametrica_slab_controller.action),
            ("column", window._arquitetura_parametrica_column_controller.action),
            ("beam", window._arquitetura_parametrica_beam_controller.action),
            ("opening", openings[0]),
            ("door", openings[1]),
            ("window", openings[2]),
        )

        root = Path(os.environ.get("OPENTRACE_CAPTURE_DIR", "visual_captures")) / LANG
        manifest = {
            "language": LANG,
            "commit": os.environ.get("GITHUB_SHA", "local"),
            "host_language": current_language(),
            "screenshots": [],
        }
        for theme, palette in (("dark", dark_palette()), ("light", light_palette())):
            APP.setPalette(palette)
            APP.processEvents()
            overlay.apply_theme()
            APP.processEvents()
            folder = root / theme
            folder.mkdir(parents=True, exist_ok=True)
            self._capture(suite.panel, folder / "sidebar.png")
            for tool, action in actions:
                with self.subTest(language=LANG, theme=theme, tool=tool):
                    action.trigger()
                    bar.refresh()
                    overlay.reposition()
                    APP.processEvents()
                    APP.processEvents()
                    self.assertEqual(bar._key, tool)
                    self.assertTrue(row.isVisible())
                    self.assertTrue(bar.isVisible())
                    for name, widget in (
                        ("row", row),
                        ("bar", bar),
                        ("overlay", overlay),
                    ):
                        file = folder / f"{tool}_{name}.png"
                        self._capture(widget, file)
                        manifest["screenshots"].append(str(file))
                    manifest.setdefault("tools", {})[tool] = {
                        "action_text": action.text(),
                        "bar_page": bar._key,
                        "bar_title": bar.pages[tool][0].findChild(
                            QLabel,
                            "opentrace_context_name",
                        ).text(),
                    }

        root.mkdir(parents=True, exist_ok=True)
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _capture(self, widget, path):
        self.assertGreater(widget.width(), 0)
        self.assertGreater(widget.height(), 0)
        pixmap = widget.grab()
        self.assertFalse(pixmap.isNull(), str(path))
        self.assertTrue(pixmap.save(str(path), "PNG"), str(path))


if __name__ == "__main__":
    unittest.main()
