# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-instance F01 leaf editor; all changes are submitted as one history edit."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QMessageBox, QSpinBox, QTableWidget,
    QVBoxLayout, QWidget,
)

from .door_leaf_grid import DEFAULT_GRID, PANEL_KINDS, normalize_leaf_grid
from .i18n import t, ui_locale


TYPES = (
    ("Vidro", "glass"),
    ("Painel sólido", "solid"),
    ("Veneziana", "louver"),
    ("Vazio", "open"),
)


class DoorLeafGridDialog(QDialog):
    """A grid editor with cell-by-cell selection, bottom-to-top indices.

    It does not mutate a document or use a global preset. The caller submits
    the one returned leaf_grid dictionary through EditHostedFill (Undo/Redo).
    """

    def __init__(self, spec, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Editar composição da folha"))
        self.setMinimumWidth(470)
        self._width = spec["width"]
        self._height = spec["height"]
        self._thickness = spec["leaf_thickness"]
        grid = normalize_leaf_grid(spec.get("leaf_grid"), self._width,
                                   self._height, self._thickness)
        self._saved = {}
        self._cell_fields = {}
        self._dimensions = {}
        root = QVBoxLayout(self)
        root.addWidget(QLabel(t(
            "Montantes verticais, travessas horizontais e painéis reais. "
            "A primeira linha da tabela é a parte superior da porta."), self))
        options = QWidget(self)
        form = QFormLayout(options)
        for key, title, upper in (("columns", "Colunas", 8),
                                  ("rows", "Linhas", 8)):
            field = QSpinBox(self)
            field.setRange(1, upper)
            field.setValue(grid[key])
            field.valueChanged.connect(self._rebuild)
            form.addRow(t(title), field)
            self._dimensions[key] = field
        for key, title in (
            ("stile_width", "Largura dos montantes laterais"),
            ("rail_width", "Largura das travessas superior/inferior"),
            ("mullion_width", "Largura dos montantes internos"),
            ("transom_width", "Largura das travessas internas"),
            ("glass_thickness", "Espessura do vidro"),
            ("panel_thickness", "Espessura dos painéis"),
        ):
            field = QDoubleSpinBox(self)
            field.setLocale(ui_locale())
            field.setRange(0.001, 1.0)
            field.setDecimals(4)
            field.setSingleStep(0.005)
            field.setSuffix(" m")
            field.setValue(grid[key])
            form.addRow(t(title), field)
            self._dimensions[key] = field
        root.addWidget(options)
        self._table = QTableWidget(self)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self._table)
        self._saved = {(r, c): grid["cell_types"][r*grid["columns"]+c]
                       for r in range(grid["rows"])
                       for c in range(grid["columns"])}
        self._rebuild()
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _snapshot(self):
        for key, field in self._cell_fields.items():
            self._saved[key] = field.currentData()

    def _rebuild(self, *_):
        self._snapshot()
        rows = self._dimensions["rows"].value()
        cols = self._dimensions["columns"].value()
        self._table.setRowCount(rows)
        self._table.setColumnCount(cols)
        self._table.setHorizontalHeaderLabels([str(i+1) for i in range(cols)])
        self._table.setVerticalHeaderLabels([
            str(rows-i) for i in range(rows)])
        self._cell_fields = {}
        for screen_row in range(rows):
            actual_row = rows-1-screen_row
            for col in range(cols):
                field = QComboBox(self._table)
                for title, kind in TYPES:
                    field.addItem(t(title), kind)
                kind = self._saved.get((actual_row, col), "glass")
                found = field.findData(kind)
                field.setCurrentIndex(found if found >= 0 else 0)
                self._table.setCellWidget(screen_row, col, field)
                self._cell_fields[(actual_row, col)] = field
        self._table.resizeRowsToContents()

    def result_grid(self):
        cols = self._dimensions["columns"].value()
        rows = self._dimensions["rows"].value()
        raw = {key: field.value() for key, field in self._dimensions.items()}
        raw["cell_types"] = [
            self._cell_fields[(row, col)].currentData()
            for row in range(rows) for col in range(cols)
        ]
        return normalize_leaf_grid(
            raw, self._width, self._height, self._thickness)

    def _validate(self):
        try:
            self.result_grid()
        except ValueError as exc:
            QMessageBox.warning(self, t("Composição da folha"), t(str(exc)))
            return
        self.accept()
