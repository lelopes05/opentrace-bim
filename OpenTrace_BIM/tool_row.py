# SPDX-License-Identifier: GPL-3.0-or-later
"""The tool row: one fixed toolbar line with every OpenTrace tool.

It only references actions the controllers already own, so choosing a tool
here is the same act as choosing it in the menu or in F3. It sits on its own
line below the host toolbars and above the options bar.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import QToolBar, QToolButton

from .i18n import t

COMPACT_KEY = "OpenTrace_BIM/tool_row_compact"
NORMAL_ICON = 24
COMPACT_ICON = 16


class ToolRow(QToolBar):
    def __init__(self, window, wall, slab, column, beam, profile):
        super().__init__(t("OpenTrace BIM · Ferramentas"), window)
        self.setObjectName("opentrace_tools_toolbar")
        self.setMovable(False)
        self.setFloatable(False)
        self._buttons = [wall.wall_menu_button]
        self.addWidget(wall.wall_menu_button)
        for controller in (slab, column, beam):
            if controller is not None:
                self._add(controller.action)
        self.addSeparator()
        for action in wall.openings.tool_actions:
            self._add(action)
        self.addSeparator()
        if profile is not None:
            self._add(profile.action)
        self.compact_button = QToolButton(self)
        self.compact_button.clicked.connect(self.toggle_compact)
        self.addWidget(self.compact_button)
        self.set_compact(self.saved_compact())

    @staticmethod
    def saved_compact():
        return QSettings().value(COMPACT_KEY, False, type=bool)

    def _add(self, action):
        self.addAction(action)
        self._buttons.append(self.widgetForAction(action))

    def set_compact(self, compact):
        self.compact = bool(compact)
        size = QSize(COMPACT_ICON, COMPACT_ICON) if self.compact else QSize(NORMAL_ICON, NORMAL_ICON)
        style = Qt.ToolButtonIconOnly if self.compact else Qt.ToolButtonTextBesideIcon
        self.setIconSize(size)
        self.setToolButtonStyle(style)
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

    def place_above(self, window, bar):
        """Own line between the host toolbars and ``bar``."""
        window.insertToolBar(bar, self)
        for toolbar in (bar, self):
            if not window.toolBarBreak(toolbar):
                window.insertToolBarBreak(toolbar)
