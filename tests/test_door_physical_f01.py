# SPDX-License-Identifier: GPL-3.0-or-later
"""Physical F01 contracts, independent of the IngeTrazo graphics host."""
import unittest

from OpenTrace_BIM.door_window_core import (
    FillError, normalize_fill, f01_minimum_unit, f01_unit_size,
    station_span, wallhole_size, wallhole_span, opening_request,
    edit_fill_from_cut_dimension,
)


def physical(**overrides):
    data = {"schema": 2, "f01_layout": "physical", "kind": "door",
            "id": "door-physical", "host_id": "wall-1",
            "opening_id": "opening-1", "position": 2.0,
            "anchor": "center", "width": 0.8, "height": 2.1,
            "frame_thickness": 0.04}
    data.update(overrides)
    return data


class PhysicalF01Tests(unittest.TestCase):
    def test_full_sized_leaf_and_independent_operating_installation_gaps(self):
        spec = normalize_fill(physical())
        self.assertAlmostEqual(spec["width"], 0.8)
        self.assertEqual((spec["clearance_left"], spec["clearance_right"],
                          spec["clearance_top"]), (0.04, 0.04, 0.04))
        self.assertAlmostEqual(f01_minimum_unit(spec)[0], 0.886)
        self.assertAlmostEqual(f01_unit_size(spec)[0], 0.886)
        self.assertAlmostEqual(wallhole_size(spec)[0], 0.966)
        self.assertAlmostEqual(wallhole_size(spec)[1], 2.183)
        rough_left, rough_right = wallhole_span(spec)
        leaf_left, leaf_right = station_span(spec)
        self.assertAlmostEqual(leaf_right-leaf_left, 0.80)
        self.assertAlmostEqual(leaf_left-rough_left, 0.083)
        self.assertAlmostEqual(rough_right-leaf_right, 0.083)
        self.assertAlmostEqual(opening_request(spec)["width"], 0.966)

    def test_external_unit_override_cannot_shrink_physical_leaf(self):
        with self.assertRaises(FillError):
            normalize_fill(physical(unit_width=0.88))
        with self.assertRaises(FillError):
            normalize_fill(physical(unit_height=2.12))
        manual=normalize_fill(physical(unit_width=0.95, unit_height=2.25))
        self.assertAlmostEqual(wallhole_size(manual)[0], 1.03)
        self.assertAlmostEqual(wallhole_size(manual)[1], 2.29)
        with self.assertRaises(FillError):
            normalize_fill(dict(manual, width=0.95))

    def test_legacy_schema2_preserves_rough_cut_and_unknown_fields(self):
        saved = physical()
        saved.pop("f01_layout")
        saved["vendor_data"] = {"last": "keep"}
        legacy = normalize_fill(saved)
        self.assertNotIn("f01_layout", legacy)
        self.assertEqual(legacy["vendor_data"], {"last": "keep"})
        self.assertAlmostEqual(wallhole_size(legacy)[0], 0.88)
        self.assertAlmostEqual(wallhole_size(legacy)[1], 2.14)

    def test_variant_frame_trim_and_material_fields_round_trip(self):
        payload=physical(
            leaf_variant="panelled", frame_depth_mode="manual",
            frame_depth=0.15, host_face="right", frame_recess=0.02,
            trim_back_enabled=False, trim_width=0.065,
            material_leaf_front={"color": [200, 100, 40]},
            material_leaf_back={"color": [20, 70, 130]},
            material_trim_front={"color": [200, 200, 200]})
        normalized=normalize_fill(payload)
        self.assertEqual(normalized["leaf_variant"], "panelled")
        self.assertEqual(normalized["frame_depth"], 0.15)
        self.assertEqual(normalized["host_face"], "right")
        self.assertFalse(normalized["trim_back_enabled"])
        self.assertNotEqual(normalized["material_leaf_front"],
                            normalized["material_leaf_back"])
        self.assertEqual(normalize_fill(normalized), normalized)

    def test_cut_field_changes_both_directions_without_compounding_clearances(self):
        current = normalize_fill(physical())
        cut = wallhole_size(current)[0]
        self.assertAlmostEqual(cut, 0.966)
        down = edit_fill_from_cut_dimension(current, "width", cut - 0.10)
        changed = normalize_fill(dict(current, **down))
        self.assertAlmostEqual(changed["width"], 0.70)
        self.assertAlmostEqual(wallhole_size(changed)[0], cut - 0.10)
        up = edit_fill_from_cut_dimension(
            changed, "width", wallhole_size(changed)[0] + 0.10)
        restored = normalize_fill(dict(changed, **up))
        self.assertAlmostEqual(restored["width"], 0.80)
        self.assertAlmostEqual(wallhole_size(restored)[0], cut)
        tall = edit_fill_from_cut_dimension(
            current, "height", wallhole_size(current)[1] + 0.10)
        self.assertAlmostEqual(tall["height"], 2.20)

    def test_cut_field_updates_explicit_unit_not_leaf(self):
        current = normalize_fill(physical(unit_width=0.95))
        original = wallhole_size(current)[0]
        adjustment = edit_fill_from_cut_dimension(
            current, "width", original - 0.02)
        self.assertEqual(set(adjustment), {"unit_width"})
        revised = normalize_fill(dict(current, **adjustment))
        self.assertAlmostEqual(revised["width"], 0.80)
        self.assertAlmostEqual(wallhole_size(revised)[0], original - 0.02)
        with self.assertRaises(FillError):
            edit_fill_from_cut_dimension(current, "width", 0.60)

    def test_cut_field_window_is_direct_dimension(self):
        current = normalize_fill({
            "kind": "window", "id": "window-1",
            "host_id": "wall-1", "opening_id": "hole-1",
            "position": 2.0, "width": 1.20, "height": 1.10,
        })
        self.assertEqual(edit_fill_from_cut_dimension(
            current, "width", 1.10), {"width": 1.10})
        self.assertEqual(edit_fill_from_cut_dimension(
            current, "height", 1.20), {"height": 1.20})

    def test_invalid_variant_and_face_raise(self):
        for change in ({"leaf_variant": "unsupported"},
                       {"host_face": "roof"},
                       {"frame_depth_mode": "unknown"},
                       {"operating_gap_left": -0.01}):
            with self.subTest(change=change), self.assertRaises(FillError):
                normalize_fill(physical(**change))


if __name__ == "__main__":
    unittest.main()
