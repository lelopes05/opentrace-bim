# SPDX-License-Identifier: GPL-3.0-or-later
"""The architecture tools inside a viewport-owned floating frame.

All actions are the existing host-registered QActions. The child toolbar is
never registered with QMainWindow and retains Qt's native overflow chevron.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QSizePolicy, QToolBar, QToolButton

from .icons import icon
from .i18n import t
from .style import SIZES, qss, theme_font
from .viewport_overlay import OverlayFrame

COMPACT_KEY = "OpenTrace_BIM/tool_row_compact"
NORMAL_ICON = SIZES["icon-24"]
COMPACT_ICON = SIZES["icon-16"]


class ToolRow(OverlayFrame):
    def __init__(self, parent, wall, slab, column, beam, profile):
        super().__init__(parent)
        self.setObjectName("opentrace_tools_row")
        self.setMinimumWidth(0)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIZES["panel-inset"], 3, SIZES["panel-inset"], 3)
        layout.setSpacing(SIZES["space-2"])
        self.brand = QLabel("OpenTrace BIM", self)
        self.brand.setObjectName("opentrace_tool_brand")
        self.logo_slot = QLabel(self)
        self.logo_slot.setObjectName("opentrace_logo_slot")
        self.logo_slot.setFixedSize(NORMAL_ICON, NORMAL_ICON)
        layout.addWidget(self.logo_slot)
        layout.addWidget(self.brand)
        self.toolbar = QToolBar(t("OpenTrace BIM · Ferramentas"), self)
        self.toolbar.setObjectName("opentrace_tool_strip")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setMinimumWidth(0)
        self.toolbar.setFocusPolicy(Qt.NoFocus)
        self.toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.toolbar, 1)

        self._icon_cache = {}
        self._buttons = [wall.wall_menu_button]
        self._icon_entries = [(wall.wall_menu_button, wall.wall_menu_button.defaultAction(), "wall")]
        wall.wall_menu_button.setFocusPolicy(Qt.NoFocus)
        self.toolbar.addWidget(wall.wall_menu_button)
        for controller, name in ((slab, "slab"), (column, "column"), (beam, "beam")):
            if controller is not None:
                self._add(controller.action, name)
        self.toolbar.addSeparator()
        for action, name in zip(wall.openings.tool_actions, ("opening", "door", "window")):
            self._add(action, name)
        self.toolbar.addSeparator()
        if profile is not None:
            self._add(profile.action, "profile")
        for _button, action, _name in self._icon_entries:
            if action is not None:
                action.toggled.connect(self.apply_theme)

        # Header and controls stay visible when the internal toolbar overflows.
        self.help_button = QToolButton(self)
        self.help_button.setObjectName("opentrace_tool_help")
        self.help_button.setText("?")
        self.help_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.help_button.setFocusPolicy(Qt.NoFocus)
        self.help_button.setToolTip(t("Ajuda da ferramenta ativa"))
        self.help_button.setAccessibleName(t("Ajuda contextual"))
        self.help_button.setFixedSize(28, 28)
        layout.addWidget(self.help_button)
        self.compact_button = QToolButton(self)
        self.compact_button.setFocusPolicy(Qt.NoFocus)
        self.compact_button.clicked.connect(self.toggle_compact)
        layout.addWidget(self.compact_button)
        self.set_compact(self.saved_compact())
        self.apply_theme()

    @staticmethod
    def saved_compact():
        return QSettings().value(COMPACT_KEY, False, type=bool)

    def _add(self, action, name):
        self.toolbar.addAction(action)
        button = self.toolbar.widgetForAction(action)
        button.setFocusPolicy(Qt.NoFocus)
        self._buttons.append(button)
        self._icon_entries.append((button, action, name))

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
        self.help_button.setIcon(icon("help", COMPACT_ICON, palette=QApplication.palette()))
        self.compact_button.setIcon(icon("expand" if self.compact else "collapse", COMPACT_ICON,
                                         palette=QApplication.palette()))
        self.compact_button.setText("")
        self.apply_theme()
        self.updateGeometry()

    def _design_icon(self, palette, name, size, state="normal"):
        key = (palette.cacheKey(), name, size, state)
        if key not in self._icon_cache:
            self._icon_cache[key] = icon(name, size, state=state, palette=palette)
        return self._icon_cache[key]

    def apply_theme(self):
        palette = QApplication.palette()
        height = SIZES["tool-height-compact" if self.compact else "tool-height"]
        self.brand.setFont(theme_font(QApplication.font(), "brand"))
        self.brand.setStyleSheet(qss("QLabel { color: {text}; padding: 0 4px; }", palette))
        self.logo_slot.setStyleSheet(qss("QLabel { background: {panel-raised}; "
                                         "border: 1px solid {panel-edge}; border-radius: 4px; }",
                                         palette))
        self.toolbar.setStyleSheet(qss(
            "QToolBar { background: {panel}; color: {text}; border: 0; spacing: 2px; }"
            "QToolButton { color: {text}; background: transparent; border: 1px solid transparent;"
            " border-radius: 4px; padding: 4px; font-size: 12px; font-weight: 500; }"
            "QToolButton:hover:!checked { background: {hover-wash}; }"
            "QToolButton:checked { background: {petrol}; border: 1px solid {petrol-edge};"
            " color: {on-petrol}; }"
            "QToolButton:disabled { color: {text-disabled}; background: transparent; }"
            "QToolButton:focus { border: 2px solid {focus-ring}; }", palette))
        for button, action, name in self._icon_entries:
            button.setMinimumHeight(height)
            button.setMaximumHeight(height)
            button.setIcon(self._design_icon(
                palette, name, COMPACT_ICON if self.compact else NORMAL_ICON,
                state="active" if action is not None and action.isChecked() else "normal"))
            button.setIconSize(QSize(COMPACT_ICON, COMPACT_ICON) if self.compact else
                               QSize(NORMAL_ICON, NORMAL_ICON))
        for button, name in ((self.help_button, "help"),
                             (self.compact_button, "expand" if self.compact else "collapse")):
            button.setIcon(self._design_icon(palette, name, COMPACT_ICON))
            button.setStyleSheet(qss(
                "QToolButton { background: transparent; color: {text}; border: 0; }"
                "QToolButton:hover { background: {hover-wash}; }", palette))

    def toggle_compact(self):
        self.set_compact(not self.compact)
        QSettings().setValue(COMPACT_KEY, self.compact)
