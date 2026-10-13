# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure schema-2 regression tests against frozen 5df646e schema-1 results."""
import copy
import unittest

from OpenTrace_BIM.door_window_core import (
    DOOR_FAMILIES, FillError, SCHEMA, SCHEMA_DOOR, door_leaf_plan,
    migrate_door, normalize_fill, opening_request, station_span,
    wallhole_size, wallhole_span,
)


def old(**changes):
    value = {"id": "door-1", "kind": "door", "host_id": "wall-1",
             "opening_id": "opening-1", "position": 2.0}
    value.update(changes)
    return value


def new(**changes):
    value = {"schema": 2, "id": "door-2", "kind": "door",
             "host_id": "wall-1", "opening_id": "opening-2",
             "position": 2.0}
    value.update(changes)
    return value


# Literal opening_request outputs observed under the schema-1 formula at
# 5df646e; no migration/new implementation is used to generate these.
_SCHEMA1_CASES = (
    (old(anchor="left", position=2.0, width=1.0, height=2.1, open_angle=0),
     2.5, 1.0, 2.1),
    (old(anchor="center", position=2.5, width=1.0, height=2.2, open_angle=45),
     2.5, 1.0, 2.2),
    (old(anchor="right", position=4.0, width=1.0, height=2.4, open_angle=90),
     3.5, 1.0, 2.4),
    (old(anchor="left", position=0.125, width=0.25, height=1.8, open_angle=45),
     0.25, 0.25, 1.8),  # narrow wall segment
    (old(anchor="right", position=0.375, width=0.25, height=1.9, open_angle=0),
     0.25, 0.25, 1.9),  # narrow wall segment
)


