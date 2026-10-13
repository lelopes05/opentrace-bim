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
        self.setAcceptDrops(True)
        self.setStyleSheet(
            "OverlayFrame { background: palette(window); "
            "color: palette(window-text); border-radius: 8px; }"
        )


class OverlayDock(_BlockViewportInput, QWidget):
    """Two stacked panels anchored eight pixels inside the real viewport."""

    MARGIN = 8

    def __init__(self, viewport, tool_row, suite):
        super().__init__(viewport)
        self.setObjectName("opentrace_overlay_dock")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setStyleSheet("QWidget#opentrace_overlay_dock { background: transparent; }")
        self.setMinimumWidth(0)
        self._repositioning = False
        self.row = tool_row

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(tool_row)
        self.options_frame = OverlayFrame(self)
        self.options_frame.setObjectName("opentrace_options_frame")
        options_layout = QHBoxLayout(self.options_frame)
        options_layout.setContentsMargins(3, 3, 3, 3)
        layout.addWidget(self.options_frame)

        from .contextual_bar import ContextualBar
        self.bar = ContextualBar(suite, self)
        suite.context_bar = self.bar
        options_layout.addWidget(self.bar)

        # Qt can send LayoutRequest to the resized child rather than its
        # parent. Observe all size-hint owners to catch those requests too.
        self._layout_sources = (
            self.row, self.row.toolbar, self.options_frame, self.bar, self.bar.stack,
        )
        for widget in self._layout_sources:
            widget.installEventFilter(self)
        viewport.installEventFilter(self)
        self.reposition()
        self.show()
        self.raise_()

    def event(self, event):
        # Qt posts LayoutRequest when child size hints or visibility change.
        # Recalculate even if the contextual page key has not changed.
        result = super().event(event)
        if event.type() == QEvent.LayoutRequest:
            self.reposition()
        return result

    def eventFilter(self, watched, event):
        if watched is self.parentWidget():
            if event.type() in (QEvent.Resize, QEvent.Show):
                self.reposition()
        elif watched in self._layout_sources:
            if event.type() in (QEvent.LayoutRequest, QEvent.Show, QEvent.Hide):
                self.reposition()
        return False

    def reposition(self):
        if self._repositioning:
            return
        self._repositioning = True
        try:
            viewport = self.parentWidget()
            available = max(1, viewport.width() - 2 * self.MARGIN)
            self.setMaximumWidth(available)
            self.row.setMaximumWidth(available)
            self.options_frame.setMaximumWidth(available)
            # Reconcile nested Qt size hints before measuring the dock.
            self.row.layout().activate()
            self.bar.layout().activate()
            self.options_frame.layout().activate()
            self.layout().activate()
            self.adjustSize()
            preferred = max(
                self.row.sizeHint().width(),
                self.options_frame.sizeHint().width()
                if not self.options_frame.isHidden() else 0,
            )
            self.resize(min(preferred, available), self.sizeHint().height())
            self.move(self.MARGIN, self.MARGIN)
        finally:
            self._repositioning = False
