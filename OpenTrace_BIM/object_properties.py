# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared layer and IFC properties backed by host entities and native history."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
from core.layers import DEFAULT_LAYER, layer_of
from core.history import AssignLayerCommand
from .bim import KIND_TO_CLASS, DEFAULT_PREDEFINED, ifc_identity_data, set_ifc_metadata
from .creation_properties import creation_defaults
from .host import WALL_TOOL_KEY, SLAB_TOOL_KEY, COLUMN_TOOL_KEY, BEAM_TOOL_KEY, host_tool
from .i18n import t
from .ifc_catalog import predefined_types

TOOL_KEYS = {
    "wall": WALL_TOOL_KEY, "slab": SLAB_TOOL_KEY,
    "column": COLUMN_TOOL_KEY, "beam": BEAM_TOOL_KEY,
    "door": "opentrace_wall_door_tool", "window": "opentrace_wall_window_tool",
}


def creation_kind(app):
    active = app.viewport.active_tool
    for kind, key in TOOL_KEYS.items():
        if active is host_tool(app, key):
            return kind
    return None


def selected_entities(scene):
    if scene.edit_group is not None:
        return []
    result = []
    for item in scene.selection:
        entity = getattr(item, "owner", None) or item
        if entity not in result:
            result.append(entity)
    return result


class ObjectProperties(QWidget):
    """One sidebar editor, with a mirrored layer selector in the Info Box."""
    def __init__(self, suite):
        super().__init__(suite.panel)
        self.suite = suite
        self.app = suite.app
        self._layer_combos = []
        self._signature = None
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 2, 6, 2)
        self.context = QLabel()
        root.addWidget(self.context)
        form = QFormLayout()
        self.layer = self.make_layer_combo(self)
        form.addRow(t("Layer"), self.layer)
        root.addLayout(form)
        from .panel_sections import EditorSection
        body = QWidget()
        fields = QFormLayout(body)
        self.ifc_class = QLabel()
        self.predefined = QComboBox()
        self.library = QComboBox()
        self.library.activated.connect(self.choose_classification)
        self.system = QLineEdit()
        self.code = QLineEdit()
        for field in (self.system, self.code):
            field.setPlaceholderText(t("Não definida"))
        fields.addRow(t("Classe IFC"), self.ifc_class)
        fields.addRow(t("Tipo predefinido"), self.predefined)
        fields.addRow(t("Biblioteca de classificações"), self.library)
        fields.addRow(t("Sistema de classificação"), self.system)
        fields.addRow(t("Código de classificação"), self.code)
        self.apply = QPushButton(t("Aplicar propriedades IFC"))
        self.apply.clicked.connect(self.apply_ifc)
        fields.addRow(self.apply)
        self.section = EditorSection(t("BIM / IFC"), body, collapsed=True)
        root.addWidget(self.section)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)

    def make_layer_combo(self, parent):
        combo = QComboBox(parent)
        combo.setObjectName("opentrace_object_layer")
        combo.setMinimumWidth(110)
        combo.setMaximumWidth(210)
        combo.setFocusPolicy(Qt.StrongFocus)
        combo.activated.connect(lambda _i, w=combo: self.assign_layer(w.currentData()))
        self._layer_combos.append(combo)
        return combo

    def _context(self):
        kind = creation_kind(self.app)
        entities = [] if kind else selected_entities(self.app.scene)
        return kind, entities

    def refresh(self):
        scene = self.app.scene
        kind, entities = self._context()
        defaults = creation_defaults(scene).get(kind, {})
        editable = scene.edit_group is None and (bool(kind) or bool(entities))
        editable = editable and all(scene.entity_selectable(e) for e in entities)
        values = {layer_of(e) for e in entities}
        chosen = defaults.get("layer", DEFAULT_LAYER) if kind else (next(iter(values)) if len(values) == 1 else None)
        names = [layer.name for layer in scene.layers]
        if chosen not in names and kind:
            chosen = DEFAULT_LAYER
        for combo in self._layer_combos:
            blocked = combo.blockSignals(True)
            combo.clear()
            if chosen is None and entities:
                combo.addItem(t("Vários layers"), None)
            for name in names:
                combo.addItem(name, name)
            combo.setCurrentIndex(combo.findData(chosen))
            combo.setEnabled(editable)
            combo.blockSignals(blocked)
        group = entities[0] if len(entities) == 1 and entities[0] in scene.groups else None
        meta = defaults.get("ifc", {}) if kind else (getattr(group, "ifc", None) or {})
        from .bim import element_kind
        cls = KIND_TO_CLASS.get(kind) if kind else (meta.get("class") or KIND_TO_CLASS.get(element_kind(group), "IfcBuildingElementProxy" if group else None))
        # Do not replace a partially typed classification on cursor movements.
        signature = (kind, tuple(id(e) for e in entities), repr(meta), cls, editable)
        if signature == self._signature:
            return
        self._signature = signature
        self.context.setText(t("Novos objetos") if kind else t("Objetos selecionados"))
        self.ifc_class.setText(cls or t("Não definida"))
        self.predefined.clear()
        if cls:
            self.predefined.addItems(predefined_types(cls))
            value = meta.get("predefined_type", DEFAULT_PREDEFINED.get(cls, "NOTDEFINED") if kind else "NOTDEFINED")
            self.predefined.setCurrentText(value)
        self.system.setText(str(meta.get("classification_system") or ""))
        self.code.setText(str(meta.get("classification_code") or ""))
        self.section.body.setEnabled(editable and bool(cls))
        from .bim import load_document_data
        from .bim_library import merged_library
        library = merged_library(load_document_data(self.app))["classifications"]
        self.library.clear()
        self.library.addItem(t("Escolher classificação"), None)
        for name, definition in sorted(library.items()):
            self.library.addItem(name, definition)
        assigned = [item for item in meta.get("classifications", [])
                    if isinstance(item, dict) and item.get("system") and item.get("code")]
        if assigned:
            self.status.setText("; ".join(f'{item["system"]}: {item["code"]}' for item in assigned))
        else:
            self.status.setText(t("Classificação: não definida")
                               if not (self.code.text() and self.system.text()) else "")

    def choose_classification(self, index):
        definition = self.library.itemData(index)
        if definition:
            self.system.setText(str(definition.get("system", "")))
            self.code.setText(str(definition.get("code", "")))

    def assign_layer(self, name):
        scene = self.app.scene
        if not name or scene.layer(name) is None:
            return
        kind, entities = self._context()
        if scene.edit_group is not None:
            return
        if kind:
            creation_defaults(scene).setdefault(kind, {})["layer"] = name
        elif entities and all(scene.entity_selectable(e) for e in entities):
            self.app.viewport.history.execute(AssignLayerCommand(entities, name))
            self.app.viewport.notify_scene_changed()
        self.refresh()
        self.app.viewport.setFocus()

    def apply_ifc(self):
        kind, entities = self._context()
        changes = {"predefined_type": self.predefined.currentText() or "NOTDEFINED",
                   "classification_system": self.system.text().strip(),
                   "classification_code": self.code.text().strip()}
        if kind and self.app.scene.edit_group is None:
            creation_defaults(self.app.scene).setdefault(kind, {})["ifc"] = changes
        elif len(entities) == 1 and entities[0] in self.app.scene.groups and self.app.scene.entity_selectable(entities[0]):
            meta = ifc_identity_data(entities[0])
            meta.update(changes)
            set_ifc_metadata(self.app, entities[0], meta)
        self.refresh()
