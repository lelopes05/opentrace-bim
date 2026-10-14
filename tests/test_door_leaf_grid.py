# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression coverage for the host-independent F01 leaf grid."""
import unittest

from OpenTrace_BIM.door_leaf_grid import (
    DEFAULT_GRID, PANEL_KINDS, leaf_grid_parts, normalize_leaf_grid,
)
from OpenTrace_BIM.door_window_core import FillError, normalize_fill


def door(**changes):
    spec = {
        "kind": "door", "schema": 2, "f01_layout": "physical",
        "id": "door-1", "host_id": "wall-1", "opening_id": "open-1",
        "position": 2.0, "width": 0.90, "height": 2.10,
        "leaf_variant": "grid",
    }
    spec.update(changes)
    return spec


class DoorLeafGridTests(unittest.TestCase):
    def test_existing_plain_door_stays_without_grid(self):
        plain = normalize_fill(dict(door(), leaf_variant="plain"))
        self.assertNotIn("leaf_grid", plain)
        self.assertEqual(plain["leaf_variant"], "plain")

    def test_default_grid_geometry_is_real_partition_not_slab(self):
        spec = normalize_fill(door())
        grid = spec["leaf_grid"]
        self.assertEqual((grid["columns"], grid["rows"]), (2, 3))
        parts = list(leaf_grid_parts(grid, spec["width"], spec["height"]))
        self.assertEqual(sum(c == "leaf_stile" for _, c, *_ in parts), 2)
        self.assertEqual(sum(c == "leaf_mullion" for _, c, *_ in parts), 1)
        self.assertEqual(sum(c == "leaf_transom" for _, c, *_ in parts), 2)
        self.assertEqual(sum(c == "leaf_rail" for _, c, *_ in parts), 2)
        self.assertEqual(sum(c in ("leaf_glass", "leaf_solid")
                             for _, c, *_ in parts), 6)
        for _name, _component, x0, x1, z0, z1 in parts:
            self.assertGreater(x1, x0)
            self.assertGreater(z1, z0)
            self.assertGreaterEqual(x0, 0)
            self.assertGreaterEqual(z0, 0)
            self.assertLessEqual(x1, spec["width"])
            self.assertLessEqual(z1, spec["height"])

    def test_independent_infill_and_materials_survive_normalization(self):
        cells = ["glass", "solid", "louver", "open"]
        spec = normalize_fill(door(leaf_grid={
            "columns": 2, "rows": 2, "cell_types": cells,
            "glass_thickness": 0.01, "stile_width": 0.06,
            "rail_width": 0.08, "mullion_width": 0.03,
            "transom_width": 0.04, "panel_thickness": 0.02,
        }, material_leaf_glass={"mat": "Vidro", "opacity": 0.3},
           material_leaf_solid={"mat": "Madeira"}))
        self.assertEqual(spec["leaf_grid"]["cell_types"], cells)
        self.assertEqual(spec["material_leaf_glass"]["opacity"], 0.3)
        self.assertEqual(normalize_fill(spec), spec)
        types = [c for _, c, *_ in leaf_grid_parts(
            spec["leaf_grid"], spec["width"], spec["height"])]
        self.assertIn("leaf_glass", types)
        self.assertIn("leaf_solid", types)
        self.assertIn("leaf_louver", types)
        self.assertNotIn("leaf_open", types)

    def test_rejects_unbuildable_or_unstable_designs(self):
        invalid = (
            {"columns": 9},
            {"rows": 0},
            {"columns": 2, "rows": 2, "cell_types": ["glass"]},
            {"columns": 2, "rows": 2,
             "cell_types": ["glass", "solid", "foo", "open"]},
            {"stile_width": 0.5},
            {"rail_width": 1.1},
            {"glass_thickness": 0.035},
            {"panel_thickness": float("nan")},
            {"columns": True},
        )
        for grid in invalid:
            with self.subTest(grid=grid), self.assertRaises(FillError):
                normalize_fill(door(leaf_grid=grid))

    def test_roundtrip_resizing_recomputes_all_bounds(self):
        original = normalize_fill(door())
        bigger = normalize_fill(dict(original, width=1.20, height=2.30))
        parts = list(leaf_grid_parts(
            bigger["leaf_grid"], bigger["width"], bigger["height"]))
        self.assertAlmostEqual(max(p[5] for p in parts), 2.30)
        self.assertAlmostEqual(max(p[3] for p in parts), 1.20)
        self.assertEqual(original["leaf_grid"]["cell_types"],
                         bigger["leaf_grid"]["cell_types"])


if __name__ == "__main__":
    unittest.main()
