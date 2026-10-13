# SPDX-License-Identifier: GPL-3.0-or-later
"""A dynamic Info Box embedded in the floating viewport overlay.

Never registers a second modelling tool, modifies the host menu bar, or stores
a second copy of a BIM property. Quick edits proxy the controller's live Qt
fields, so existing validation, history, and Undo/Redo remain authoritative.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QSize, QTimer
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QStackedWidget,
    QToolButton, QWidget, QWidgetAction, QFrame, QVBoxLayout, QStyle,
)

from .icons import set_symbol_icon
from .i18n import t
from .model import MIN_DIM


class _CompactStack(QStackedWidget):
    """Only the selected tool's controls determine toolbar geometry."""
    def sizeHint(self):
        page = self.currentWidget()
        return page.sizeHint() if page is not None else super().sizeHint()

    def minimumSizeHint(self):
        page = self.currentWidget()
        return page.minimumSizeHint() if page is not None else super().minimumSizeHint()


class _ReturnViewportFocus(QObject):
    """Give keyboard shortcuts back to the viewport after a field edit."""

    def __init__(self, viewport, parent):
        super().__init__(parent)
        self.viewport = viewport

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.KeyRelease and
                event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape)):
            self.viewport.setFocus()
        return False


class ContextualBar(QWidget):
    """Compact, collapsible view onto the SAME actions and fields as the dock."""

    def __init__(self, suite, overlay_dock):
        super().__init__(overlay_dock.options_frame)
        self.setObjectName("opentrace_contextual_bar")
        self.suite = suite
        self.overlay_dock = overlay_dock
        self.app = suite.app
        self.controllers = suite.controllers
        self.wall = self.controllers["wall"]
        self._mirrors = []
        self._mode_controls = []
        self._segment_controls = []
        self._derived_controls = []
        self._collapsed = False
        self._key = None
        self._opening_kind = "opening"
        self._focus_return = _ReturnViewportFocus(self.app.viewport, self)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(12)
        self.stack = _CompactStack(self)
        row.addWidget(self.stack, 1)
        self.collapsed_label = QLabel("Contexto · abrir ▾")
        self.collapsed_label.hide()
        row.addWidget(self.collapsed_label, 1)
        self.collapse_button = QToolButton(self)
        self.collapse_button.setFocusPolicy(Qt.NoFocus)
        self.collapse_button.setObjectName("opentrace_context_collapse")
        self.collapse_button.setToolTip("Recolher ou expandir a barra contextual")
        self.collapse_button.setText("▴")
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        row.addWidget(self.collapse_button)

        self.pages = {}
        self._build_pages()
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
        button.setFocusPolicy(Qt.NoFocus)
        button.setAutoRaise(True)
        button.setToolTip(title)
        button.setAccessibleName(title)
        button.setFixedSize(34, 32)
        button.setIconSize(QSize(22, 22))
        from .icons import icon as pa_icon
        names={
            "／":"wall","▱":"rect",
            "⊥":"wall_base","⌒":"wall_curve","⊙":"center_arc",
            "∴":"three_points","⬡":"polygon","◧":"anchor_left",
            "⊕":"anchor_center","◨":"anchor_right",
            "↶":"swing","⊘":"delete","ⓘ":"bim"}
        chosen=names.get(symbol)
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
        self.app.viewport.setFocus()
        QTimer.singleShot(0, self.refresh)

    def _field(self, layout, text, source, *, width=90, grouped=False, name=None):
        if source is None:
            return
        if grouped:
            container = QWidget(self)
            vertical = QVBoxLayout(container)
            vertical.setContentsMargins(0, 0, 0, 0)
            vertical.setSpacing(2)
            label = QLabel(t(text), container)
            label.setObjectName("opentrace_label_" + name)
            vertical.addWidget(label)
        else:
            label = self._section(layout, text)
        if isinstance(source, QComboBox):
            mirror = QComboBox(self)
            mirror.activated.connect(lambda _index: self.app.viewport.setFocus())
            mirror.setMinimumWidth(width)
            mirror.setMaximumWidth(max(width, 145))
            mirror.currentIndexChanged.connect(
                lambda _=0, a=mirror, b=source: self._apply_combo(a, b))
            source.currentIndexChanged.connect(self.suite.schedule_sync_context)
        else:
            mirror = QDoubleSpinBox(self)
            mirror.editingFinished.connect(self.app.viewport.setFocus)
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
        mirror.setToolTip(source.toolTip() or t(text))
        mirror.setAccessibleName(t(text))
        if name is not None:
            mirror.setObjectName("opentrace_field_" + name)
        mirror.installEventFilter(self._focus_return)
        if isinstance(mirror, QDoubleSpinBox):
            mirror.lineEdit().installEventFilter(self._focus_return)
        elif mirror.isEditable():
            mirror.lineEdit().installEventFilter(self._focus_return)
        self._mirrors.append((mirror, source))
        if grouped:
            vertical.addWidget(mirror)
            self._target(layout).addWidget(container)
        else:
            self._target(layout).addWidget(mirror)
        return label, mirror

    def _segment(self, layout, group_name, source_values, read_value, write_value):
        """An exclusive control mirroring a controller option, never a tool action."""
        buttons = QButtonGroup(self)
        buttons.setExclusive(True)
        for caption, value in source_values:
            button = QToolButton(self)
            button.setObjectName(f"opentrace_opt_{group_name}_{value}")
            button.setText(t(caption))
            button.setAccessibleName(t(caption))
            button.setToolTip(t(caption))
            button.setCheckable(True)
            button.setAutoRaise(True)
            buttons.addButton(button)
            button.clicked.connect(
                lambda _checked=False, v=value, cb=write_value: self._choose_option(cb, v))
            self._target(layout).addWidget(button)
            self._segment_controls.append((button, read_value, value))

    def _choose_option(self, setter, value):
        setter(value)
        self.app.viewport.setFocus()
        self.refresh()

    @staticmethod
    def _select_combo(source, value):
        index = source.findData(value)
        if index >= 0:
            source.setCurrentIndex(index)

    def _calculated(self, layout, label, name, source, getter, setter,
                    read_only, tooltip):
        """A derived view: no stored property, edits write to the source controller."""
        container = QWidget(self)
        vertical = QVBoxLayout(container)
        vertical.setContentsMargins(0, 0, 0, 0)
        vertical.setSpacing(2)
        heading = QLabel(t(label), container)
        heading.setObjectName("opentrace_label_" + name)
        vertical.addWidget(heading)
        spin = QDoubleSpinBox(self)
        spin.setObjectName("opentrace_field_" + name)
        spin.setAccessibleName(t(label))
        spin.setLocale(source.locale())
        spin.setDecimals(source.decimals())
        spin.setRange(-10000.0, 10000.0)
        spin.setSingleStep(source.singleStep())
        spin.setSuffix(" m")
        spin.setKeyboardTracking(False)
        spin.setMinimumWidth(90)
        spin.editingFinished.connect(self.app.viewport.setFocus)
        spin.valueChanged.connect(setter)
        spin.installEventFilter(self._focus_return)
        spin.lineEdit().installEventFilter(self._focus_return)
        vertical.addWidget(spin)
        self._target(layout).addWidget(container)
        self._derived_controls.append((spin, getter, read_only, tooltip))
        return spin

    def _beam_anchor_horizontal(self, horizontal):
        beam = self.controllers["beam"]
        current = beam.defaults["anchor"]
        beam.anchor_changed(current[0] + horizontal)

    def _beam_top(self):
        """Section's highest world Z at the first centerline station."""
        from .beam_model import (_centerline_local, _complex_profile_loops_yz,
                                 _profile_yz, _ring_frames)
        beam = self.controllers["beam"]
        p = beam.resolved_defaults()
        chord = p.get("chord", p["length"] * abs(__import__("math").cos(
            __import__("math").radians(p["inclination"]))))
        centers, _length, _plan = _centerline_local(chord, p)
        center, lateral, vertical = _ring_frames(centers)[0]
        if p["section_type"] == "complex":
            sections = (point for loop in _complex_profile_loops_yz(p)
                        for point in loop["points"])
        else:
            sections = iter(_profile_yz(p))
        return p["base_z"] + max(
            (center + lateral * y + vertical * z).z() for y, z in sections)

    def _set_beam_top(self, desired):
        beam = self.controllers["beam"]
        if not self._beam_top_locked():
            beam.offset.setValue(beam.offset.value() + desired - self._beam_top())

    def _beam_top_locked(self):
        beam = self.controllers["beam"]
        p = beam.resolved_defaults()
        return (abs(p["inclination"]) > 1e-8 or abs(p["curvature"]) > 1e-8
                or abs(p["vertical_curvature"]) > 1e-8
                or not beam.offset.isEnabled() or beam.offset.isReadOnly())

    def _set_wall_top(self, desired):
        base = self.wall.fields["base"]
        height = self.wall.fields["height"]
        if height.isEnabled() and not height.isReadOnly():
            height.setValue(desired - base.value())

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

        self._page("idle", t("Pronto para modelar"))
        p = self._page("wall", t("Parede"))
        self._section(p, t("Geometria"))
        geometry_group = QButtonGroup(self)
        geometry_group.setExclusive(True)
        for symbol, title, geometry in (
            ("／", "Reta: início e fim", "single"),
            ("▱", "Retângulo por diagonal", "rect_diagonal"),
            ("⊥", "Retângulo por base e largura", "rect_base_width"),
            ("⌒", "Arco normal", "arc_normal"),
            ("⊙", "Arco pelo centro", "arc_center"),
            ("∴", "Arco por 3 pontos", "arc_three"),
        ):
            button = self._method(
                p, symbol, t(title), lambda g=geometry: wall.choose_geometry(g),
                active=lambda g=geometry: wall.draw_tool.geometry == g)
            button.setObjectName("opentrace_opt_wall_geometry_" + geometry)
            geometry_group.addButton(button)
        self._wall_options(p, "wall")
        p = self._page("wall_edit", t("Parede selecionada"))
        self._wall_options(p, "wall_edit")

        p = self._page("slab", t("Laje"))
        if slab is not None:
            self._slab_options(p, slab, "slab")
        p = self._page("slab_edit", t("Laje selecionada"))
        if slab is not None:
            self._slab_options(p, slab, "slab_edit")

        p = self._page("column", t("Pilar"))
        if column is not None:
            self._section(p, t("Medidas"))
            for label, field in (
                ("Largura", column.width), ("Profundidade", column.depth),
                ("Altura", column.height), ("Base", column.base_offset),
            ):
                self._field(p, label, field, grouped=True,
                            name="column_" + label.lower())

        p = self._page("beam", t("Viga"))
        if beam is not None:
            self._section(p, t("Referência"))
            self._segment(
                p, "beam_reference",
                (("Esquerdo", "l"), ("Centro", "c"), ("Direito", "r")),
                lambda: beam.defaults["anchor"][-1],
                self._beam_anchor_horizontal)
            self._section(p, t("Medidas"))
            self._field(p, "Largura", beam.width, grouped=True, name="beam_width")
            self._field(p, "Altura", beam.height, grouped=True, name="beam_height")
            self._calculated(
                p, "Topo", "beam_top", beam.offset, self._beam_top,
                self._set_beam_top, self._beam_top_locked,
                lambda: (t("Viga inclinada: edite na paleta")
                         if self._beam_top_locked() else t("Cota do topo no início da viga")))

        self._build_opening_pages()
        p = self._page("opening_edit", t("Vão selecionado"))
        for key, label in (
            ("width", "Largura"), ("height", "Altura"),
            ("sill", "Peitoril"), ("position", "Posição"),
        ):
            self._field(p, label, wall.opening_fields[key])
        self._anchor_label = self._section(p, t("Âncora"))
        self._anchor_buttons = []
        for symbol, name, title in (
            ("◧", "left", "Âncora esquerda"),
            ("⊕", "center", "Âncora central"),
            ("◨", "right", "Âncora direita"),
        ):
            self._anchor_buttons.append(
                self._method(p, symbol, t(title),
                             lambda value=name: self._edit_fill_anchor(value)))
        self._swing_button = self._method(
            p, "↶", t("Inverter giro da porta"), wall.reverse_swing_btn.click)
        self._method(p, "⊘", t("Excluir abertura selecionada"), wall.delete_wall_opening)
        p = self._page("polygon_edit", t("Abertura poligonal"))
        self._section(p, t("Edição da geometria"))
        p.addWidget(QLabel(t("Vértices e arestas: paleta lateral / radial")))
        self._method(p, "⬡", t("Abrir editor da abertura na paleta lateral"),
                     lambda: self.suite.show_page("wall"))
        self._method(p, "⊘", t("Excluir abertura selecionada"), wall.delete_wall_opening)

    def _wall_options(self, layout, page_name):
        wall = self.wall
        self._section(layout, t("Referência"))
        self._segment(
            layout, page_name + "_reference",
            (("Esquerdo", "left"), ("Centro", "center"), ("Direito", "right")),
            wall.alignment.currentData,
            lambda v: self._select_combo(wall.alignment, v))
        self._section(layout, t("Tipo"))
        self._segment(
            layout, page_name + "_type",
            (("Simples", "simple"), ("Composta", "composite")),
            wall.structure.currentData,
            lambda v: self._select_combo(wall.structure, v))
        self._section(layout, t("Medidas"))
        for label, field in (
            ("Espessura", wall.fields["thickness"]), ("Altura", wall.fields["height"]),
            ("Base", wall.fields["base"]),
        ):
            self._field(layout, label, field, grouped=True,
                        name=page_name + "_" + label.lower())
        self._calculated(
            layout, "Topo", page_name + "_top", wall.fields["height"],
            lambda: wall.fields["base"].value() + wall.fields["height"].value(),
            self._set_wall_top,
            lambda: (wall.fields["height"].isReadOnly()
                     or not wall.fields["height"].isEnabled()),
            lambda: t("Calculado: Base + Altura"))

    def _slab_options(self, layout, slab, page_name):
        self._section(layout, t("Tipo"))
        self._segment(
            layout, page_name + "_type",
            (("Simples", "simple"), ("Composta", "composite")),
            slab.structure.currentData,
            lambda v: self._select_combo(slab.structure, v))
        self._section(layout, t("Medidas"))
        self._field(layout, "Espessura", slab.thickness, grouped=True,
                    name=page_name + "_thickness")
        self._field(layout, "Base", slab.offset, grouped=True,
                    name=page_name + "_base")

    def _edit_fill_anchor(self, anchor):
        # Use the EXISTING hosted-fill combobox, hence its EditHostedFill
        # handler, source_id and one undoable history command.
        field = self.wall.fill_anchor_combo
        index = field.findData(anchor)
        if index >= 0:
            field.setCurrentIndex(index)

    def _build_opening_pages(self):
        """Options of the Opening, Door and Window tools; the values are ``tool.sizes``."""
        openings = self.wall.openings
        self._size_controls = []
        p = self._page("opening", t("Abertura") + " · criação")
        self._section(p, t("Forma"))
        for symbol, title, shape in (
            ("▭", "Retangular", "rect"), ("□", "Quadrada", "square"),
            ("◯", "Circular", "circle"), ("⬡", "Livre", "free"),
        ):
            self._method(p, symbol, t(title),
                         lambda s=shape: self._choose_shape(s),
                         active=lambda s=shape: openings.opening_tool.shape == s)
        self._size_fields(p, openings.opening_tool.place,
                          lambda: None if openings.opening_tool.shape == "free"
                          else openings.opening_tool.shape)
        # Reuse the placement tool's existing anchor; free polygons have none.
        self._section(p, t("Âncora"))
        self._opening_anchor_buttons = []
        for symbol, anchor, title in (
            ("◧", "left", "Âncora esquerda"),
            ("⊕", "center", "Âncora central"),
            ("◨", "right", "Âncora direita"),
        ):
            self._opening_anchor_buttons.append(
                self._method(p, symbol, t(title),
                             lambda a=anchor: self._set_anchor(openings.opening_tool.place, a),
                             active=lambda a=anchor: openings.opening_tool.place.anchor == a))
        for key, tool, title in (("door", openings.door_tool, "Porta"),
                                 ("window", openings.window_tool, "Janela")):
            p = self._page(key, t(title) + " · criação")
            self._size_fields(p, tool, lambda k=key: k)
            self._section(p, t("Âncora"))
            for symbol, anchor, label in (
                ("◧", "left", "Âncora esquerda"), ("⊕", "center", "Âncora central"),
                ("◨", "right", "Âncora direita"),
            ):
                self._method(p, symbol, t(label),
                             lambda tl=tool, a=anchor: self._set_anchor(tl, a),
                             active=lambda tl=tool, a=anchor: tl.anchor == a)

    def _choose_shape(self, shape):
        self.wall.openings.opening_tool.set_shape(shape)
        self._sync_size_controls()

    def _size_fields(self, layout, tool, kind_of):
        """Width, height and sill spin boxes on ``tool.sizes[kind_of()]``."""
        for key, label in (("width", "Largura"), ("height", "Altura"), ("sill", "Peitoril")):
            title = self._section(layout, t(label))
            spin = QDoubleSpinBox(self)
            spin.editingFinished.connect(self.app.viewport.setFocus)
            spin.installEventFilter(self._focus_return)
            spin.lineEdit().installEventFilter(self._focus_return)
            spin.setDecimals(2)
            spin.setRange(0.0 if key == "sill" else MIN_DIM, 100.0)
            spin.setSingleStep(0.05)
            spin.setSuffix(" m")
            spin.setKeyboardTracking(False)
            spin.setAccessibleName(t(label))
            spin.valueChanged.connect(
                lambda value, tl=tool, k=key, f=kind_of: self._set_size(tl, f(), k, value))
            self._target(layout).addWidget(spin)
            self._size_controls.append((spin, title, tool, kind_of, key))

    def _set_size(self, tool, kind, key, value):
        sizes = tool.sizes[kind]
        sizes[key] = value
        if kind in ("square", "circle") and key == "width":
            sizes["height"] = value
        self.app.viewport.update()

    def _set_anchor(self, tool, anchor):
        tool.anchor = anchor
        self.app.viewport.update()

    def _sync_size_controls(self):
        for button in self._opening_anchor_buttons:
            button.setEnabled(self.wall.openings.opening_tool.shape != "free")
        for spin, title, tool, kind_of, key in self._size_controls:
            kind = kind_of()
            spin.setEnabled(kind is not None
                            and not (key == "height" and kind in ("square", "circle")))
            if kind is None:
                continue
            old = spin.blockSignals(True)
            spin.setValue(tool.sizes[kind][key])
            spin.blockSignals(old)
            if key == "width":
                title.setText(t("Diâmetro") if kind == "circle" else t("Largura"))

    def _context_key(self):
        vp = self.app.viewport
        active = getattr(vp, "active_tool", None)
        wall = self.wall
        if active is wall.draw_tool:
            return "wall"
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
        self.updateGeometry()
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
        self._sync_size_controls()
        if key == "column":
            column = self.controllers["column"]
            first = column.segment.findData(0)
            if first >= 0 and column.segment.currentIndex() != first:
                column.segment.setCurrentIndex(first)
        for mirror, source in self._mirrors:
            # A binding may be on an inactive stacked page; its source can be
            # hidden because the native suite switched pages, not because the
            # model became read-only. Respect source.enabled but not visibility.
            self._sync_field(mirror, source)
        if key in ("slab", "slab_edit"):
            slab = self.controllers["slab"]
            hint = t("Relativa ao nível") if slab.level.currentData() else t("Cota absoluta")
            for mirror, source in self._mirrors:
                if source is slab.offset:
                    mirror.setToolTip(hint)
        if key == "column":
            column = self.controllers["column"]
            stations = column.defaults.get("stations") or ()
            tapered = bool(stations and (
                float(stations[-1]["width"]) != float(stations[0]["width"])
                or float(stations[-1]["depth"]) != float(stations[0]["depth"])))
            for mirror, source in self._mirrors:
                if source in (column.width, column.depth):
                    mirror.setToolTip(t("Pilar afunilado: o fim se edita na paleta")
                                      if tapered else t("Medida no início do pilar"))
        for spin, getter, locked, hint in self._derived_controls:
            old = spin.blockSignals(True)
            try:
                spin.setValue(getter())
                spin.setReadOnly(bool(locked()))
                spin.setToolTip(hint())
            finally:
                spin.blockSignals(old)
        for button, getter, value in self._segment_controls:
            blocked = button.blockSignals(True)
            button.setChecked(getter() == value)
            button.blockSignals(blocked)
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
        # Options are methods of the active construction tool. Selection and
        # native editing keep their properties in the sidebar / radial palette.
        creating = key in {"wall", "slab", "column", "beam",
                           "opening", "door", "window"}
        frame = self.overlay_dock.options_frame
        if frame.isHidden() == creating:
            frame.setVisible(creating)
        self.updateGeometry()
