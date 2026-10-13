# SPDX-License-Identifier: GPL-3.0-or-later
"""A single dynamic Info Box in its OWN toolbar row below the host tools.

Never registers a second modelling tool, modifies the host menu bar, or stores
a second copy of a BIM property. Quick edits proxy the controller's live Qt
fields, so existing validation, history, and Undo/Redo remain authoritative.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QStackedWidget,
    QToolButton, QWidget, QWidgetAction, QFrame, QVBoxLayout, QStyle,
)

from .icons import set_symbol_icon


class _CompactStack(QStackedWidget):
    """Only the selected tool's controls determine toolbar geometry."""
    def sizeHint(self):
        page = self.currentWidget()
        return page.sizeHint() if page is not None else super().sizeHint()

    def minimumSizeHint(self):
        page = self.currentWidget()
        return page.minimumSizeHint() if page is not None else super().minimumSizeHint()


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
        self._opening_kind = "opening"

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(12)
        self.brand = QLabel("OpenTrace BIM")
        self.brand.setObjectName("opentrace_context_brand")
        self.brand.setMinimumWidth(116)
        self.brand.setStyleSheet("font-size:11pt; font-weight:700; padding-right:8px;")
        row.addWidget(self.brand)
        self.stack = _CompactStack(self)
        row.addWidget(self.stack, 1)
        self.collapsed_label = QLabel("Contexto · abrir ▾")
        self.collapsed_label.hide()
        row.addWidget(self.collapsed_label, 1)
        self.collapse_button = QToolButton(self)
        self.collapse_button.setObjectName("opentrace_context_collapse")
        self.collapse_button.setToolTip("Recolher ou expandir a barra contextual")
        self.collapse_button.setText("▴")
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        row.addWidget(self.collapse_button)
        self.help_button=QToolButton(self)
        self.help_button.setObjectName("opentrace_context_help")
        self.help_button.setText("?")
        self.help_button.setToolTip("Ajuda desta ferramenta")
        self.help_button.setAccessibleName("Ajuda contextual")
        self.help_button.setFixedSize(28,28)
        self.help_button.clicked.connect(
            lambda: self.suite.open_help(self._context_key()))
        row.addWidget(self.help_button)

        self.pages = {}
        self._build_pages()
        # Important: this MUST be a separate Qt toolbar ROW. The old design
        # simply added a widget to the native row, compressing it out of view.
        # Qt keeps native menus / native toolbars and their actions unchanged.
        toolbar = self.wall.toolbar
        window = self.app.window
        # QMainWindow manages full-width rows and persistence for toolbars.
        # Insert one break BEFORE our toolbar; do not create Ribbon bars.
        if not window.toolBarBreak(toolbar):
            window.insertToolBarBreak(toolbar)
        toolbar.addWidget(self)
        toolbar.setWindowTitle("OpenTrace BIM · Barra contextual")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(24,24))
        self.refresh()

    def _page(self, key, title):
        w = QWidget(self.stack)
        w.setObjectName("opentrace_context_" + key)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        label = QLabel(title)
        label.setObjectName("opentrace_context_name")
        label.setStyleSheet("font-weight:600; padding-right:5px;")
        layout.addWidget(label)
        self.stack.addWidget(w)
        self.pages[key] = (w, layout)
        return layout

    def _section(self, layout, title):
        # Every section has a real hierarchy: a small heading ABOVE methods
        # and dimensions, not inline fragments mixed with buttons.
        group = QFrame(self)
        group.setObjectName("opentrace_context_section")
        group.setStyleSheet(
            "QFrame#opentrace_context_section {"
            " border-left:1px solid palette(mid); padding-left:5px; }")
        v = QVBoxLayout(group)
        v.setContentsMargins(4,0,3,0)
        v.setSpacing(2)
        label = QLabel(title,group)
        label.setStyleSheet("font-size:9pt; color:palette(mid);")
        v.addWidget(label)
        controls=QHBoxLayout()
        controls.setContentsMargins(0,0,0,0)
        controls.setSpacing(3)
        v.addLayout(controls)
        layout.addWidget(group)
        if not hasattr(self,"_group_rows"): self._group_rows={}
        self._group_rows[id(layout)]=controls
        return label

    def _target(self,layout):
        return getattr(self,"_group_rows",{}).get(id(layout),layout)

    def _method(self, layout, symbol, title, callback, *, active=None):
        button = QToolButton(self)
        button.setAutoRaise(True)
        button.setToolTip(title)
        button.setAccessibleName(title)
        button.setFixedSize(34, 32)
        button.setIconSize(QSize(22, 22))
        from .icons import icon as pa_icon
        names={
            "／":"wall","▏":"wall","▱":"rect","□":"opening",
            "⊥":"wall_base","⌒":"wall_curve","⊙":"center_arc",
            "∴":"three_points","⬡":"polygon","◧":"anchor_left",
            "⊕":"anchor_center","◨":"anchor_right",
            "↶":"swing","⊘":"delete","ⓘ":"bim"}
        chosen=("slab" if title=="Criar laje" else names.get(symbol))
        if chosen:
            button.setIcon(pa_icon(chosen,32))
            button.setText("")
        else:
            set_symbol_icon(button,symbol,22)
        button.setStyleSheet(
            "QToolButton {border:1px solid transparent; border-radius:4px;}"
            "QToolButton:hover {background:palette(midlight);}"
            "QToolButton:checked {background:palette(highlight);"
            "border:1px solid palette(highlight);}")
        if active is not None:
            button.setCheckable(True)
            self._mode_controls.append((button, active))
        button.clicked.connect(lambda checked=False, cb=callback: self._run(cb))
        self._target(layout).addWidget(button)
        return button

    def _run(self, callback):
        callback()
        QTimer.singleShot(0, self.refresh)

    def _field(self, layout, text, source, *, width=90):
        if source is None:
            return
        label = self._section(layout, text)
        if isinstance(source, QComboBox):
            mirror = QComboBox(self)
            mirror.setMinimumWidth(width)
            mirror.setMaximumWidth(max(width, 145))
            mirror.currentIndexChanged.connect(
                lambda _=0, a=mirror, b=source: self._apply_combo(a, b))
            source.currentIndexChanged.connect(self.suite.schedule_sync_context)
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
            # A direct QObject-to-QObject Qt connection avoids referencing
            # destroyed mirrors from Python signal closures during teardown.
            mirror.valueChanged.connect(source.setValue)
            source.valueChanged.connect(self.suite.schedule_sync_context)
        mirror.setToolTip(source.toolTip() or text)
        mirror.setAccessibleName(text)
        self._mirrors.append((mirror, source))
        self._target(layout).addWidget(mirror)
        return label, mirror

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

        p = self._page("idle", "Pronto para modelar")
        self._section(p, "Ferramentas")
        self._method(p, "▏", "Criar parede", wall.action.trigger)
        if slab is not None:
            self._method(p, "▱", "Criar laje", slab.action.trigger)
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
        self._field(p, "Nível base", wall.base_level, width=135)
        self._field(p, "Nível topo", wall.top_level, width=135)
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
        self._field(p, "Nível base", wall.base_level, width=135)
        self._field(p, "Nível topo", wall.top_level, width=135)
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
            self._page(kind, title + " · criação")
        # One set of live opening fields: variants use visibility, not
        # duplicate signal-connected spinboxes for the same source widgets.
        p = self._page("opening_edit", "Vão selecionado")
        for key, label in (
            ("width", "Larg."), ("height", "Alt."),
            ("sill", "Peitoril"), ("position", "Pos."),
        ):
            self._field(p, label, wall.opening_fields[key])
        self._anchor_label = self._section(p, "Âncora")
        self._anchor_buttons = []
        for symbol, name, title in (
            ("◧", "left", "Âncora esquerda"),
            ("⊕", "center", "Âncora central"),
            ("◨", "right", "Âncora direita"),
        ):
            self._anchor_buttons.append(
                self._method(p, symbol, title,
                             lambda value=name: self._edit_fill_anchor(value)))
        self._swing_button = self._method(
            p, "↶", "Inverter giro da porta", wall.reverse_swing_btn.click)
        self._method(p, "⊘", "Excluir abertura selecionada", wall.delete_wall_opening)
        p = self._page("polygon_edit", "Abertura poligonal")
        self._section(p, "Edição da geometria")
        p.addWidget(QLabel("Vértices e arestas: paleta lateral / radial"))
        self._method(p, "⬡", "Abrir editor da abertura na paleta lateral",
                     lambda: self.suite.show_page("wall"))
        self._method(p, "⊘", "Excluir abertura selecionada", wall.delete_wall_opening)

    def _edit_fill_anchor(self, anchor):
        # Use the EXISTING hosted-fill combobox, hence its EditHostedFill
        # handler, source_id and one undoable history command.
        field = self.wall.fill_anchor_combo
        index = field.findData(anchor)
        if index >= 0:
            field.setCurrentIndex(index)

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
        for key, tool in (("opening", wall.openings.opening_tool),
                          ("door", wall.openings.door_tool),
                          ("window", wall.openings.window_tool)):
            if active is tool:
                return key
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
             or selected_hosted_opening(scene) is not None
             or (wall.target is not None
                 and wall._active_opening_wall is wall.target
                 and wall._fields_opening_id == wall._active_opening_id))
                and wall.target is not None and wall._active_opening_id):
            from .model import read_wall
            from .door_window_commands import _fill_record
            try:
                op = next(x for x in read_wall(wall.target)["openings"]
                          if x.get("id") == wall._active_opening_id)
                if op.get("kind") == "polygon":
                    self._opening_kind = "polygon"
                    return "polygon_edit"
                self._opening_kind = "opening"
                fill = wall._find_linked_fill(op)
                if fill is not None:
                    params = (_fill_record(fill) or {}).get("params") or {}
                    if params.get("kind") in ("door", "window"):
                        self._opening_kind = params["kind"]
            except (ValueError, KeyError, StopIteration, TypeError):
                pass
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
        # Collapsing is a true layout shrink, not simply painting over the UI.
        self.wall.toolbar.updateGeometry()
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
        # Do not display inapplicable buttons: only hosted doors can swing,
        # and only hosted elements have an anchor.
        show_anchor = self._opening_kind in ("door", "window")
        self._anchor_label.setVisible(show_anchor)
        for widget in self._anchor_buttons:
            widget.setVisible(show_anchor)
        self._swing_button.setVisible(self._opening_kind == "door")
        for button, predicate in self._mode_controls:
            checked = bool(predicate())
            old = button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(old)
        self.setToolTip("Barra contextual do OpenTrace BIM: " + key)
