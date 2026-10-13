# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure polygon opening regression tests, independent of PySide6/IngeTrazo."""
import unittest

from OpenTrace_BIM.wall_polygon import (
    arc_samples, clip_to_wall, contains, cut_stations, normalize_polygon, sample_outline,
    scan_edges,
)


class WallPolygonTests(unittest.TestCase):
    def test_free_rectangular_cut(self):
        pts = normalize_polygon([[1, 0], [2, 0], [2, 2.1], [1, 2.1]], 4)
        self.assertEqual(len(scan_edges(pts, 1.5)), 2)
        self.assertTrue(contains(pts, 1.5, 1.0))
        self.assertFalse(contains(pts, 0.5, 1.0))

    def test_concave_polygon_has_two_separate_voids_in_a_strip(self):
        pts = normalize_polygon([[1, 0.4], [3, 0.4], [3, 0.9], [2, 0.9],
                                 [2, 1.5], [3, 1.5], [3, 2.0], [1, 2.0]], 4)
        self.assertEqual(len(scan_edges(pts, 2.5)), 4)
        self.assertTrue(contains(pts, 2.5, 0.7))
        self.assertFalse(contains(pts, 2.5, 1.2))
        self.assertTrue(contains(pts, 2.5, 1.7))

    def test_self_intersection_rejected(self):
        with self.assertRaises(ValueError):
            normalize_polygon([[1, 0], [3, 2], [1, 2], [3, 0]], 4)

    def test_adjacent_backtracking_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_polygon([[1, 0.2], [3, 0.2], [2, 0.2],
                               [3, 2], [1, 2]], 5)

    def test_submillimetre_edge_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_polygon([[1, 0.3], [1.0005, 0.3],
                               [3, 0.3], [3, 2], [1, 2]], 5)

    def test_end_margin_rejected(self):
        with self.assertRaises(ValueError):
            normalize_polygon([[0, 0], [2, 0], [1, 2]], 4)

    def test_non_finite_rejected(self):
        with self.assertRaises(ValueError):
            normalize_polygon([[1, 0], [2, float("nan")], [1.5, 2]], 4)

    def test_profile_head_crossing(self):
        points = [[1, 1.5], [3, 2.5], [3, 3.5], [1, 3.5]]
        stations = cut_stations(points, 4, [0, 0], [3, 2])
        self.assertTrue(any(1 < x < 3 for x in stations))

    def test_clip_tall_opening_to_wall(self):
        ends = clip_to_wall([1, 2], [3, 4], 4, [0, 0], [3, 3])
        self.assertIsNotNone(ends)
        self.assertAlmostEqual(ends[1][1], 3)

    def test_outside_opening_edge_has_no_reveal(self):
        self.assertIsNone(clip_to_wall([1, 4], [2, 4], 4, [0, 0], [3, 3]))

    def test_arc_bulges_left_for_positive_sagitta(self):
        pts = arc_samples((0.0, 0.0), (2.0, 0.0), 0.5)
        self.assertEqual(pts[0], (0.0, 0.0))
        self.assertEqual(pts[-1], (2.0, 0.0))
        self.assertAlmostEqual(max(z for _s, z in pts), 0.5, places=3)

    def test_circle_outline_has_circle_area(self):
        import math
        r, cs, cz = 0.3, 2.0, 1.5
        quad = [[cs, cz - r], [cs + r, cz], [cs, cz + r], [cs - r, cz]]
        h = -r * (1 - math.cos(math.pi / 4))
        ring = sample_outline(quad, [{"type": "arc", "sagitta": h}] * 4)
        n = len(ring)
        area = sum(ring[i][0] * ring[(i + 1) % n][1] - ring[(i + 1) % n][0] * ring[i][1]
                   for i in range(n)) / 2
        self.assertAlmostEqual(area, math.pi * r * r, delta=0.01 * math.pi * r * r)
        normalize_polygon(ring, 4)

    def test_straight_outline_is_the_polygon(self):
        rect = [[1, 0.3], [3, 0.3], [3, 2], [1, 2]]
        self.assertEqual(sample_outline(rect, None), rect)

    def test_door_floor_edge_is_coplanar(self):
        ends = clip_to_wall([1, 0], [2, 0], 4, [0, 0], [3, 3])
        self.assertEqual(ends, ((1.0, 0.0), (2.0, 0.0)))


if __name__ == "__main__":
    unittest.main()
