# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure WCAG checks: this module does not import Qt or the host."""
import re
import unittest
from pathlib import Path

from OpenTrace_BIM.style import ACCENTS, contrast, ensure_contrast, luminance


# These pre-existing colours are replaced only in the 6b/7b widget wiring.
# Exact counts, not lower bounds: adding a hard-coded colour fails immediately.
KNOWN_FIXED_COLOURS = {
    "architecture_contracts.py": 1,
    "beam_ui.py": 2,
    "column_ui.py": 3,
    "membrane_ui.py": 1,
    "profile_editor.py": 2,
    "slab_ui.py": 6,
    "ui.py": 10,
    "wall_opening_ui.py": 2,
}


class StyleContrastTests(unittest.TestCase):
    def test_wcag_reference_ratios(self):
        self.assertAlmostEqual(luminance("#000000"), 0.0)
        self.assertAlmostEqual(luminance("#FFFFFF"), 1.0)
        self.assertAlmostEqual(contrast("#000000", "#FFFFFF"), 21.0)
        self.assertAlmostEqual(contrast("#777777", "#FFFFFF"), 4.48, places=2)

    def test_ensure_contrast_preserves_hue(self):
        import colorsys

        original = "#556688"
        result = ensure_contrast(original, "#FFFFFF", 7.0)
        self.assertGreaterEqual(contrast(result, "#FFFFFF"), 7.0)
        a = tuple(int(original[i:i + 2], 16) / 255 for i in (1, 3, 5))
        b = tuple(int(result[i:i + 2], 16) / 255 for i in (1, 3, 5))
        self.assertAlmostEqual(colorsys.rgb_to_hls(*a)[0],
                               colorsys.rgb_to_hls(*b)[0], delta=0.02)

    def test_approved_accents_on_reference_panels(self):
        grounds = {
            "dark": {"panel": "#2A2C2F", "field": "#1E2022"},
            "light": {"panel": "#F4F5F6", "field": "#FFFFFF"},
        }
        for theme, fixed in ACCENTS.items():
            with self.subTest(theme=theme):
                panel = grounds[theme]["panel"]
                field = grounds[theme]["field"]
                self.assertGreaterEqual(contrast(fixed["on-petrol"], fixed["petrol"]), 4.5)
                self.assertGreaterEqual(contrast(fixed["petrol-edge"], panel), 3.0)
                self.assertGreaterEqual(contrast(fixed["orange"], panel), 3.0)
                self.assertGreaterEqual(contrast(fixed["orange"], field), 3.0)
                self.assertGreaterEqual(contrast(fixed["focus-ring"], panel), 3.0)

    def test_no_fixed_colours_outside_style_and_icons(self):
        root = Path(__file__).resolve().parents[1] / "OpenTrace_BIM"
        pattern = re.compile(r"#[0-9A-Fa-f]{6}\b")
        seen = {}
        for source in root.glob("*.py"):
            if source.name in ("style.py", "icons.py"):
                continue
            count = len(pattern.findall(source.read_text(encoding="utf-8")))
            if count:
                seen[source.name] = count
        self.assertEqual(seen, KNOWN_FIXED_COLOURS)


if __name__ == "__main__":
    unittest.main()
