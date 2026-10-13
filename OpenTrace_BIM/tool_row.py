# SPDX-License-Identifier: GPL-3.0-or-later
"""A fixed, collapsible toolbar for the registered architecture tool actions."""
from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import QToolBar, QToolButton

from .i18n import t


class ToolRow(QToolBar):
    """One row of existing actions, independent of the context options bar."""

    SETTINGS_KEY = "OpenTrace_BIM/tool_row_compact"

    def __init__(self, app, wall, slab, column, beam, profiles):
        super().__init__(t("OpenTrace BIM · Ferramentas"), app.window)
        self.setObjectName("opentrace_tools_toolbar")
        self.setMovable(False)
        self.setFloatable(False)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(24, 24))

        # Keep the wall's existing split button and its original dropdown.
        self.wall_button = wall.wall_menu_button
        wall_widget_action = self.addWidget(self.wall_button)
        wall_widget_action.setText(wall.action.text())
        self.tool_actions = [wall.action]
        for controller in (slab, column, beam):
            if controller is not None:
                self.addAction(controller.action)
                self.tool_actions.append(controller.action)
        self.addSeparator()
        for action in wall.openings.tool_actions:
            self.addAction(action)
            self.tool_actions.append(action)
        self.addSeparator()
        if profiles is not None:
            self.addAction(profiles.action)
            self.tool_actions.append(profiles.action)

        self.collapse_button = QToolButton(self)
        self.collapse_button.setObjectName("opentrace_tool_row_collapse")
        self.collapse_button.clicked.connect(self.toggle_compact)
        self.addWidget(self.collapse_button)
        self._compact = False
        self.set_compact(QSettings().value(self.SETTINGS_KEY, False, type=bool),
                         persist=False)

        window = app.window
        window.insertToolBar(wall.toolbar, self)
        if not window.toolBarBreak(self):
            window.insertToolBarBreak(self)
        if not window.toolBarBreak(wall.toolbar):
            window.insertToolBarBreak(wall.toolbar)

    def set_compact(self, compact, *, persist=True):
        self._compact = bool(compact)
        style = (Qt.ToolButtonIconOnly if self._compact
                 else Qt.ToolButtonTextBesideIcon)
        self.setToolButtonStyle(style)
        self.setIconSize(QSize(16, 16) if self._compact else QSize(24, 24))
        self.wall_button.setToolButtonStyle(style)
        self.wall_button.setIconSize(self.iconSize())
        self.collapse_button.setText("▾" if self._compact else "▴")
        self.collapse_button.setToolTip(t("Expandir ferramentas") if self._compact
                                       else t("Recolher ferramentas"))
        for action in self.tool_actions:
            if not action.toolTip():
                action.setToolTip(action.text())
        self.updateGeometry()
        if persist:
            QSettings().setValue(self.SETTINGS_KEY, self._compact)

    def toggle_compact(self):
        self.set_compact(not self._compact)
