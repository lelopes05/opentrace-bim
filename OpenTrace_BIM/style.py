# SPDX-License-Identifier: GPL-3.0-or-later
"""OpenTrace design tokens and WCAG contrast, independent of host theme internals."""
from __future__ import annotations

import colorsys
from math import isfinite


ACCENTS = {
    "dark": {
        "petrol": "#3A7780", "petrol-edge": "#6FB1BB",
        "on-petrol": "#FFFFFF", "orange": "#F0A36B",
        "focus-ring": "#9ED0D8",
    },
    "light": {
        "petrol": "#2F6670", "petrol-edge": "#245560",
        "on-petrol": "#FFFFFF", "orange": "#B35C22",
        "focus-ring": "#1F5560",
    },
}

SIZES = {
    "space-1": 2, "space-2": 4, "space-3": 6,
    "space-4": 8, "space-5": 12, "space-6": 16,
    "panel-inset": 8, "radius-panel": 8, "radius-control": 4,
    "border-width": 1, "border-marked": 2,
    "icon-24": 24, "icon-20": 20, "icon-16": 16,
    "tool-height": 40, "tool-height-compact": 28,
    "option-height": 32, "control-height": 28,
    "panel-shadow-y": 8, "panel-shadow-blur": 24,
    "panel-shadow-dark-alpha": 0.38, "panel-shadow-light-alpha": 0.16,
}

TYPE = {
    "brand": {"px": 13, "weight": 700},
    "tool-label": {"px": 12, "weight": 500},
    "section-title": {"px": 12, "weight": 600},
    "field-label": {"px": 11, "weight": 500, "color": "text-muted"},
    "field-value": {"px": 12, "weight": 400, "tabular-numbers": True},
    "hint": {"px": 11, "weight": 400, "color": "text-muted"},
}


def _rgb(color):
    """Convert #RRGGBB, RGB triples, or a QColor without importing Qt."""
    if isinstance(color, str):
        value = color.lstrip("#")
        if len(value) != 6:
            raise ValueError("Expected a six-digit RGB colour.")
        return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    if hasattr(color, "red") and hasattr(color, "green") and hasattr(color, "blue"):
        return color.red() / 255, color.green() / 255, color.blue() / 255
    channels = tuple(color)
    if len(channels) != 3:
        raise ValueError("Expected three colour channels.")
    if any(not isfinite(float(x)) for x in channels):
        raise ValueError("Colour channels must be finite.")
    scale = 255.0 if any(float(x) > 1 for x in channels) else 1.0
    return tuple(float(x) / scale for x in channels)


def _hex(rgb):
    return "#" + "".join(f"{round(max(0, min(1, value)) * 255):02X}" for value in rgb)


def luminance(color):
    """WCAG 2.x relative luminance in sRGB (0..1)."""
    channels = _rgb(color)
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(a, b):
    """WCAG 2.x contrast ratio, from 1 to 21."""
    first, second = sorted((luminance(a), luminance(b)), reverse=True)
    return (first + 0.05) / (second + 0.05)


def _adjust_multi(color, grounds, minimum):
    """Find the nearest HSL lightness satisfying every opaque background."""
    rgb = _rgb(color)
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb)

    def adjusted(level):
        return _hex(colorsys.hls_to_rgb(hue, level, saturation))

    def passes(level):
        candidate = adjusted(level)
        return all(contrast(candidate, ground) + 1e-9 >= minimum
                   for ground in grounds)

    if passes(lightness):
        return _hex(rgb)

    candidates = []
    for endpoint in (0.0, 1.0):
        if not passes(endpoint):
            continue
        low, high = sorted((lightness, endpoint))
        for _ in range(30):
            middle = (low + high) / 2
            if endpoint < lightness:
                low, high = (middle, high) if passes(middle) else (low, middle)
            else:
                low, high = (low, middle) if passes(middle) else (middle, high)
        level = low if endpoint < lightness else high
        # RGB rounding can lose a little contrast; walk towards the endpoint.
        if not passes(level):
            level = max(0, level - 0.001) if endpoint < lightness else min(1, level + 0.001)
        if passes(level):
            candidates.append((abs(level - lightness), adjusted(level)))
    if not candidates:
        raise ValueError("Cannot achieve contrast with the requested hue.")
    return min(candidates)[1]


