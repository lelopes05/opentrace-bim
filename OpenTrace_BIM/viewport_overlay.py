# SPDX-License-Identifier: GPL-3.0-or-later
"""Viewport-owned floating controls, independent of QMainWindow toolbar state."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget


_POINTER_EVENTS = frozenset((
    QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
    QEvent.MouseButtonDblClick, QEvent.MouseMove,
    QEvent.Wheel, QEvent.ContextMenu,
    QEvent.DragEnter, QEvent.DragMove, QEvent.DragLeave, QEvent.Drop,
))


class _BlockViewportInput:
    """Consume unused pointer events rather than forwarding them to GL tools."""

    def event(self, event):
        if event.type() in _POINTER_EVENTS:
            event.accept()
            return True
        return super().event(event)


class OverlayFrame(_BlockViewportInput, QFrame):
    """A styled, input-opaque panel even when an empty area is clicked."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "OverlayFrame { background: palette(window); "
            "color: palette(window-text); border-radius: 8px; }"
        )


class OverlayDock(_BlockViewportInput, QWidget):
    """Two stacked panels anchored eight pixels inside the real viewport."""

    MARGIN = 8

    def __init__(self, viewport, tool_row, contextual_bar):
        super().__init__(viewport)
        self.setObjectName("opentrace_overlay_dock")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#opentrace_overlay_dock { background: transparent; }")
        self.setMinimumWidth(0)
        self.row = tool_row
        self.bar = contextual_bar

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(tool_row)
        self.options_frame = OverlayFrame(self)
        self.options_frame.setObjectName("opentrace_options_frame")
        options_layout = QHBoxLayout(self.options_frame)
        options_layout.setContentsMargins(3, 3, 3, 3)
        options_layout.addWidget(contextual_bar)
        layout.addWidget(self.options_frame)

        viewport.installEventFilter(self)
        self.reposition()
        self.show()
        self.raise_()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() in (QEvent.Resize, QEvent.Show):
            self.reposition()
        return False

    def reposition(self):
        viewport = self.parentWidget()
        if viewport is None:
            return
        available = max(1, viewport.width() - 2 * self.MARGIN)
        self.setMaximumWidth(available)
        self.row.setMaximumWidth(available)
        self.options_frame.setMaximumWidth(available)
        self.adjustSize()
        preferred = max(self.row.sizeHint().width(), self.options_frame.sizeHint().width())
        self.resize(min(preferred, available), self.sizeHint().height())
        self.move(self.MARGIN, self.MARGIN)
