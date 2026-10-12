# SPDX-License-Identifier: GPL-3.0-or-later
"""Curved walls with openings: hover snaps and overlays must not re-derive geometry.

Regression for the slowdown reported after hosted openings were added: every
arc sample re-ran ``validate()``, which renormalises all openings, on every
mouse move and every frame.
"""
import unittest
from types import SimpleNamespace

from PySide6.QtGui import QVector3D
from core.scene import Scene

from OpenTrace_BIM import model, wall_cache
from OpenTrace_BIM.commands import EditWall
from OpenTrace_BIM.snaprefs import snap_to_wall_references


def curved_wall_with_openings(count=4):
    openings = [{"id": f"w{i}", "position": 1.5 + 2.0 * i, "width": 0.8,
                 "sill": 0.9, "height": 1.2} for i in range(count)]
    values = dict(model.DEFAULTS, openings=openings)
    return model.make_arc_wall(QVector3D(0, 0, 0), QVector3D(8, 0, 0), 2.0, values)


class CountingValidate:
    def __init__(self):
        self.calls = 0
        self._original = model.validate

    def __call__(self, values):
        self.calls += 1
        return self._original(values)

    def __enter__(self):
        model.validate = self
        return self

    def __exit__(self, *exc):
        model.validate = self._original


class FakeViewport:
    snap_threshold_px = 12.0

    def __init__(self, scene):
        self.scene = scene

    def _world_to_pixel(self, point):
        return (point.x() * 100.0, -point.y() * 100.0)


class CurvedWallSamplingTests(unittest.TestCase):
    def test_sampling_validates_once_not_once_per_arc_sample(self):
        wall = curved_wall_with_openings()
        samples = len(model.wall_path(wall))
        self.assertGreater(samples, 20)
        with CountingValidate() as counter:
            model.base_path_world(wall)
        # read_wall + _profiled_sample_paths; previously one more per sample.
        self.assertLessEqual(counter.calls, 3)

    def test_rebuild_validates_a_bounded_number_of_times(self):
        wall = curved_wall_with_openings()
        values = model.read_wall(wall)
        samples = len(model.wall_path(wall))
        with CountingValidate() as counter:
            model.build_children(values, path=model.wall_path(wall), smooth_path=True)
        self.assertLess(counter.calls, samples)


class WallCacheTests(unittest.TestCase):
    def setUp(self):
        self.scene = Scene()
        self.wall = curved_wall_with_openings()
        self.scene.groups.append(self.wall)

    def test_same_version_reuses_geometry(self):
        first = wall_cache.base_path(self.scene, self.wall)
        with CountingValidate() as counter:
            second = wall_cache.base_path(self.scene, self.wall)
            wall_cache.values(self.scene, self.wall)
            wall_cache.values(self.scene, self.wall)
        self.assertIs(first, second)
        self.assertEqual(counter.calls, 1)  # values() computed once

    def test_edit_invalidates_and_returns_new_geometry(self):
        before = wall_cache.base_path(self.scene, self.wall)
        values = model.read_wall(self.wall)
        values["thickness"] = values["thickness"] + 0.1
        values["base"] = values["base"] + 1.0
        EditWall(self.scene, self.wall, values).do(self.scene)
        after = wall_cache.base_path(self.scene, self.wall)
        self.assertIsNot(before, after)
        self.assertAlmostEqual(after[0].z(), before[0].z() + 1.0, places=6)

    def test_invalid_wall_error_is_cached_and_raised(self):
        self.wall.ext = {}
        with self.assertRaises(model.WallError):
            wall_cache.base_path(self.scene, self.wall)
        with CountingValidate() as counter, self.assertRaises(model.WallError):
            wall_cache.base_path(self.scene, self.wall)
        self.assertEqual(counter.calls, 0)

    def test_hover_snap_does_not_revalidate_on_repeated_moves(self):
        viewport = FakeViewport(self.scene)
        snap_to_wall_references(None, viewport, None, 0.0, 0.0)
        with CountingValidate() as counter:
            for x in range(50):
                snap_to_wall_references(None, viewport, None, float(x * 10), 0.0)
        self.assertEqual(counter.calls, 0)


if __name__ == "__main__":
    unittest.main()
