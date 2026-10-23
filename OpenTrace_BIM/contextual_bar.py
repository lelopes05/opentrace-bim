# SPDX-License-Identifier: GPL-3.0-or-later
"""A dynamic Info Box embedded in the floating viewport overlay.

Never registers a second modelling tool, modifies the host menu bar, or stores
a second copy of a BIM property. Quick edits proxy the controller's live Qt
fields, so existing validation, history, and Undo/Redo remain authoritative.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QObject, Qt, QSize, Slot
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel, QStackedWidget,
    QToolButton, QWidget, QWidgetAction, QFrame, QVBoxLayout, QStyle, QMenu,
)

from .icons import icon
from .i18n import t, englishize_widget, english
from .style import SIZES, qss, theme_font
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
        self._combo_controls = []
        self._shape_fields = []
        self._anchor_grids = []
        self._derived_controls = []
        self._button_icons = {}
        self._icon_cache = {}
        self._icon_assignments = {}
        self._collapsed = False
        self._key = None
        self._opening_kind = "opening"
        self._door_bar_second_row = None
        self._focus_return = _ReturnViewportFocus(self.app.viewport, self)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(12)
        self.stack = _CompactStack(self)
        row.addWidget(self.stack, 1)
        self.layer_combo = suite.object_properties.make_layer_combo(self)
        self.layer_combo.setToolTip(t("Layer"))
        row.addWidget(self.layer_combo)
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
        # The Qt stack gives each page the available width.  A stretch AFTER
        # the controls keeps every tool's groups against the left edge rather
        # than distributing surplus width between groups (notably on Slab).
        for _page, page_layout in self.pages.values():
            page_layout.addStretch(1)
        self.refresh()
        englishize_widget(self)

    def _page(self, key, title):
        w = QWidget(self.stack)
        w.setObjectName("opentrace_context_" + key)
        if key == "door":
            # Two predictable compact lines, rather than a single row wider
            # than the viewport. Both point to the SAME suite/tool values.
            outer = QVBoxLayout(w)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(2)
            layout = QHBoxLayout()
            second = QHBoxLayout()
            for line in (layout, second):
                line.setContentsMargins(0, 0, 0, 0)
                line.setSpacing(6)
                line.setAlignment(Qt.AlignLeft)
                outer.addLayout(line)
            self._door_bar_second_row = second
        else:
            layout = QHBoxLayout(w)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(9)
            layout.setAlignment(Qt.AlignLeft)
        label = QLabel(title)
        label.setObjectName("opentrace_context_name")
        layout.addWidget(label)
        self.stack.addWidget(w)
        self.pages[key] = (w, layout)
        return layout

    def _section(self, layout, title):
        # Every section has a real hierarchy: a small heading ABOVE methods
        # and dimensions, not inline fragments mixed with buttons.
        group = QFrame(self)
        group.setObjectName("opentrace_context_section")
        v = QVBoxLayout(group)
        v.setContentsMargins(4,0,3,0)
        v.setSpacing(2)
        label = QLabel(title,group)
        label.setObjectName("opentrace_context_group_label")
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
        button.setFixedHeight(SIZES["option-height"])
        button.setMinimumWidth(SIZES["option-height"])
        button.setIconSize(QSize(SIZES["icon-20"], SIZES["icon-20"]))
        names = {
            "／": "geo_segment", "▱": "geo_rect_diagonal",
            "⊥": "geo_rect_base_width", "⌒": "geo_arc_normal",
            "⊙": "geo_arc_center", "∴": "geo_arc_three",
            "▭": "opening_rect", "□": "opening_square",
            "◯": "opening_circle", "⬡": "opening_free", "⬠": "opening_free",
            "◧": "anchor_left", "⊕": "anchor_center",
            "◨": "anchor_right", "↶": "swing", "⊘": "delete",
            "✓": "door", "＋": "profile", "▤": "library",
        }
        self._button_icons[button] = names[symbol]
        if active is not None:
            button.setCheckable(True)
            self._mode_controls.append((button, active))
        button.clicked.connect(lambda checked=False, cb=callback: self._run(cb))
        self._target(layout).addWidget(button)
        return button

    def _run(self, callback):
        # Refresh synchronously. An unparented singleShot retained self after
        # the bar's Qt widgets were deleted, then touched dead QToolButtons in
        # _sync_size_controls when the queued callback eventually ran.
        callback()
        self.app.viewport.setFocus()
        self.refresh()

    def _field(self, layout, text, source, *, width=90, grouped=False, name=None, show_label=True):
        if source is None:
            return
        if grouped:
            container = QWidget(self)
            vertical = QVBoxLayout(container)
            vertical.setContentsMargins(0, 0, 0, 0)
            vertical.setSpacing(2)
            label = QLabel(t(text), container)
            label.setObjectName("opentrace_label_" + name)
            label.setProperty("designRole", "field-label")
            if show_label:
                vertical.addWidget(label)
            else:
                label.hide()
        else:
            label = self._section(layout, text)
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
        # Bind to this bar as the Qt receiver; Qt disconnects when the bar is
        # destroyed, unlike a connection to a non-QObject suite callback.
        source.valueChanged.connect(self._on_source_value_changed)
        mirror.setToolTip(source.toolTip() or t(text))
        mirror.setAccessibleName(t(text))
        if name is not None:
            mirror.setObjectName("opentrace_field_" + name)
        mirror.installEventFilter(self._focus_return)
        mirror.lineEdit().installEventFilter(self._focus_return)
        self._mirrors.append((mirror, source))
        if grouped:
            vertical.addWidget(mirror)
            self._target(layout).addWidget(container)
        else:
            self._target(layout).addWidget(mirror)
        return label, mirror

    @Slot(float)
    def _on_source_value_changed(self, _value):
        """Schedule controller sync only while this bar's QObject exists."""
        self.suite.schedule_sync_context()

    def _segment(self, layout, group_name, source_values, read_value, write_value):
        """An exclusive control mirroring a controller option, never a tool action."""
        buttons = QButtonGroup(self)
        buttons.setExclusive(True)
        for caption, value in source_values:
            button = QToolButton(self)
            button.setFocusPolicy(Qt.NoFocus)
            button.setObjectName(f"opentrace_opt_{group_name}_{value}")
            button.setText(t(caption))
            button.setAccessibleName(t(caption))
            button.setToolTip(t(caption))
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setFixedHeight(SIZES["option-height"])
            # Placement modes have the same icon-only language as wall and
            # slab construction.  Names remain in tooltips/accessibility.
            if group_name == "door_insertion":
                button.setToolButtonStyle(Qt.ToolButtonIconOnly)
                button.setFixedWidth(SIZES["option-height"])
            else:
                button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setIconSize(QSize(SIZES["icon-20"], SIZES["icon-20"]))
            icon_name = ("door" if value == "complete" else "opening_rect") if group_name == "door_insertion" else ("anchor_" + {"l": "left", "c": "center", "r": "right"}[value]
                         if group_name == "beam_reference" else
                         "anchor_" + value if group_name.endswith("_reference") else
                         "wall_composite" if group_name.startswith("wall") and value == "composite" else
                         "wall" if group_name.startswith("wall") else
                         "slab_composite" if value == "composite" else "slab")
            self._button_icons[button] = icon_name
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
        heading.setProperty("designRole", "field-label")
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
        chord = p.get("chord", p["length"] * abs(math.cos(math.radians(p["inclination"]))))
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

    def _sync_field(self, mirror, source):
        old = mirror.blockSignals(True)
        try:
            mirror.setEnabled(source.isEnabled())
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
            self._section(p, t("Construção"))
            slab_group = QButtonGroup(self)
            slab_group.setExclusive(True)
            for symbol, title, mode in (
                ("▱", "Retângulo por cantos opostos", "diagonal"),
                ("⊥", "Retângulo por três pontos: base e largura", "base_width"),
                ("⬠", "Polígono livre", "polygon"),
            ):
                button = self._method(
                    p, symbol, t(title), lambda m=mode: slab.choose_mode(m),
                    active=lambda m=mode: slab.tool.mode == m)
                button.setObjectName("opentrace_opt_slab_mode_" + mode)
                slab_group.addButton(button)
            self._slab_options(p, slab, "slab")
        p = self._page("slab_edit", t("Laje selecionada"))
        if slab is not None:
            self._slab_options(p, slab, "slab_edit")

        p = self._page("column", t("Pilar"))
        if column is not None:
            self._structure_options(p, column, "column")
            self._section(p, t("Seção / medidas"))
            self._stacked_dimensions(p, "column", (
                ("Largura", column.width, "rect"),
                ("Comprimento", column.depth, "rect"),
                ("Diâmetro", column.diameter, "circle"),
            ))
            self._section(p, t("Elevação"))
            self._field(p, "Altura", column.height, width=77, grouped=True, name="column_height")
            self._field(p, "Base", column.base_offset, width=77, grouped=True, name="column_base")
            self._section(p, t("Âncora · 9 pontos"))
            self._anchor_grid(p, column, "column")
            self._section(p, t("Transição de seções"))
            source=column.section_transition
            transition=QComboBox(self)
            transition.setObjectName("opentrace_context_column_section_transition")
            for i in range(source.count()):
                transition.addItem(source.itemText(i),source.itemData(i))
            transition.activated.connect(
                lambda i, box=transition, original=source:
                    self._select_combo(original,box.itemData(i)))
            self._target(p).addWidget(transition)
            self._combo_controls.append((transition,lambda ctrl=source:ctrl.currentData(),source))
            self._section(p, t("Cortes de base e topo"))
            for cut, label in (("base","Base"),("top","Topo")):
                source=getattr(column,cut+"_cut_mode")
                chooser=QComboBox(self)
                chooser.setObjectName("opentrace_context_column_cut_"+cut)
                for i in range(source.count()):
                    chooser.addItem(source.itemText(i),source.itemData(i))
                chooser.activated.connect(
                    lambda i, box=chooser, original=source:
                        self._select_combo(original,box.itemData(i)))
                self._target(p).addWidget(chooser)
                self._combo_controls.append((chooser,lambda ctrl=source:ctrl.currentData(),source))
                self._field(p,t("Ângulo "+label.lower()),getattr(column,cut+"_cut_angle"),grouped=True,
                            name="column_cut_angle_"+cut)

        p = self._page("beam", t("Viga"))
        if beam is not None:
            self._structure_options(p, beam, "beam")
            self._section(p, t("Seção / medidas"))
            self._stacked_dimensions(p, "beam", (
                ("Largura", beam.width, "rect"),
                ("Altura", beam.height, "rect"),
                ("Diâmetro", beam.diameter, "circle"),
            ))
            self._section(p, t("Âncora · 9 pontos"))
            self._anchor_grid(p, beam, "beam")
            self._section(p, t("Elevação"))
            self._calculated(
                p, "Topo", "beam_top", beam.offset, self._beam_top,
                self._set_beam_top, self._beam_top_locked,
                lambda: (t("Viga inclinada: edite na paleta")
                         if self._beam_top_locked() else t("Cota do topo no início da viga")))

        p = self._page("profiles", t("Perfil Complexo"))
        profile = self.controllers.get("profiles")
        if profile is not None:
            self._section(p, t("Biblioteca de Perfis"))
            new_btn = self._method(p, "＋", t("Criar novo perfil 2D"), profile.new_profile)
            new_btn.setObjectName("opentrace_context_profile_new")
            open_btn = self._method(p, "▤", t("Abrir biblioteca de perfis existentes"),
                                    profile.show_library)
            open_btn.setObjectName("opentrace_context_profile_open")
            self._section(p, t("Desenho 2D do IngeTrazo"))
            # Show the host's native CAD tools as DIRECT toolbar buttons, not
            # another menu. Reuse existing QActions/shortcuts, never register
            # a competing CAD drawing engine or action.
            menu_bar = self.app.window.menuBar()
            draw = next((a.menu() for a in menu_bar.actions()
                         if a.menu() is not None and
                         a.text().replace("&", "").strip().casefold()
                         in ("draw", "desenhar", "desenho")), None)
            native = []
            if draw is not None:
                import unicodedata
                def normalized(label):
                    label = unicodedata.normalize("NFKD", label.casefold())
                    return "".join(c for c in label if not unicodedata.combining(c))
                terms = (("line", "linha"), ("freehand", "mao livre"),
                         ("3-point arc", "arco 3 pontos"),
                         ("center arc", "arco centro"),
                         ("arc", "arco"), ("rectangle", "retangulo"),
                         ("circle", "circulo"))
                def collect(menu):
                    for action in menu.actions():
                        if action.menu() is not None:
                            collect(action.menu())
                        elif not action.isSeparator():
                            name = normalized(action.text().replace("&", ""))
                            if any(t in name for group in terms for t in group):
                                if action not in native: native.append(action)
                collect(draw)
            for i, action in enumerate(native):
                button = QToolButton(self)
                button.setObjectName("opentrace_profile_cad_native_" + str(i))
                button.setDefaultAction(action)
                button.setFocusPolicy(Qt.NoFocus)
                button.setToolTip(action.text().replace("&", "") +
                                  (("  " + action.shortcut().toString()) if not action.shortcut().isEmpty() else ""))
                button.setAccessibleName(action.text().replace("&", ""))
                button.setFixedHeight(SIZES["option-height"])
                if action.icon().isNull():
                    button.setToolButtonStyle(Qt.ToolButtonTextOnly)
                    button.setText(action.text().replace("&", "").split("  ")[0])
                else:
                    button.setToolButtonStyle(Qt.ToolButtonIconOnly)
                    button.setIconSize(QSize(SIZES["icon-20"], SIZES["icon-20"]))
                self._target(p).addWidget(button)
            if not native:
                missing = QLabel(t("Use Draw no menu do IngeTrazo"), self)
                self._target(p).addWidget(missing)

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

    def _structure_options(self, layout, ctrl, key):
        """The existing shapes as icon-only construction choices.

        The complex-profile library is still chosen by the original
        controller's combobox; none of the geometry engines are duplicated.
        """
        self._section(layout, t("Perfil"))
        shapes = QButtonGroup(self)
        shapes.setExclusive(True)
        for icon_name, title, shape in (
            ("opening_rect", "Quadrado / retangular", "rect"),
            ("opening_circle", "Circular", "circle"),
            ("profile", "Perfil complexo", "complex"),
        ):
            button = QToolButton(self)
            button.setObjectName("opentrace_opt_" + key + "_profile_" + shape)
            button.setFocusPolicy(Qt.NoFocus)
            button.setAutoRaise(True)
            button.setCheckable(True)
            button.setFixedSize(SIZES["option-height"], SIZES["option-height"])
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setIconSize(QSize(SIZES["icon-20"], SIZES["icon-20"]))
            button.setToolTip(t(title))
            button.setAccessibleName(t(title))
            button.clicked.connect(lambda _checked=False, x=ctrl, v=shape:
                                   self._run(lambda: self._choose_profile(x, v)))
            shapes.addButton(button)
            self._target(layout).addWidget(button)
            self._button_icons[button] = icon_name
            self._mode_controls.append((button, lambda x=ctrl, v=shape: (
                "complex" if x.defaults.get("section_type") == "complex"
                else x.defaults.get("profile", "rect")) == v))
        profiles = QComboBox(self)
        profiles.setObjectName("opentrace_opt_" + key + "_complex_profile")
        profiles.setMinimumWidth(115)
        profiles.setToolTip("Perfil da biblioteca existente do OpenTrace BIM.")
        profiles.activated.connect(lambda _i, c=profiles, x=ctrl:
                                   self._choose_complex_profile(x, c.currentData()))
        self._target(layout).addWidget(profiles)
        self._combo_controls.append((profiles, lambda x=ctrl:
                                     x.complex_profile.currentData(), ctrl.complex_profile))
        self._shape_fields.append((profiles, ctrl, "complex_picker"))

    def _choose_profile(self, ctrl, shape):
        if shape == "complex":
            ctrl.refresh_complex_profile_options(ctrl.defaults.get("profile_ref"), ctrl.defaults.get("profile_data"))
            if not any(ctrl.complex_profile.itemData(i) for i in range(ctrl.complex_profile.count())):
                ctrl.message("Nenhum perfil complexo disponível. Crie um no editor de Perfis.", True)
                self.refresh()
                return
            self._select_combo(ctrl.section_type, "complex")
        else:
            self._select_combo(ctrl.section_type, "simple")
            self._select_combo(ctrl.profile, shape)
        self.app.viewport.setFocus()
        self.refresh()

    def _choose_complex_profile(self, ctrl, ref):
        if ref is not None:
            self._select_combo(ctrl.complex_profile, ref)
            self.app.viewport.setFocus()
        self.refresh()

    def _stacked_dimensions(self, layout, key, rows):
        panel = QWidget(self)
        vertical = QVBoxLayout(panel)
        vertical.setContentsMargins(0, 0, 0, 0)
        vertical.setSpacing(2)
        for label, source, shape in rows:
            line = QWidget(panel)
            horizontal = QHBoxLayout(line)
            horizontal.setContentsMargins(0, 0, 0, 0)
            horizontal.setSpacing(4)
            caption = QLabel(t(label), line)
            caption.setMinimumWidth(78)  # Never reduce type size to fit.
            horizontal.addWidget(caption)
            self._field(horizontal, label, source, width=88, grouped=True, show_label=False,
                        name=key + "_" + ("depth" if label == "Comprimento" else label.lower()))
            vertical.addWidget(line)
            self._shape_fields.append((line, self.controllers[key], shape))
        self._target(layout).addWidget(panel)

    def _anchor_grid(self, layout, ctrl, key):
        """Compact 3x3 anchor; X/Y for columns, lateral/Z for beams."""
        grid_widget = QWidget(self)
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(2)
        grid.setVerticalSpacing(2)
        buttons = {}
        for r, row in enumerate((("tl", "tc", "tr"), ("ml", "mc", "mr"), ("bl", "bc", "br"))):
            for c, pos in enumerate(row):
                button = QToolButton(grid_widget)
                button.setObjectName("opentrace_opt_" + key + "_anchor_" + pos)
                button.setFocusPolicy(Qt.NoFocus)
                button.setCheckable(True)
                button.setAutoExclusive(True)
                button.setText("·")
                button.setFixedSize(17, 17)
                button.setToolTip("Ponto de referência " + pos + " (9 posições)")
                button.clicked.connect(lambda _checked=False, x=ctrl, k=pos: self._run(lambda: x.anchor_changed(k)))
                grid.addWidget(button, r, c)
                buttons[pos] = button
        self._anchor_grids.append((buttons, ctrl))
        self._target(layout).addWidget(grid_widget)

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
            (("Simples", "simple"), ("Material Composer", "composite")),
            wall.structure.currentData,
            lambda v: self._choose_wall_structure(v))
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

    def _choose_wall_structure(self, kind):
        # The sidebar may still display the previous creation default when a
        # wall has just been picked. Read that wall before choosing its mode.
        from .ui import selected_walls
        if len(selected_walls(self.app.scene)) == 1:
            self.wall._state_key = self.wall._loaded_key = None
            self.wall.refresh()
        self._select_combo(self.wall.structure, kind)
        if kind == "composite":
            # This is an action as well as a selected mode: clicking an already
            # checked Composite button must still open Material Composer.
            self.wall.open_material_composer()

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
        p = self._page("slab_opening", t("Abertura na laje"))
        self._section(p, t("Desenho de abertura"))
        p.addWidget(QLabel(t("Clique nos vértices no plano da laje; feche o contorno para recortar.")))
        p = self._page("opening", t("Abertura") + " · criação")
        self._section(p, t("Forma"))
        for symbol, title, shape in (
            ("▭", "Retangular", "rect"), ("□", "Quadrada", "square"),
            ("◯", "Circular", "circle"), ("⬡", "Livre", "free"),
        ):
            button = self._method(p, symbol, t(title),
                                  lambda s=shape: self._choose_shape(s),
                                  active=lambda s=shape: openings.opening_tool.shape == s)
            button.setObjectName("opentrace_opt_opening_shape_" + shape)
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
            button = self._method(p, symbol, t(title),
                                  lambda a=anchor: self._set_anchor(openings.opening_tool.place, a),
                                  active=lambda a=anchor: openings.opening_tool.place.anchor == a)
            button.setObjectName("opentrace_opt_opening_anchor_" + anchor)
            self._opening_anchor_buttons.append(button)
        for key, tool, title in (("door", openings.door_tool, "Porta"),
                                 ("window", openings.window_tool, "Janela")):
            p = self._page(key, t(title) + " · criação")
            if key == "door":
                self._section(p, t("Inserir"))
                self._segment(p, "door_insertion",
                              (("Porta", "complete"), ("Vão de porta", "void")),
                              lambda tl=tool: "void" if tl.door_as_opening else "complete",
                              lambda mode: self.suite._choose_door_mode(mode == "void"))
                from .door_style_catalog import DOOR_STYLES, DOOR_INSTALLATIONS
                from .door_leaf_presets import LEAF_PRESETS
                from .door_leaf_editor import _preset_icon
                self._section(p, 'Sistema de abertura')
                family_combo=QComboBox(self)
                family_combo.setObjectName('opentrace_context_door_family')
                for family,title in DOOR_INSTALLATIONS:family_combo.addItem(title,family)
                family_combo.activated.connect(
                    lambda _i,c=family_combo:self.suite._set_door_family(c.currentData()))
                family_combo.setMaximumWidth(135)
                self._target(p).addWidget(family_combo)
                self._combo_controls.append((family_combo,
                    lambda tl=tool:getattr(tl,'door_family_key','swing_single'),None))
                slide_combo=QComboBox(self)
                slide_combo.setObjectName('opentrace_context_door_slide_side')
                slide_combo.addItem('Desliza ←','left')
                slide_combo.addItem('Desliza →','right')
                slide_combo.activated.connect(
                    lambda _i,c=slide_combo:self.suite._set_door_slide_side(c.currentData()))
                slide_combo.setMaximumWidth(98)
                self._target(p).addWidget(slide_combo)
                self._combo_controls.append((slide_combo,
                    lambda tl=tool:getattr(tl,'door_slide_side','left'),None))
                # Same state as Porta tab; options never restart placement.
                hinge_combo=QComboBox(self)
                hinge_combo.setObjectName('opentrace_context_door_hinge')
                for label,data in (('Dobradiça esquerda','left'),
                                   ('Dobradiça direita','right')):
                    hinge_combo.addItem(label,data)
                hinge_combo.activated.connect(
                    lambda _i,c=hinge_combo:self.suite._set_door_hinge(c.currentData()))
                hinge_combo.setMaximumWidth(106)
                self._target(p).addWidget(hinge_combo)
                self._combo_controls.append((hinge_combo,
                    lambda tl=tool:getattr(tl,'door_hinge','left'),None))
                swing_combo=QComboBox(self)
                swing_combo.setObjectName('opentrace_context_door_swing')
                swing_combo.addItem('Giro positivo',1)
                swing_combo.addItem('Giro negativo',-1)
                swing_combo.activated.connect(
                    lambda _i,c=swing_combo:self.suite._set_door_swing(c.currentData()))
                swing_combo.setMaximumWidth(104)
                self._target(p).addWidget(swing_combo)
                self._combo_controls.append((swing_combo,
                    lambda tl=tool:getattr(tl,'door_swing',1),None))
                self._section(p, 'Conversão da porta selecionada')
                apply_button=self._method(p,'✓','Aplicar modelo/sistema à porta selecionada',
                    self.suite._apply_door_conversion)
                apply_button.setObjectName('opentrace_context_door_apply')
                apply_button.setText('Aplicar')
                apply_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                self._door_apply_button=apply_button
                # Second line: leaf model, dimensions and insertion anchors.
                p=self._door_bar_second_row
                self._section(p, 'Tipo de folha')
                variant=QComboBox(self)
                variant.setObjectName('opentrace_context_door_variant')
                for label,key2 in (('Compositor','grid'),('Lisa','plain'),
                                   ('Frisada','grooved'),('Almofadada','panelled')):
                    variant.addItem(label,key2)
                variant.setMaximumWidth(110)
                variant.activated.connect(
                    lambda _i,c=variant:self.suite._set_door_variant(c.currentData()))
                self._target(p).addWidget(variant)
                self._combo_controls.append((variant,
                    lambda:self.suite._door_selected_variant,None))
                self._section(p, 'Modelo de folha')
                style_combo=QComboBox(self)
                style_combo.setObjectName('opentrace_context_door_preset')
                patterns={x[0]:x for x in LEAF_PRESETS}
                for style,title in DOOR_STYLES:
                    style_combo.addItem(_preset_icon(patterns[style]),title,style)
                style_combo.setIconSize(QSize(20,24))
                style_combo.setMaximumWidth(155)
                style_combo.activated.connect(
                    lambda _i,c=style_combo:self.suite._choose_door_style(c.currentData()))
                self._target(p).addWidget(style_combo)
                self._combo_controls.append((style_combo,
                    lambda tl=tool:getattr(tl,'door_style_key','plain_solid'),None))
            self._size_fields(p, tool, lambda k=key: k)
            self._section(p, t("Âncora"))
            for symbol, anchor, label in (
                ("◧", "left", "Âncora esquerda"), ("⊕", "center", "Âncora central"),
                ("◨", "right", "Âncora direita"),
            ):
                button = self._method(p, symbol, t(label),
                                      lambda tl=tool, a=anchor: self._set_anchor(tl, a),
                                      active=lambda tl=tool, a=anchor: tl.anchor == a)
                button.setObjectName("opentrace_opt_" + key + "_anchor_" + anchor)

    def _choose_shape(self, shape):
        self.wall.openings.opening_tool.set_shape(shape)
        self._sync_size_controls()

    def _size_fields(self, layout, tool, kind_of):
        """Width, height and sill spin boxes on ``tool.sizes[kind_of()]``."""
        for key, label in (("width", "Largura"), ("height", "Altura"), ("sill", "Peitoril")):
            title = self._section(layout, t(label))
            spin = QDoubleSpinBox(self)
            spin.installEventFilter(self._focus_return)
            spin.lineEdit().installEventFilter(self._focus_return)
            spin.setDecimals(2)
            spin.setRange(0.0 if key == "sill" else MIN_DIM, 100.0)
            spin.setSingleStep(0.05)
            spin.setSuffix(" m")
            spin.setKeyboardTracking(False)
            spin.setAccessibleName(t(label))
            spin.setObjectName('opentrace_size_' + key)
            spin.valueChanged.connect(
                lambda value, tl=tool, k=key, f=kind_of: self._set_size(tl, f(), k, value))
            self._target(layout).addWidget(spin)
            self._size_controls.append((spin, title, tool, kind_of, key))

    def _set_size(self, tool, kind, key, value):
        sizes = tool.sizes[kind]
        sizes[key] = value
        if kind == "door":
            self.wall.openings.notify_door_settings()
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
        profile = self.controllers.get("profiles")
        if profile is not None and (
                profile.is_profile_workspace() or (
                    self.suite.stack.currentWidget() is self.suite.pages.get("profiles")
                    and getattr(self.suite, "_profile_tool_at_entry", object()) is active)):
            return "profiles"
        slab = self.controllers.get("slab")
        if slab is not None and active is slab.opening_tool:
            return "slab_opening"
        if active is wall.draw_tool:
            # Selected wall editing takes priority even if creation is still
            # active. Match WallController.refresh and its material handlers.
            from .ui import selected_walls
            if len(selected_walls(self.app.scene)) == 1:
                return "wall_edit"
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
                fill = wall._find_linked_fill(op)
                if fill is not None:
                    params = (_fill_record(fill) or {}).get("params") or {}
                    if params.get("kind") in ("door", "window"):
                        self._opening_kind = params["kind"]
                        return "opening_edit"
                if op.get("kind") == "polygon":
                    self._opening_kind = "polygon"
                    return "polygon_edit"
                self._opening_kind = "opening"
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

    def apply_theme(self):
        """Apply one tokenized stylesheet and refresh icon states."""
        palette = QApplication.palette()
        self.setStyleSheet(qss(
            "QLabel#opentrace_context_name { color: {text}; font-size: 12px; font-weight: 600; }"
            "QFrame#opentrace_context_section { border-left: 1px solid {divider}; padding-left: 5px; }"
            "QLabel#opentrace_context_group_label { color: {text-muted}; font-size: 12px; font-weight: 600; }"
            "QLabel[designRole='field-label'] { color: {text-muted}; font-size: 11px; font-weight: 500; }"
            "QToolButton { background: {panel-raised}; border: 0px; border-radius: 4px;"
            " padding: 3px; color: {text}; }"
            "QToolButton:hover:!checked { background: {hover-wash}; }"
            "QToolButton:checked { background: {panel}; border: 2px solid {orange}; }"
            "QToolButton:focus { border: 2px solid {focus-ring}; }"
            "QToolButton:disabled { background: transparent; color: {text-disabled}; }"
            "QDoubleSpinBox { background: {field}; border: 1px solid {border};"
            " border-radius: 4px; color: {text}; padding: 3px; min-height: 20px; font-size: 12px; }"
            "QDoubleSpinBox:hover { background: {panel-raised}; }"
            "QDoubleSpinBox:focus { border: 2px solid {focus-ring}; }"
            "QDoubleSpinBox:read-only { background: {panel-raised}; border: 0px; }"
            "QDoubleSpinBox:disabled { background: transparent;"
            " border: 1px solid {divider}; color: {text-disabled}; }", palette))
        for spin in self.findChildren(QDoubleSpinBox):
            spin.setFont(theme_font(QApplication.font(), "field-value"))
        # Render state variants before any click/paint callback. A refresh
        # only swaps cached QIcons; it never starts a QPainter in an input event.
        for name in set(self._button_icons.values()):
            for state in ("normal", "marked", "disabled"):
                key = (palette.cacheKey(), name, state)
                if key not in self._icon_cache:
                    self._icon_cache[key] = icon(
                        name, SIZES["icon-20"], state=state, palette=palette)
        self._update_icons(palette)

    def _update_icons(self, palette):
        palette_key = palette.cacheKey()
        for button, name in self._button_icons.items():
            state = ("disabled" if not button.isEnabled() else
                     "marked" if button.isCheckable() and button.isChecked()
                     else "normal")
            key = (palette_key, name, state)
            if self._icon_assignments.get(button) == key:
                continue
            if key not in self._icon_cache:
                self._icon_cache[key] = icon(
                    name, SIZES["icon-20"], state=state, palette=palette)
            button.setIcon(self._icon_cache[key])
            self._icon_assignments[button] = key

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self.stack.setVisible(not self._collapsed)
        self.collapsed_label.setVisible(self._collapsed)
        # Collapsing is a true layout shrink, not simply painting over the UI.
        self.updateGeometry()
        self.collapse_button.setText("▾" if self._collapsed else "▴")
        self.collapse_button.setToolTip(
            "Expand contextual bar" if self._collapsed
            else "Collapse contextual bar")
        self.updateGeometry()

    def refresh(self):
        self.suite.object_properties.refresh()
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
        if getattr(self, '_door_apply_button', None) is not None:
            self._door_apply_button.setEnabled(
                self.suite._selected_door_instance() is not None)
        for mirror, source in self._mirrors:
            # A binding may be on an inactive stacked page; its source can be
            # hidden because the native suite switched pages, not because the
            # model became read-only. Respect source.enabled but not visibility.
            self._sync_field(mirror, source)
        slab = self.controllers.get("slab")
        if slab is not None:
            hint = t("Relativa ao nível") if slab.level.currentData() else t("Cota absoluta")
            for mirror, source in self._mirrors:
                if source is slab.offset:
                    mirror.setToolTip(hint)
        column = self.controllers.get("column")
        if column is not None:
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
        for combo, getter, source in self._combo_controls:
            blocked = combo.blockSignals(True)
            if source is not None:
                options = [(source.itemText(i), source.itemData(i),
                            source.model().item(i).isEnabled() if hasattr(source.model(), "item")
                            and source.model().item(i) is not None else True)
                           for i in range(source.count())]
                if [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())] != [(name, ref) for name, ref, _ in options]:
                    combo.clear()
                    for text, ref, enabled in options:
                        combo.addItem(text, ref)
                        if not enabled:
                            item = combo.model().item(combo.count()-1)
                            if item is not None: item.setEnabled(False)
                combo.setEnabled(source.isEnabled())
            index = combo.findData(getter())
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(blocked)
        for widget, ctrl, shape in self._shape_fields:
            current = "complex" if ctrl.defaults.get("section_type") == "complex" else ctrl.defaults.get("profile", "rect")
            widget.setVisible(current == shape if shape != "complex_picker" else current == "complex")
        for buttons, ctrl in self._anchor_grids:
            for pos, button in buttons.items():
                blocked = button.blockSignals(True)
                button.setChecked(ctrl.defaults.get("anchor", "mc") == pos)
                button.blockSignals(blocked)
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
        self._update_icons(QApplication.palette())
        self.setToolTip("OpenTrace BIM contextual bar: " + key)
        # Options are methods of the active construction tool. Selection and
        # native editing keep their properties in the sidebar / radial palette.
        creating = key != "idle" or bool(self.app.scene.selection)
        frame = self.overlay_dock.options_frame
        if frame.isHidden() == creating:
            frame.setVisible(creating)
            self.updateGeometry()