class DoorSchema2Tests(unittest.TestCase):
    def test_migrated_door_cuts_exactly_like_schema1(self):
        for legacy, position, width, height in _SCHEMA1_CASES:
            # Frozen output shape and expected values from the old code.
            expected = {
                "id": "opening-1", "kind": "rect", "position": position,
                "width": width, "sill": 0.0, "height": height,
                "source_id": "door-1", "ifc_global_id": "opening-guid",
                "fill": {"class": "IfcDoor", "global_id": None,
                         "name": "Porta", "overall_width": width,
                         "overall_height": height},
            }
            with self.subTest(legacy=legacy):
                self.assertEqual(opening_request(legacy, opening_guid="opening-guid"), expected)
                self.assertEqual(opening_request(migrate_door(legacy), opening_guid="opening-guid"), expected)

    def test_migrated_door_keeps_its_angle(self):
        for angle in (0, 45, 90, 180):
            result = normalize_fill(old(open_angle=angle))
            self.assertEqual(result["schema"], SCHEMA_DOOR)
            self.assertNotIn("unit_width", result)
            self.assertNotIn("unit_height", result)
            self.assertEqual(result["plan_angle"], angle)
            self.assertEqual(result["model_angle"], angle)
            self.assertNotIn("open_angle", result)
            self.assertEqual(result["host_mode"], "hosted")
            self.assertEqual(result["family_key"], "swing_single")
            self.assertEqual(wallhole_size(result), (result["width"], result["height"]))

    def test_new_door_defaults(self):
        result = normalize_fill(new())
        self.assertEqual(result["schema"], 2)
        self.assertEqual(result["family_key"], "swing_single")
        self.assertEqual(result["host_mode"], "hosted")
        self.assertEqual(result["anchor"], "center")
        self.assertEqual(result["plan_angle"], 90)
        self.assertEqual(result["model_angle"], 0)
        self.assertEqual((result["clearance_left"], result["clearance_right"],
                          result["clearance_top"], result["clearance_bottom"]),
                         (0.04, 0.04, 0.04, 0.0))
        self.assertNotIn("unit_width", result)
        self.assertNotIn("unit_height", result)
        self.assertAlmostEqual(wallhole_size(result)[0], result["width"] + 0.08)
        self.assertAlmostEqual(wallhole_size(result)[1], result["height"] + 0.04)
        self.assertNotIn("open_angle", result)

    def test_editing_nominal_moves_the_cut(self):
        # Migrated schema-1 records have zero clearance, so the physical cut
        # tracks edits exactly, without stale cached unit dimensions.
        for raw, width_margin, height_margin in (
            (old(anchor="center", width=0.90, height=2.10), 0.0, 0.0),
            (new(anchor="center", width=0.90, height=2.10), 0.08, 0.04),
        ):
            with self.subTest(schema=raw.get("schema", 1)):
                original = normalize_fill(raw)
                self.assertNotIn("unit_width", original)
                self.assertNotIn("unit_height", original)
                first = opening_request(original)
                width_edited = normalize_fill(dict(original, width=1.10))
                height_edited = normalize_fill(dict(original, height=2.20))
                self.assertNotIn("unit_width", width_edited)
                self.assertNotIn("unit_height", height_edited)
                widened = opening_request(width_edited)
                raised = opening_request(height_edited)
                self.assertAlmostEqual(widened["width"], 1.10 + width_margin)
                self.assertAlmostEqual(raised["height"], 2.20 + height_margin)
                self.assertAlmostEqual(widened["width"] - first["width"], 0.20)
                self.assertAlmostEqual(raised["height"] - first["height"], 0.10)
                self.assertAlmostEqual(widened["position"], first["position"])
                self.assertEqual(widened["fill"]["overall_width"], 1.10)
                self.assertEqual(raised["fill"]["overall_height"], 2.20)

    def test_explicit_unit_override_stays_independent(self):
        result = normalize_fill(new(width=0.9, height=2.1,
                                    unit_width=1.0, unit_height=2.3))
        self.assertEqual(result["unit_width"], 1.0)
        self.assertEqual(result["unit_height"], 2.3)
        changed = normalize_fill(dict(result, width=1.2, height=2.5))
        self.assertEqual(wallhole_size(changed), wallhole_size(result))
        self.assertEqual((changed["width"], changed["height"]), (1.2, 2.5))

    def test_instance_sizes_do_not_touch_family(self):
        initial_family = copy.deepcopy(DOOR_FAMILIES)
        first = normalize_fill(new(width=1.2, clearance_left=0.1))
        first["clearance_right"] = 0.3
        second = normalize_fill(new())
        self.assertEqual(DOOR_FAMILIES, initial_family)
        self.assertEqual(second["width"], 0.9)
        self.assertEqual(second["clearance_left"], 0.04)
        self.assertEqual(second["clearance_right"], 0.04)

    def test_wallhole_formula(self):
        spec = new(anchor="center", position=2.0, width=0.8, height=2.1,
                   unit_width=0.8, unit_height=2.12,
                   clearance_left=0.03, clearance_right=0.08,
                   clearance_top=0.06, clearance_bottom=0.02)
        w, h = wallhole_size(spec)
        left, right = wallhole_span(spec)
        self.assertAlmostEqual(w, 0.91)
        self.assertAlmostEqual(h, 2.20)
        self.assertAlmostEqual(left, 1.57)
        self.assertAlmostEqual(right, 2.48)
        self.assertAlmostEqual(sum(station_span(spec))/2, 2.0)
        request = opening_request(spec)
        self.assertAlmostEqual(request["width"], w)
        self.assertAlmostEqual(request["height"], h)
        self.assertAlmostEqual(request["position"], (left+right)/2)
        self.assertEqual(request["fill"]["overall_width"], 0.8)
        self.assertEqual(request["fill"]["overall_height"], 2.1)

    def test_angles_are_independent(self):
        first = door_leaf_plan(new(plan_angle=90, model_angle=0))
        changed_model = door_leaf_plan(new(plan_angle=90, model_angle=45))
        changed_plan = door_leaf_plan(new(plan_angle=45, model_angle=0))
        self.assertEqual(first, changed_model)
        self.assertNotEqual(first["tip"], changed_plan["tip"])

    def test_host_mode_rules(self):
        with self.assertRaises(FillError):
            normalize_fill(new(host_id=""))
        with self.assertRaises(FillError):
            normalize_fill(new(host_mode="free"))
        free = normalize_fill(new(host_mode="free", host_id="", opening_id=""))
        self.assertEqual((free["host_id"], free["opening_id"]), ("", ""))
        with self.assertRaises(FillError):
            opening_request(free)

    def test_disabled_family_is_refused(self):
        self.assertEqual(len(DOOR_FAMILIES), 8)
        self.assertEqual([k for k, v in DOOR_FAMILIES.items() if v["enabled"]], ["swing_single"])
        for key in DOOR_FAMILIES:
            if key == "swing_single":
                continue
            with self.subTest(key=key), self.assertRaisesRegex(FillError, "Família em desenvolvimento"):
                normalize_fill(new(family_key=key))

    def test_newer_schema_is_refused_with_diagnostic(self):
        with self.assertRaisesRegex(FillError, "schema 3"):
            normalize_fill(new(schema=3))

    def test_unknown_door_keys_survive_normalize(self):
        extension = {"custom": [1, {"material": "A"}]}
        source = new(vendor_data=extension, open_angle=77)
        saved = normalize_fill(source)
        self.assertEqual(saved["vendor_data"], extension)
        self.assertIsNot(saved["vendor_data"], extension)
        self.assertNotIn("open_angle", saved)
        self.assertEqual(source["vendor_data"], extension)
        legacy = old(vendor_data=extension)
        self.assertEqual(normalize_fill(legacy)["vendor_data"], extension)

    def test_window_record_unchanged(self):
        source = {"id": "window-1", "kind": "window", "host_id": "wall-1",
                  "opening_id": "opening-1", "position": 2.0, "unknown": "discard"}
        expected = {
            "schema": 1, "id": "window-1", "kind": "window",
            "host_id": "wall-1", "opening_id": "opening-1",
            "anchor": "left", "position": 2.0,
            "width": 1.2, "height": 1.2, "sill": 0.9,
            "frame_thickness": 0.04, "name": "Janela", "panes": 1,
        }
        self.assertEqual(SCHEMA, 1)
        self.assertEqual(normalize_fill(source), expected)


if __name__ == "__main__":
    unittest.main()
