# SPDX-License-Identifier: GPL-3.0-or-later
"""Compact, genuine collapsible sections for existing OpenTrace editor widgets.

The original QObject editors are retained. No alternate BIM state, validators,
Undo handlers or geometrical tools are constructed here.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QToolButton, QVBoxLayout, QWidget


class EditorSection(QFrame):
    def __init__(self, title, widget, *, parent=None, collapsed=False):
        super().__init__(parent)
        self.setObjectName("opentrace_editor_section")
        outer=QVBoxLayout(self)
        outer.setContentsMargins(1,3,1,3)
        outer.setSpacing(2)
        self.toggle=QToolButton(self)
        self.toggle.setObjectName("opentrace_section_toggle")
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(not collapsed)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.DownArrow if not collapsed else Qt.RightArrow)
        self.toggle.setAccessibleName(title)
        self.toggle.setToolTip("Expandir ou recolher " + title)
        self.toggle.setStyleSheet(
            "QToolButton{font-weight:600;text-align:left;"
            "border:0;border-bottom:1px solid palette(mid);padding:6px;}"
            "QToolButton:hover{background:palette(midlight);}")
        outer.addWidget(self.toggle)
        # Collapse the containing body, not the controller's widget itself.
        # Controller code may call widget.show()/hide() on scene selection.
        self.body=QWidget(self)
        content=QVBoxLayout(self.body)
        content.setContentsMargins(6,4,6,4)
        content.setSpacing(4)
        content.addWidget(widget)
        outer.addWidget(self.body)
        self.toggle.toggled.connect(self.set_expanded)
        self.set_expanded(not collapsed)

    def set_expanded(self, expanded):
        self.body.setVisible(bool(expanded))
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