def ensure_contrast(color, ground, minimum):
    """Adjust only the HSL lightness until WCAG contrast reaches minimum."""
    if minimum < 1 or minimum > 21:
        raise ValueError("Contrast minimum must be between 1 and 21.")
    return _adjust_multi(color, (ground,), minimum)


def _mix(a, b, ratio):
    rgb_a, rgb_b = _rgb(a), _rgb(b)
    return _hex(tuple(x * ratio + y * (1 - ratio) for x, y in zip(rgb_a, rgb_b)))


def _muted(base, text, backgrounds):
    if all(contrast(base, bg) >= 4.5 for bg in backgrounds):
        return base
    # The host's text colour is the limiting readable endpoint.
    for step in range(1, 101):
        mixed = _mix(text, base, step / 100)
        if all(contrast(mixed, bg) >= 4.5 for bg in backgrounds):
            return mixed
    return _adjust_multi(text, backgrounds, 4.5)


def tokens(palette):
    """Return every colour token as QColor, using the host QPalette neutrals."""
    from PySide6.QtGui import QColor, QPalette

    panel = palette.color(QPalette.Window)
    raised = palette.color(QPalette.Button)
    field = palette.color(QPalette.Base)
    text = palette.color(QPalette.WindowText)
    dark = luminance(panel) < luminance(text)
    fixed = ACCENTS["dark" if dark else "light"]
    raw = {
        "panel": panel, "panel-raised": raised, "field": field,
        "text": text,
        "text-disabled": palette.color(QPalette.Disabled, QPalette.WindowText),
        "text-muted": QColor(_muted(
            palette.color(QPalette.PlaceholderText), text, (panel, field))),
        "border": QColor(_adjust_multi(
            palette.color(QPalette.Mid), (panel, field), 3.0)),
    }
    raw.update({key: QColor(value) for key, value in fixed.items()})
    for name, source, alpha in (
        ("panel-edge", "text", 0.12 if dark else 0.08),
        ("hover-wash", "text", 0.08 if dark else 0.06),
        ("divider", "text", 0.08 if dark else 0.10),
    ):
        value = QColor(raw[source])
        value.setAlphaF(alpha)
        raw[name] = value
    raw.update({
        "icon": QColor(raw["text"]),
        "icon-accent": QColor(raw["orange"]),
        "icon-on-active": QColor(raw["on-petrol"]),
        "icon-disabled": QColor(raw["text-disabled"]),
    })
    return raw


def qss(template, palette):
    """Substitute tokens in a stylesheet, including alpha-aware rgba() values."""
    values = {}
    for key, color in tokens(palette).items():
        if color.alpha() == 255:
            values[key] = color.name()
        else:
            values[key] = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alphaF():.3f})"
    return template.format(**values)


def theme_font(font, name):
    """Derive a typography role from the application's QFont, not a bundled font."""
    from PySide6.QtGui import QFont
    spec = TYPE[name]
    face = QFont(font)
    face.setPixelSize(spec["px"])
    face.setWeight(QFont.Weight(spec["weight"]))
    return face


def _create_watcher():
    from PySide6.QtCore import QEvent, QObject, Signal
    from PySide6.QtWidgets import QApplication

    class ThemeWatcher(QObject):
        """One event filter per app; clients connect to the changed signal."""
        changed = Signal()

        def __init__(self):
            app = QApplication.instance()
            if app is None:
                raise RuntimeError("ThemeWatcher requires QApplication.")
            if getattr(app, "_opentrace_theme_watcher", None) is not None:
                raise RuntimeError("ThemeWatcher already installed for this application.")
            super().__init__(app)
            app._opentrace_theme_watcher = self
            app.installEventFilter(self)

        def eventFilter(self, obj, event):
            if obj is self.parent() and event.type() == QEvent.ApplicationPaletteChange:
                self.changed.emit()
            return False

    return ThemeWatcher


ThemeWatcher = _create_watcher()
