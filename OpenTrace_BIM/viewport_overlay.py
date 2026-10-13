# SPDX-License-Identifier: GPL-3.0-or-later
"""Floating panels pinned to the top-left corner of the 3D view.

The tool row and the options bar are children of the viewport, not host
toolbars: the host re-applies its saved window layout (``restoreState``) and
packs every toolbar it knows, and a widget outside that mechanism cannot be
moved by it.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

MARGIN = 8
SPACING = 6
PANEL_RADIUS = 8


def style_panel(panel):
    """Rounded panel painted with the host palette (no colour of its own)."""
    panel.setAttribute(Qt.WA_StyledBackground, True)
    panel.setStyleSheet(
        f"QFrame#{panel.objectName()} {{"
        " background: palette(window); color: palette(window-text);"
        f" border: 1px solid palette(mid); border-radius: {PANEL_RADIUS}px; }}")


class OverlayDock(QWidget):
    """Stacks ``panels`` top to bottom, 8 px from the viewport's top-left."""

    def __init__(self, viewport, panels):
        super().__init__(viewport)
        self.setObjectName("opentrace_overlay_dock")
        # Clicks and wheel turns the panels do not use stop here instead of
        # reaching the viewport and its active tool.
        self.setAttribute(Qt.WA_NoMousePropagation, True)
        self.panels = list(panels)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING)
        for panel in self.panels:
            layout.addWidget(panel, 0, Qt.AlignLeft)
        viewport.installEventFilter(self)
        self.place()
        self.show()

    def place(self):
        viewport = self.parentWidget()
        self.setMaximumWidth(max(0, viewport.width() - 2 * MARGIN))
        self.setMaximumHeight(max(0, viewport.height() - 2 * MARGIN))
        self.adjustSize()
        self.move(MARGIN, MARGIN)

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Resize:
            self.place()
        return False

    def event(self, event):
        if event.type() == QEvent.LayoutRequest:
            self.place()
        return super().event(event)
