# SPDX-License-Identifier: GPL-3.0-or-later
"""One context-sensitive OpenTrace Info Box in the existing architecture toolbar.

Never registers a second modelling tool, modifies the host menu bar, or stores
a second copy of a BIM property. Quick edits proxy the controller's live Qt
fields, so existing validation, history, and Undo/Redo remain authoritative.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QStackedWidget,
    QToolButton, QWidget, QWidgetAction,
)

from .icons import set_symbol_icon


class _CompactStack(QStackedWidget):
    """Only the selected tool's controls determine toolbar geometry."""
    def sizeHint(self):
        page = self.currentWidget()
        return page.sizeHint() if page is not None else super().sizeHint()


class ContextualBar(QWidget):
    """Compact, collapsible view onto the SAME actions and fields as the dock."""

    def __init__(self, suite):
        super().__init__(suite.app.window)
        self.setObjectName("opentrace_contextual_bar")
        self.suite = suite
        self.app = suite.app
        self.controllers = suite.controllers
        self.wall = self.controllers["wall"]
        self._mirrors = []
        self._mode_controls = []
        self._collapsed = False
        self._key = None

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 6, 2)
        row.setSpacing(7)
        self.brand = QLabel("OpenTrace BIM")
        self.brand.setObjectName("opentrace_context_brand")
        self.brand.setStyleSheet("font-weight:600;")
        row.addWidget(self.brand)
        self.stack = _CompactStack(self)
        row.addWidget(self.stack, 1)
        self.collapsed_label = QLabel("Contexto recolhido")
        self.collapsed_label.hide()
        row.addWidget(self.collapsed_label, 1)
        self.collapse_button = QToolButton(self)
        self.collapse_button.setObjectName("opentrace_context_collapse")
        self.collapse_button.setToolTip("Recolher ou expandir a barra contextual")
        self.collapse_button.setText("▴")
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        row.addWidget(self.collapse_button)

        self.pages = {}
        self._build_pages()
        # Existing fixed toolbar is REUSED (including its host toggle action).
        # Hide its old fixed wall/slab/door/window controls; keep QAction
        # objects and menus alive, so native shortcuts are not disturbed.
        toolbar = self.wall.toolbar
        self.hidden_legacy_actions = tuple(toolbar.actions())
        for action in self.hidden_legacy_actions:
            if isinstance(action, QWidgetAction):
                action.setVisible(False)
            else:
                # QAction also belongs to menus; removing it ONLY from the
                # toolbar avoids hiding the same menu/keyboard command.
                toolbar.removeAction(action)
        toolbar.addWidget(self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.refresh()

    def _page(self, key, title):
        w = QWidget(self.stack)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = QLabel(title)
        label.setStyleSheet("font-weight:600;")
        layout.addWidget(label)
        self.stack.addWidget(w)
        self.pages[key] = (w, layout)
        return layout

    def _section(self, layout, title):
        label = QLabel(title)
        label.setStyleSheet("font-size:9pt; color:palette(mid);")
        layout.addWidget(label)

    def _method(self, layout, symbol, title, callback, *, active=None):
        button = QToolButton(self)
        button.setAutoRaise(True)
        button.setToolTip(title)
        button.setAccessibleName(title)
        button.setFixedSize(30, 30)
        button.setIconSize(QSize(20, 20))
        set_symbol_icon(button, symbol, 20)
        if active is not None:
            button.setCheckable(True)
            self._mode_controls.append((button, active))
        button.clicked.connect(lambda checked=False, cb=callback: self._run(cb))
        layout.addWidget(button)
        return button

    def _run(self, callback):
        callback()
        QTimer.singleShot(0, self.refresh)

    def _field(self, layout, text, source, *, width=90):
        if source is None:
            return
        self._section(layout, text)
        if isinstance(source, QComboBox):
            mirror = QComboBox(self)
            mirror.setMinimumWidth(width)
            mirror.setMaximumWidth(max(width, 145))
            mirror.currentIndexChanged.connect(
                lambda _=0, a=mirror, b=source: self._apply_combo(a, b))
        else:
            mirror = QDoubleSpinBox(self)
            mirror.setLocale(source.locale())
            mirror.setDecimals(source.decimals())
            mirror.setRange(source.minimum(), source.maximum())
            mirror.setSingleStep(source.singleStep())
            mirror.setSuffix(source.suffix())
            mirror.setKeyboardTracking(False)
            mirror.setMinimumWidth(width)
            mirror.setMaximumWidth(width + 12)
            mirror.valueChanged.connect(
                lambda _=0, a=mirror, b=source: self._apply_value(a, b))
            source.valueChanged.connect(
                lambda _=0, a=mirror, b=source: self._sync_field(a, b))
        mirror.setToolTip(source.toolTip() or text)
        mirror.setAccessibleName(text)
        self._mirrors.append((mirror, source))
        layout.addWidget(mirror)

    @staticmethod
    def _apply_value(mirror, source):
        if source.isEnabled():
            source.setValue(mirror.value())

    @staticmethod
    def _apply_combo(mirror, source):
        if source.isEnabled():
            index = source.findData(mirror.currentData())
            if index >= 0 and index != source.currentIndex():
                source.setCurrentIndex(index)

    def _sync_field(self, mirror, source):
        old = mirror.blockSignals(True)
        try:
            mirror.setEnabled(source.isEnabled())
            if isinstance(mirror, QComboBox):
                current = source.currentData()
                options = [(source.itemText(i), source.itemData(i))
                           for i in range(source.count())]
                previous = [(mirror.itemText(i), mirror.itemData(i))
                            for i in range(mirror.count())]
                if options != previous:
                    mirror.clear()
                    for title, data in options:
                        mirror.addItem(title, data)
                index = mirror.findData(current)
                mirror.setCurrentIndex(index if index >= 0 else -1)
            else:
                mirror.setRange(source.minimum(), source.maximum())
                mirror.setValue(source.value())
                mirror.setReadOnly(source.isReadOnly())
        finally:
            mirror.blockSignals(old)

    def _build_pages(self):
        wall = self.wall
        slab = self.controllers.get("slab")
        column = self.controllers.get("column")
        beam = self.controllers.get("beam")

        p = self._page("idle", "Selecione uma ferramenta ou objeto BIM")
        self._method(p, "▏", "Criar parede", wall.action.trigger)
        if slab is not None:
            self._method(p, "▱", "Criar laje", slab.action.trigger)
        self._method(p, "□", "Criar abertura", lambda: wall.begin_hosted_fill("opening"))
        p = self._page("wall", "Parede")
        self._section(p, "Mét. construtivos")
        for symbol, title, mode in (
            ("／", "Reta: início e fim", "single"),
            ("▱", "Retângulo por diagonal", "rect_diagonal"),
            ("⊥", "Retângulo por base e largura", "rect_base_width"),
        ):
            self._method(p, symbol, title,
                         lambda m=mode: self._wall_mode(m),
                         active=lambda m=mode: self.app.viewport.active_tool is wall.tool
                         and wall.tool.mode == m)
        self._method(p, "⌒", "Parede curva: arco", wall.curve_action.trigger)
        self._field(p, "Alinham.", wall.alignment)
        self._field(p, "Estrutura", wall.structure)
        self._field(p, "Esp.", wall.fields["thickness"])
        self._field(p, "Alt.", wall.fields["height"])
        p = self._page("wall_curve", "Parede curva")
        self._section(p, "Mét. construtivos")
        for symbol, title, mode in (
            ("⌒", "Arco normal", "normal"),
            ("⊙", "Arco pelo centro", "center"),
            ("∴", "Arco por 3 pontos", "three"),
        ):
            self._method(p, symbol, title,
                         lambda m=mode: self._curve_mode(m),
                         active=lambda m=mode: self.app.viewport.active_tool is wall.curve_create_tool
                         and wall.curve_create_tool.mode == m)
        self._method(p, "／", "Voltar à parede reta", wall.action.trigger)
        self._field(p, "Esp.", wall.fields["thickness"])
        self._field(p, "Alt.", wall.fields["height"])
        p = self._page("wall_edit", "Parede selecionada")
        self._field(p, "Esp.", wall.fields["thickness"])
        self._field(p, "Alt.", wall.fields["height"])
        self._field(p, "Alinham.", wall.alignment)
        self._method(p, "ⓘ", "Informações do Projeto",
                     lambda: self.suite.show_page("project"))
        p = self._page("slab", "Laje")
        if slab is not None:
            self._section(p, "Mét. construtivos")
            for symbol, title, mode in (
                ("▱", "Retângulo por diagonal", "diagonal"),
                ("⊥", "Retângulo por base e largura", "base_width"),
                ("⬡", "Polígono livre", "polygon"),
            ):
                self._method(p, symbol, title, lambda m=mode: slab.choose_mode(m),
                             active=lambda m=mode: slab.tool.mode == m)
            self._field(p, "Estrutura", slab.structure)
            self._field(p, "Esp.", slab.thickness)
            self._field(p, "Nível", slab.level)
            self._field(p, "Cota", slab.offset)
        p = self._page("slab_edit", "Laje selecionada")
        if slab is not None:
            self._field(p, "Esp.", slab.thickness)
            self._field(p, "Cota", slab.offset)
        for key, ctrl in (("column", column), ("beam", beam)):
            p = self._page(key, "Pilar" if key == "column" else "Viga")
            if ctrl is not None:
                self._section(p, "Seção")
                for name, label in (
                    ("section_type", "Tipo"), ("profile", "Forma"),
                    ("width", "Larg."), ("height", "Alt."),
                ):
                    self._field(p, label, getattr(ctrl, name, None))
        for kind, title in (("opening", "Abertura"), ("door", "Porta"), ("window", "Janela")):
            p = self._page(kind, title + " · criação")
            if kind == "opening":
                self._section(p, "Mét. construtivos")
                self._method(p, "▱", "Vão retangular", lambda: wall.begin_hosted_fill("opening"))
                self._method(p, "⬡", "Vão poligonal", wall.begin_wall_polygon_from_toolbar)
            else:
                self._section(p, "Ancoragem")
                for symbol, anchor, label in (
                    ("◧", "left", "Esquerda"), ("⊕", "center", "Centro"),
                    ("◨", "right", "Direita"),
                ):
                    self._method(p, symbol, label,
                                 lambda k=kind, a=anchor: wall.begin_hosted_fill(k, a))
            p.addWidget(QLabel("Clique na parede para posicionar"))
        p = self._page("opening_edit", "Vão selecionado")
        for key, label in (
            ("width", "Larg."), ("height", "Alt."),
            ("sill", "Peitoril"), ("position", "Pos."),
        ):
            self._field(p, label, wall.opening_fields[key])
        self._method(p, "↶", "Inverter giro da porta", wall.reverse_swing_btn.click)
        self._method(p, "⊘", "Excluir abertura selecionada", wall.delete_wall_opening)

    def _wall_mode(self, mode):
        if self.app.viewport.active_tool is not self.wall.tool:
            self.wall.action.trigger()
        self.wall.choose_straight_mode(mode)

    def _curve_mode(self, mode):
        if self.app.viewport.active_tool is not self.wall.curve_create_tool:
            self.wall.curve_action.trigger()
        self.wall.choose_curve_mode(mode)

    def _context_key(self):
        vp = self.app.viewport
        active = getattr(vp, "active_tool", None)
        wall = self.wall
        if active is wall.tool:
            return "wall"
        if active is wall.curve_create_tool:
            return "wall_curve"
        if active is wall.opening_tool:
            return wall.opening_tool.kind
        if active is wall.polygon_tool:
            return "opening"
        for key in ("slab", "column", "beam"):
            ctrl = self.controllers.get(key)
            if ctrl is not None and active is getattr(ctrl, "tool", None):
                return key
        scene = self.app.scene
        if getattr(scene, "edit_group", None) is not None:
            return "idle"
        # The selected void may be a virtual pick OR an independently
        # selected door/window group. Do not assume the first wall opening.
        from .ui import selected_hosted_opening, selected_walls
        if ((getattr(vp, "extension_pick", None) is not None
             or selected_hosted_opening(scene) is not None)
                and wall.target is not None and wall._active_opening_id):
            return "opening_edit"
        if len(selected_walls(scene)) == 1:
            return "wall_edit"
        for key in ("slab", "column", "beam"):
            ctrl = self.controllers.get(key)
            if ctrl is not None and getattr(ctrl, "target", None) is not None:
                return "slab_edit" if key == "slab" else key
        return "idle"

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self.stack.setVisible(not self._collapsed)
        self.collapsed_label.setVisible(self._collapsed)
        self.collapse_button.setText("▾" if self._collapsed else "▴")
        self.collapse_button.setToolTip(
            "Expandir a barra contextual" if self._collapsed
            else "Recolher a barra contextual")
        self.updateGeometry()

    def refresh(self):
        key = self._context_key()
        if key != self._key:
            self._key = key
            self.stack.setCurrentWidget(self.pages[key][0])
            self.updateGeometry()
        for mirror, source in self._mirrors:
            # A binding may be on an inactive stacked page; its source can be
            # hidden because the native suite switched pages, not because the
            # model became read-only. Respect source.enabled but not visibility.
            self._sync_field(mirror, source)
        for button, predicate in self._mode_controls:
            checked = bool(predicate())
            old = button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(old)
        self.setToolTip("Barra contextual do OpenTrace BIM: " + key)
