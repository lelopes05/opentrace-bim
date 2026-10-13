# SPDX-License-Identifier: GPL-3.0-or-later
"""The tool row: a floating panel with every OpenTrace tool.

It only references actions the controllers already own, so choosing a tool
here is the same act as choosing it in the menu or in F3. It is a panel over
the 3D view (see viewport_overlay), above the options bar; its plain
QToolBar is never handed to the host window.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolBar, QToolButton

from .i18n import t
from .viewport_overlay import style_panel

COMPACT_KEY = "OpenTrace_BIM/tool_row_compact"
NORMAL_ICON = 24
COMPACT_ICON = 16


class ToolRow(QFrame):
    def __init__(self, wall, slab, column, beam, profile):
        super().__init__()
        self.setObjectName("opentrace_tool_row")
        style_panel(self)
        self.toolbar = QToolBar(t("OpenTrace BIM · Ferramentas"), self)
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self.toolbar)
        self._buttons = [wall.wall_menu_button]
        self.toolbar.addWidget(wall.wall_menu_button)
        for controller in (slab, column, beam):
            if controller is not None:
                self._add(controller.action)
        self.toolbar.addSeparator()
        for action in wall.openings.tool_actions:
            self._add(action)
        self.toolbar.addSeparator()
        if profile is not None:
            self._add(profile.action)
        self.compact_button = QToolButton(self)
        self.compact_button.clicked.connect(self.toggle_compact)
        self.toolbar.addWidget(self.compact_button)
        self.set_compact(self.saved_compact())

    @staticmethod
    def saved_compact():
        return QSettings().value(COMPACT_KEY, False, type=bool)

    def _add(self, action):
        self.toolbar.addAction(action)
        self._buttons.append(self.toolbar.widgetForAction(action))

    def set_compact(self, compact):
        self.compact = bool(compact)
        size = QSize(COMPACT_ICON, COMPACT_ICON) if self.compact else QSize(NORMAL_ICON, NORMAL_ICON)
        style = Qt.ToolButtonIconOnly if self.compact else Qt.ToolButtonTextBesideIcon
        self.toolbar.setIconSize(size)
        self.toolbar.setToolButtonStyle(style)
        for button in self._buttons:
            button.setIconSize(size)
            button.setToolButtonStyle(style)
        self.compact_button.setText("▾" if self.compact else "▴")
        self.compact_button.setToolTip(
            t("Expandir a fileira de ferramentas") if self.compact
            else t("Recolher a fileira de ferramentas"))

    def toggle_compact(self):
        self.set_compact(not self.compact)
        QSettings().setValue(COMPACT_KEY, self.compact)
