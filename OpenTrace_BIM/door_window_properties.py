# SPDX-License-Identifier: GPL-3.0-or-later
"""Instance-only hosted fill controls; never activates modelling tools.

Every user action is delegated to WallController's EditHostedFill command.
No values are copied between instances or written directly into scene records.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QLabel, QPushButton, QToolButton,
    QVBoxLayout, QWidget, QHBoxLayout, QInputDialog, QMessageBox,
)

from .door_window_core import f01_unit_size, normalize_fill, wallhole_size
from .door_leaf_editor import DoorLeafGridDialog
from .i18n import t, ui_locale, englishize_widget, english
from .materials import material_catalog
from .materials_ui import MaterialPickerCombo
from .widgets import FlexibleDoubleSpinBox
from .length_field import LengthField, format_length


class FillPropertiesPanel(QWidget):
    """Collapsible controls for the implemented F01 and simple window motor."""

    _MATERIALS = (
        ("material_leaf_front", "Face externa da folha"),
        ("material_leaf_back", "Face interna da folha"),
        ("material_leaf_edge", "Borda da folha"),
        ("material_leaf_stile", "Montantes laterais"),
        ("material_leaf_rail", "Travessas superior/inferior"),
        ("material_leaf_mullion", "Montantes internos"),
        ("material_leaf_transom", "Travessas internas"),
        ("material_leaf_glass", "Vidro da folha"),
        ("material_leaf_solid", "Painéis opacos"),
        ("material_leaf_louver", "Réguas da veneziana"),
        ("material_frame", "Marco / batente"),
        ("material_trim_front", "Alizar face A"),
        ("material_trim_back", "Alizar face B"),
        ("material_hardware", "Ferragens"),
        ("material_window_frame", "Marco da janela"),
        ("material_window_glass", "Vidro da janela"),
    )

    def __init__(self, parent, submit):
        super().__init__(parent)
        self.submit = submit
        self._loading = False
        self._spec = None
        self._fields = {}
        self._rows = {}
        self._groups = {}
        self._catalog = {}
        self._material_names = ()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 4)
        root.setSpacing(4)
        self._forms = {}
        for key, title in (
            ("geometry", "Sistema, folha e sentido de abertura"),
            ("dimensions", "Dimensões da esquadria"),
            ("installation", "Instalação e batente"),
            ("leaf", "Composição paramétrica da folha"),
            ("materials", "Materiais por componente"),
        ):
            frame = QFrame(self)
            outer = QVBoxLayout(frame)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(3)
            toggle = QToolButton(frame)
            toggle.setCheckable(key != 'materials')
            toggle.setChecked(key in ("geometry", "dimensions", "materials"))
            if key == 'materials':
                toggle.setText('MATERIALS — BY COMPONENT')
                toggle.setStyleSheet('font-weight:700; text-align:left;')
            if key != 'materials': toggle.setText(t(title))
            toggle.setArrowType(Qt.NoArrow if key=='materials' else
                                Qt.DownArrow if toggle.isChecked() else Qt.RightArrow)
            content = QWidget(frame)
            form = QFormLayout(content)
            form.setContentsMargins(8, 2, 0, 2)
            form.setSpacing(5)
            def expand(checked, body=content, button=toggle, section_key=key):
                body.setVisible(checked)
                button.setArrowType(Qt.NoArrow if section_key=='materials' else
                                    Qt.DownArrow if checked else Qt.RightArrow)
            if key != 'materials': toggle.toggled.connect(expand)
            outer.addWidget(toggle)
            outer.addWidget(content)
            expand(True if key == 'materials' else toggle.isChecked())
            root.addWidget(frame)
            self._forms[key] = form
            self._groups[key] = (frame, toggle)
        favorites = QHBoxLayout()
        self._save_fill_favourite_btn = QPushButton('Save door/window to library…', self)
        self._save_fill_favourite_btn.clicked.connect(self._save_fill_favourite)
        self._apply_fill_favourite_btn = QPushButton('Use library favourite…', self)
        self._apply_fill_favourite_btn.clicked.connect(self._apply_fill_favourite)
        favorites.addWidget(self._save_fill_favourite_btn)
        favorites.addWidget(self._apply_fill_favourite_btn)
        root.addLayout(favorites)
        root.addStretch(0)

        for key, title, low, step in (
            ("width", "Largura física da folha", 0.05, 0.01),
            ("height", "Altura física da folha", 0.05, 0.01),
            ("unit_width", "Largura externa do conjunto", 0.05, 0.01),
            ("unit_height", "Altura externa do conjunto", 0.05, 0.01),
        ):
            self._number("dimensions", key, title, low, step)
        self._bool("dimensions", "unit_width_manual", "Largura externa manual")
        self._bool("dimensions", "unit_height_manual", "Altura externa manual")
        for key, title in (("rough_width", "Largura de corte"),
                           ("rough_height", "Altura de corte")):
            label = QLabel(self)
            label.setObjectName("opentrace_fill_" + key)
            self._forms["dimensions"].addRow(t(title), label)
            self._fields[key] = label
        for key, title, low, step in (
            ("frame_thickness", "Largura aparente do marco", 0.001, 0.005),
            ("leaf_thickness", "Espessura da folha", 0.005, 0.005),
            ("clearance_left", "Folga de instalação esquerda", 0, 0.005),
            ("clearance_right", "Folga de instalação direita", 0, 0.005),
            ("clearance_top", "Folga de instalação superior", 0, 0.005),
            ("clearance_bottom", "Folga de instalação inferior", 0, 0.005),
            ("operating_gap_left", "Folga móvel esquerda", 0, 0.001),
            ("operating_gap_right", "Folga móvel direita", 0, 0.001),
            ("operating_gap_top", "Folga móvel superior", 0, 0.001),
            ("frame_depth", "Profundidade do batente", 0.002, 0.01),
            ("frame_recess", "Recuo da face escolhida", 0, 0.01),
        ):
            self._number("installation", key, title, low, step)
        self._choice("installation", "frame_depth_mode",
                     "Profundidade do batente",
                     (("Automática", "auto"), ("Manual", "manual")))
        self._choice("installation", "host_face", "Face de referência",
                     (("Face A", "left"), ("Face B", "right")))

        self._choice("geometry", "family_key", "Sistema de abertura",
                     (("Abrir · uma folha", "swing_single"),
                      ("Correr · aparente", "sliding_surface"),
                      ("Correr · embutida (alojamento experimental)", "sliding_pocket")))
        self._choice("geometry", "slide_side", "Correr para",
                     (("Esquerda", "left"), ("Direita", "right")))
        self._number("geometry", "slide_open_fraction", "Abertura da folha (%)",
                     0, 5, maximum=100, decimals=0, suffix=" %")
        self._number("geometry", "slide_overlap", "Sobreposição da folha", 0, .005)
        for key,label,minimum,maximum,step,decimals in (
            ('groove_count','Grooves (number)',1,12,1,0),
            ('groove_width','Groove width',.001,.03,.001,4),
            ('groove_end_margin','Top/bottom groove margin',.01,1.,.005,4),
            ('groove_offset','Horizontal groove offset',-.30,.30,.005,4),
        ):
            self._number('leaf',key,label,minimum,step,maximum=maximum,
                         decimals=decimals,suffix='' if key=='groove_count' else ' m')
        self._choice("geometry", "leaf_variant", "Tipo de folha",
                     (("Lisa", "plain"), ("Frisada", "grooved"),
                      ("Almofadada", "panelled"),
                      ("Montantes e painéis", "grid")))
        self._leaf_summary = QLabel(self)
        self._leaf_summary.setWordWrap(True)
        self._forms["leaf"].addRow(self._leaf_summary)
        self._leaf_button = QPushButton(t("Editar montantes, travessas e painéis…"), self)
        self._leaf_button.setObjectName("opentrace_fill_edit_leaf")
        self._leaf_button.clicked.connect(self._edit_leaf)
        self._forms["leaf"].addRow(self._leaf_button)
        self._bool("leaf", "window_grid_enabled", "Usar composição visual na janela")
        self._choice("geometry", "hinge", "Lado da dobradiça",
                     (("Esquerda", "left"), ("Direita", "right")))
        self._choice("geometry", "swing", "Sentido de giro",
                     (("Positivo", 1), ("Negativo", -1)))
        for key, label in (("plan_angle", "Ângulo em planta"),
                           ("model_angle", "Ângulo da folha no 3D")):
            self._number("geometry", key, label, 0, 5, maximum=180, suffix="°")
        self._number("geometry", "panes", "Quantidade de folhas da janela",
                     1, 1, maximum=16, decimals=0, suffix="")
        self._number("installation", "glass_thickness", "Espessura do vidro",
                     0.001, 0.001)
        self._bool("geometry", "trim_front_enabled", "Alizar face A")
        self._bool("geometry", "trim_back_enabled", "Alizar face B")
        self._number("geometry", "trim_width", "Largura do alizar", 0.005, 0.005)
        self._number("geometry", "trim_thickness", "Espessura do alizar",
                     0.001, 0.001)

        for key, title in self._MATERIALS:
            self._choice("materials", key, title, ())
        self._choice("materials", "material_name", "Material da janela", ())
        englishize_widget(self)
        self.setVisible(False)

    def _add(self, section, key, label, widget):
        widget.setObjectName("opentrace_fill_" + key)
        self._fields[key] = widget
        form = self._forms[section]
        form.addRow(t(label), widget)
        self._rows[key] = form.labelForField(widget)

    def _number(self, section, key, label, minimum, step, *,
                maximum=100.0, decimals=4, suffix=" m"):
        # Metre fields are lengths: shown in the document's units.
        field = (LengthField(self) if suffix.strip() == "m"
                 else FlexibleDoubleSpinBox(self))
        field.setLocale(ui_locale())
        field.setDecimals(decimals)
        field.setRange(minimum, maximum)
        field.setSingleStep(step)
        field.setSuffix(suffix)
        field.setKeyboardTracking(False)
        field.valueChanged.connect(
            lambda value, name=key: self._changed(name, value))
        self._add(section, key, label, field)

    def _choice(self, section, key, label, options):
        field = MaterialPickerCombo(self) if section == 'materials' else QComboBox(self)
        for title, value in options:
            field.addItem(t(title), value)
        field.currentIndexChanged.connect(
            lambda _index, name=key, widget=field:
            self._changed(name, widget.currentData()))
        self._add(section, key, label, field)

    def _bool(self, section, key, label):
        field = QCheckBox(self)
        field.toggled.connect(
            lambda value, name=key: self._changed(name, value))
        self._add(section, key, label, field)

    def _changed(self, name, value):
        if self._loading or self._spec is None:
            return
        if name in ("rough_width", "rough_height"):
            return
        if name in ("unit_width_manual", "unit_height_manual"):
            target = name.replace("_manual", "")
            self.submit({target: self._fields[target].value() if value else None})
            return
        if name.startswith("material_") and name != "material_name":
            recipe = self._catalog.get(value)
            if value is None:
                self.submit({name: None})
            elif recipe is not None:
                material = {"mat": value}
                material.update({
                    key: item for key, item in recipe.items()
                    if key in ("color", "texture", "opacity") and item is not None
                })
                self.submit({name: material})
            return
        if name == "slide_open_fraction":
            value = value / 100.0
        self.submit({name: value})

    def _edit_leaf(self):
        if self._spec is None:
            return
        spec = self._spec
        if spec["kind"] == "door" and spec.get("f01_layout") != "physical":
            return
        try:
            editor = DoorLeafGridDialog(spec, self, catalog=self._catalog)
        except ValueError as exc:
            QMessageBox.warning(self, t("Composição da esquadria"), t(str(exc)))
            return
        if editor.exec():
            # One command through the established history mechanism; no
            # per-cell writes, no UID, wall or opening changes.
            if spec["kind"] == "door":
                if spec.get('leaf_variant')=='grooved':
                    self.submit(editor.result_grooves())
                else:
                    self.submit({"leaf_variant": "grid",
                                 "leaf_grid": editor.result_grid()})
            else:
                self.submit({"window_grid_enabled": True,
                             "window_grid": editor.result_grid()})

    def _save_fill_favourite(self):
        if self._spec is None:return
        name,ok=QInputDialog.getText(self,'Save esquadria','Nome do favorito:')
        if not ok or not name.strip():return
        from .resource_favourites import save_favourite
        try:
            save_favourite(self._spec['kind'], self._spec, name=name.strip())
        except (TypeError,ValueError) as exc:
            QMessageBox.warning(self,'Favorito',str(exc))

    def _apply_fill_favourite(self):
        if self._spec is None:return
        from .resource_favourites import favourites
        items=favourites(self._spec['kind'])
        if not items:
            QMessageBox.information(self,'Favoritos','Nenhum favorito salvo para este tipo de esquadria.')
            return
        names=[str(item.get('name') or 'Esquadria') for item in items]
        name,ok=QInputDialog.getItem(self,'Usar favorito da biblioteca',
                                    'Choose a configuration:',names,0,False)
        if not ok:return
        item=items[names.index(name)]
        config=item.get('config') or {}
        # One existing EditHostedFill command, with Undo/Redo; never copy
        # original host IDs, wall openings or position from the source.
        allowed=set(self._fields)|{'leaf_grid','leaf_variant','f01_layout',
                                   'trim_front_enabled','trim_back_enabled'}
        changes={key:val for key,val in config.items()
                 if key in allowed and key not in ('rough_width','rough_height',
                                                     'unit_width_manual','unit_height_manual')}
        if changes:self.submit(changes)

    def _show(self, key, visible):
        # Repeated setVisible calls during a host scene refresh invalidate
        # QScrollArea geometry and cause the sidebar to jump on each spin edit.
        field = self._fields[key]
        if field.isHidden() == bool(visible):
            field.setVisible(visible)
        label = self._rows.get(key)
        if label is not None and label.isHidden() == bool(visible):
            label.setVisible(visible)

    def _group_visible(self, key, visible):
        frame = self._groups[key][0]
        if frame.isHidden() == bool(visible):
            frame.setVisible(visible)

    @staticmethod
    def _set_label(widget, text):
        """Unchanged text must not trigger QFormLayout relayout on every edit."""
        text=english(text)
        if widget.text() != text:
            widget.setText(text)

    def load(self, raw, scene):
        self._loading = True
        try:
            self._spec = normalize_fill(raw) if raw is not None else None
            spec = self._spec
            if self.isHidden() == (spec is not None):
                self.setVisible(spec is not None)
            if spec is None:
                return
            door = spec["kind"] == "door"
            physical = door and spec.get("f01_layout") == "physical"
            unit_width, unit_height = (
                f01_unit_size(spec) if door else (spec["width"], spec["height"]))
            rough_width, rough_height = (
                wallhole_size(spec) if door else (spec["width"], spec["height"]))
            from .door_grooves import DEFAULT_GROOVES
            values = dict(DEFAULT_GROOVES, **dict(spec, glass_thickness=spec.get("glass_thickness", 0.006),
                          slide_open_fraction=spec.get("slide_open_fraction", 0)*100,
                          unit_width=unit_width, unit_height=unit_height,
                          rough_width=rough_width, rough_height=rough_height,
                          unit_width_manual="unit_width" in spec,
                          unit_height_manual="unit_height" in spec))
            for key, field in self._fields.items():
                if key in ("rough_width", "rough_height"):
                    self._set_label(field, format_length(values[key]))
                elif isinstance(field, QCheckBox):
                    field.setChecked(bool(values.get(key, False)))
                elif isinstance(field, QComboBox) and key.startswith("material_"):
                    continue
                elif isinstance(field, QComboBox):
                    target = values.get(key)
                    index = field.findData(target)
                    field.setCurrentIndex(index if index >= 0 else 0)
                else:
                    value = float(values.get(key, 0))
                    if abs(field.value() - value) > 1e-8:
                        field.setValue(value)
            for key in ("unit_width", "unit_height"):
                self._fields[key].setEnabled(key in spec)
                self._fields[key].setToolTip(english(
                    'Ative o ajuste manual acima para editar a medida externa.'
                    if key not in spec else 'Valor externo manual do conjunto.'))
            self._fields["frame_depth"].setEnabled(
                physical and spec["frame_depth_mode"] == "manual")
            materials = material_catalog(scene)
            self._catalog = materials
            names = tuple(materials)
            if names != self._material_names:
                self._material_names = names
                for key, _title in self._MATERIALS:
                    field = self._fields[key]
                    field.clear()
                    field.addItem(t("Padrão"), None)
                    for name in names:
                        field.addItem(name, name)
                field = self._fields["material_name"]
                field.clear()
                field.addItem(t("Padrão"), None)
                for name in names:
                    field.addItem(name, name)
            for key, _title in self._MATERIALS:
                field = self._fields[key]
                saved = spec.get(key)
                current = saved.get("mat") if isinstance(saved, dict) else None
                field.setCurrentIndex(max(0, field.findData(current)))
            field = self._fields["material_name"]
            field.setCurrentIndex(max(0, field.findData(spec.get("material_name"))))
            self._set_label(self._rows["width"],
                t("Largura física da folha") if door else t("Largura da janela"))
            self._set_label(self._rows["height"],
                t("Altura física da folha") if door else t("Altura da janela"))
            for key in ("width", "height", "frame_thickness",
                        "rough_width", "rough_height"):
                self._show(key, True)
            for key in ("unit_width", "unit_height", "unit_width_manual",
                        "unit_height_manual", "leaf_thickness",
                        "clearance_left", "clearance_right", "clearance_top",
                        "clearance_bottom", "operating_gap_left",
                        "operating_gap_right", "operating_gap_top",
                        "frame_depth", "frame_depth_mode", "frame_recess",
                        "host_face", "family_key", "slide_side", "slide_open_fraction",
                        "slide_overlap", "leaf_variant", "hinge", "swing",
                        "plan_angle", "model_angle", "trim_front_enabled",
                        "trim_back_enabled", "trim_width", "trim_thickness"):
                self._show(key, physical)
            sliding = physical and spec.get("family_key") in ("sliding_surface", "sliding_pocket")
            for key in ("slide_side", "slide_open_fraction", "slide_overlap"):
                self._show(key, sliding)
            for key in ("hinge", "swing", "plan_angle", "model_angle"):
                self._show(key, physical)
            self._show("panes", not door and not spec.get("window_grid_enabled"))
            self._show("glass_thickness", not door)
            self._group_visible("leaf", physical or not door)
            for name in ('groove_count','groove_width','groove_end_margin','groove_offset'):
                self._show(name,physical and spec.get('leaf_variant')=='grooved')
            self._show("window_grid_enabled", not door)
            # Door composer has a permanent primary button on Porta tab.
            # Keep the inspector button only for windows to avoid duplicates.
            if self._leaf_button.isHidden() == (not door):
                self._leaf_button.setVisible(not door)
            self._set_label(self._leaf_button, t("Editar caixilho, vidros e divisões…"))
            if not door:
                grid = spec.get("window_grid")
                self._set_label(self._leaf_summary, t(
                    "Composição visual ativa" if spec.get("window_grid_enabled")
                    else "Divisão simples atual; abra o compositor para montar a janela."))
            if physical:
                grid = spec.get("leaf_grid")
                if spec.get("leaf_variant") == "grid" and grid:
                    self._set_label(self._leaf_summary, t(
                        "{0} colunas × {1} linhas · {2} painéis configuráveis").format(
                            grid["columns"], grid["rows"],
                            len(grid["cell_types"])))
                else:
                    self._set_label(self._leaf_summary, t(
                        "Folha atual sem grade. Edite para criar montantes, "
                        "travessas, vidro, painéis sólidos ou venezianas."))
            for key, _title in self._MATERIALS:
                self._show(key, (not door) if key.startswith("material_window_")
                           else physical)
            self._show("material_name", not door)
            self._group_visible("installation", physical or not door)
            self._group_visible("geometry", physical or not door)
            self._group_visible("materials", physical or not door)
            # The plan diagram angle is currently IFC metadata; it does not
            # rotate the 3D sash. It must not impersonate a functional tool.
            for name in ("family_key", "leaf_variant"):
                self._fields[name].setEnabled(False)
                self._fields[name].setToolTip(
                    "Escolha o sistema e o modelo acima; clique Aplicar / Converter "
                    "para modificar a porta selecionada.")
            self._fields["plan_angle"].setEnabled(False)
            self._fields["plan_angle"].setToolTip(
                "Ângulo em planta reservado para representação 2D; "
                "não altera a geometria 3D nesta versão.")
            for key in ("hinge", "swing"):
                self._fields[key].setEnabled(physical and not sliding)
                self._fields[key].setToolTip(
                    "Controle disponível somente para porta de giro."
                    if sliding else "Edita imediatamente a porta selecionada.")
            self._fields["model_angle"].setEnabled(physical and not sliding)
            self._fields["model_angle"].setToolTip(
                "Ângulo da folha no modelo 3D; disponível para portas de giro.")
            self._fields["trim_width"].setEnabled(physical and (
                spec["trim_front_enabled"] or spec["trim_back_enabled"]))
            self._fields["trim_thickness"].setEnabled(physical and (
                spec["trim_front_enabled"] or spec["trim_back_enabled"]))
        finally:
            self._loading = False
