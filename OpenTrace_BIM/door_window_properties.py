# SPDX-License-Identifier: GPL-3.0-or-later
"""Instance-only hosted fill controls; never activates modelling tools.

Every user action is delegated to WallController's EditHostedFill command.
No values are copied between instances or written directly into scene records.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QLabel, QToolButton,
    QVBoxLayout, QWidget,
)

from .door_window_core import f01_unit_size, normalize_fill, wallhole_size
from .i18n import t, ui_locale
from .materials import material_catalog
from .widgets import FlexibleDoubleSpinBox


class FillPropertiesPanel(QWidget):
    """Collapsible controls for the implemented F01 and simple window motor."""

    _MATERIALS = (
        ("material_leaf_front", "Face externa da folha"),
        ("material_leaf_back", "Face interna da folha"),
        ("material_leaf_edge", "Borda da folha"),
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
            ("dimensions", "Dimensões da esquadria"),
            ("installation", "Instalação e batente"),
            ("geometry", "Folha, giro e guarnições"),
            ("materials", "Materiais por componente"),
        ):
            frame = QFrame(self)
            outer = QVBoxLayout(frame)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(3)
            toggle = QToolButton(frame)
            toggle.setCheckable(True)
            toggle.setChecked(key == "dimensions")
            toggle.setText(t(title))
            toggle.setArrowType(Qt.DownArrow if toggle.isChecked() else Qt.RightArrow)
            content = QWidget(frame)
            form = QFormLayout(content)
            form.setContentsMargins(8, 2, 0, 2)
            form.setSpacing(5)
            def expand(checked, body=content, button=toggle):
                body.setVisible(checked)
                button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
            toggle.toggled.connect(expand)
            outer.addWidget(toggle)
            outer.addWidget(content)
            expand(toggle.isChecked())
            root.addWidget(frame)
            self._forms[key] = form
            self._groups[key] = (frame, toggle)
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

        self._choice("geometry", "leaf_variant", "Variante F01",
                     (("Lisa", "plain"), ("Frisada", "grooved"),
                      ("Almofadada", "panelled")))
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
        self.setVisible(False)

    def _add(self, section, key, label, widget):
        widget.setObjectName("opentrace_fill_" + key)
        self._fields[key] = widget
        form = self._forms[section]
        form.addRow(t(label), widget)
        self._rows[key] = form.labelForField(widget)

    def _number(self, section, key, label, minimum, step, *,
                maximum=100.0, decimals=4, suffix=" m"):
        field = FlexibleDoubleSpinBox(self)
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
        field = QComboBox(self)
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
        self.submit({name: value})

    def _show(self, key, visible):
        self._fields[key].setVisible(visible)
        label = self._rows.get(key)
        if label is not None:
            label.setVisible(visible)

    def load(self, raw, scene):
        self._loading = True
        try:
            self._spec = normalize_fill(raw) if raw is not None else None
            spec = self._spec
            self.setVisible(spec is not None)
            if spec is None:
                return
            door = spec["kind"] == "door"
            physical = door and spec.get("f01_layout") == "physical"
            unit_width, unit_height = (
                f01_unit_size(spec) if door else (spec["width"], spec["height"]))
            rough_width, rough_height = (
                wallhole_size(spec) if door else (spec["width"], spec["height"]))
            values = dict(spec, glass_thickness=spec.get("glass_thickness", 0.006),
                          unit_width=unit_width, unit_height=unit_height,
                          rough_width=rough_width, rough_height=rough_height,
                          unit_width_manual="unit_width" in spec,
                          unit_height_manual="unit_height" in spec)
            for key, field in self._fields.items():
                if key in ("rough_width", "rough_height"):
                    field.setText(f'{values[key]:.4f} m')
                elif isinstance(field, QCheckBox):
                    field.setChecked(bool(values.get(key, False)))
                elif isinstance(field, QComboBox) and key.startswith("material_"):
                    continue
                elif isinstance(field, QComboBox):
                    target = values.get(key)
                    index = field.findData(target)
                    field.setCurrentIndex(index if index >= 0 else 0)
                else:
                    field.setValue(float(values.get(key, 0)))
            for key in ("unit_width", "unit_height"):
                self._fields[key].setEnabled(key in spec)
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
            self._rows["width"].setText(
                t("Largura física da folha") if door else t("Largura da janela"))
            self._rows["height"].setText(
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
                        "host_face", "leaf_variant", "hinge", "swing",
                        "plan_angle", "model_angle", "trim_front_enabled",
                        "trim_back_enabled", "trim_width", "trim_thickness"):
                self._show(key, physical)
            self._show("panes", not door)
            self._show("glass_thickness", not door)
            for key, _title in self._MATERIALS:
                self._show(key, (not door) if key.startswith("material_window_")
                           else physical)
            self._show("material_name", not door)
            self._groups["installation"][0].setVisible(physical or not door)
            self._groups["geometry"][0].setVisible(physical or not door)
            self._groups["materials"][0].setVisible(physical or not door)
        finally:
            self._loading = False
