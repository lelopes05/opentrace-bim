# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure F01 leaf-composition contract, independent from Qt and the scene.

The grid is a true assembly of stiles, rails, mullions, transoms and cell
infill, not a full opaque door with cosmetic glass attached to its faces.
Dimensions are metres. Cell order is bottom-to-top, left-to-right.
"""
from __future__ import annotations

import math


PANEL_KINDS = ("glass", "solid", "louver", "open")
DEFAULT_GRID = {
    "columns": 2,
    "rows": 3,
    "stile_width": 0.08,
    "rail_width": 0.10,
    "mullion_width": 0.045,
    "transom_width": 0.045,
    "glass_thickness": 0.008,
    "panel_thickness": 0.018,
    "cell_types": ["solid", "solid", "glass", "glass", "glass", "glass"],
}


def normalize_leaf_grid(raw, width, height, leaf_thickness):
    """Return a canonical, bounded, JSON-safe grid or raise ValueError.

    Cells are stored as an array rather than floating-point coordinates, so
    resizing a leaf recomputes its true geometry without drifting positions.
    """
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("Composição da folha deve ser um registro.")
    result = {}
    for key in ("columns", "rows"):
        value = raw.get(key, DEFAULT_GRID[key])
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8:
            raise ValueError("Montantes/travessas: quantidade deve ser de 1 a 8.")
        result[key] = value
    for key in ("stile_width", "rail_width", "mullion_width", "transom_width",
                "glass_thickness", "panel_thickness"):
        value = raw.get(key, DEFAULT_GRID[key])
        if isinstance(value, bool):
            raise ValueError("Espessura da composição inválida.")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Espessura da composição inválida.") from exc
        if not math.isfinite(number) or number <= 0:
            raise ValueError("Medida da composição deve ser positiva.")
        result[key] = number
    if result["glass_thickness"] >= leaf_thickness:
        raise ValueError("Vidro deve ser mais fino que a folha.")
    if result["panel_thickness"] > leaf_thickness:
        raise ValueError("Painel não pode ser mais espesso que a folha.")
    cols, rows = result["columns"], result["rows"]
    usable_width = (width - 2 * result["stile_width"]
                    - (cols - 1) * result["mullion_width"])
    usable_height = (height - 2 * result["rail_width"]
                     - (rows - 1) * result["transom_width"])
    if usable_width < cols * .02 or usable_height < rows * .02:
        raise ValueError("Larguras da estrutura excedem a folha.")
    raw_cells = raw.get("cell_types")
    if raw_cells is None:
        raw_cells = (DEFAULT_GRID["cell_types"] if cols == 2 and rows == 3
                     else ["glass"] * (cols * rows))
    if not isinstance(raw_cells, (list, tuple)) or len(raw_cells) != cols * rows:
        raise ValueError("Número de painéis diferente da malha da folha.")
    if any(cell not in PANEL_KINDS for cell in raw_cells):
        raise ValueError("Tipo de painel de porta desconhecido.")
    result["cell_types"] = list(raw_cells)
    return result


def leaf_grid_parts(grid, width, height):
    """Yield (name, component, x0, x1, z0, z1) in local leaf coordinates.

    Frames fill the perimeter. Internal members divide the unobstructed area.
    Every cell infill sits between its members and can be empty or glazed.
    """
    cols, rows = grid["columns"], grid["rows"]
    stile = grid["stile_width"]
    rail = grid["rail_width"]
    mullion = grid["mullion_width"]
    transom = grid["transom_width"]
    clear_width = (width - 2 * stile - (cols - 1) * mullion) / cols
    clear_height = (height - 2 * rail - (rows - 1) * transom) / rows
    yield ("Montante lateral E", "leaf_stile", 0, stile, 0, height)
    yield ("Montante lateral D", "leaf_stile", width-stile, width, 0, height)
    yield ("Travessa inferior", "leaf_rail", stile, width-stile, 0, rail)
    yield ("Travessa superior", "leaf_rail", stile, width-stile, height-rail, height)
    for col in range(1, cols):
        x = stile + col * clear_width + (col - 1) * mullion
        yield (f"Montante {col}", "leaf_mullion", x, x+mullion,
               rail, height-rail)
    for row in range(1, rows):
        z = rail + row * clear_height + (row - 1) * transom
        yield (f"Travessa {row}", "leaf_transom", stile, width-stile,
               z, z+transom)
    for row in range(rows):
        z = rail + row * (clear_height + transom)
        for col in range(cols):
            x = stile + col * (clear_width + mullion)
            panel = grid["cell_types"][row*cols+col]
            if panel != "open":
                yield (f"Painel {row+1}-{col+1} ({panel})",
                       "leaf_" + panel, x, x+clear_width, z, z+clear_height)
