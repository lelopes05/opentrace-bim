# SPDX-License-Identifier: GPL-3.0-or-later
"""The architecture tools inside a viewport-owned floating frame.

All actions are the existing host-registered QActions. The child toolbar is
never registered with QMainWindow and retains Qt's native overflow chevron.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolBar, QToolButton

from .i18n import t
from .viewport_overlay import OverlayDock, OverlayFrame

COMPACT_KEY = "OpenTrace_BIM/tool_row_compact"
NORMAL_ICON = 24
COMPACT_ICON = 16


class ToolRow(OverlayFrame):
    def __init__(self, parent, wall, slab, column, beam, profile):
        super().__init__(parent)
        self.setObjectName("opentrace_tools_row")
        self.setMinimumWidth(0)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(3)
        self.brand = QLabel("OpenTrace BIM", self)
        self.brand.setObjectName("opentrace_tool_brand")
        self.brand.setStyleSheet("font-weight: 700; padding: 0px 4px;")
        layout.addWidget(self.brand)
        self.toolbar = QToolBar(t("OpenTrace BIM · Ferramentas"), self)
        self.toolbar.setObjectName("opentrace_tool_strip")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setMinimumWidth(0)
        self.toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toolbar.setStyleSheet(
            "QToolBar { background: palette(window); color: palette(window-text); "
            "border: 0px; spacing: 2px; }"
        )
        layout.addWidget(self.toolbar, 1)

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

        # Header and controls stay visible when the internal toolbar overflows.
        self.help_button = QToolButton(self)
        self.help_button.setObjectName("opentrace_tool_help")
        self.help_button.setText("?")
        self.help_button.setToolTip(t("Ajuda da ferramenta ativa"))
        self.help_button.setAccessibleName(t("Ajuda contextual"))
        self.help_button.setFixedSize(28, 28)
        layout.addWidget(self.help_button)
        self.compact_button = QToolButton(self)
        self.compact_button.clicked.connect(self.toggle_compact)
        layout.addWidget(self.compact_button)
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
        self.updateGeometry()
        container = self.parentWidget()
        if isinstance(container, OverlayDock):
            container.reposition()

    def toggle_compact(self):
        self.set_compact(not self.compact)
        QSettings().setValue(COMPACT_KEY, self.compact)
