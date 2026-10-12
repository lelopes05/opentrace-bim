# SPDX-License-Identifier: GPL-3.0-or-later
"""Timing of curved walls with openings: mouse hover snaps and one parameter edit.

Not a unit test. Run with the plugin and IngeTrazo on PYTHONPATH:
    QT_QPA_PLATFORM=offscreen python tests_host/bench_curved_walls.py
Uses only APIs present before and after the cache, so two revisions can be compared.
"""
import time

from PySide6.QtGui import QVector3D
from core.scene import Scene

from OpenTrace_BIM import model
from OpenTrace_BIM.commands import EditWall
from OpenTrace_BIM.snaprefs import snap_to_wall_references

WALLS = 6
OPENINGS = 4
HOVERS = 200


class Viewport:
    snap_threshold_px = 12.0

    def __init__(self, scene):
        self.scene = scene

    def _world_to_pixel(self, point):
        return (point.x() * 100.0, -point.y() * 100.0)


def build_scene():
    scene = Scene()
    for w in range(WALLS):
        openings = [{"id": f"w{w}-{i}", "position": 1.5 + 2.0 * i, "width": 0.8,
                     "sill": 0.9, "height": 1.2} for i in range(OPENINGS)]
        values = dict(model.DEFAULTS, openings=openings)
        y = 12.0 * w
        scene.groups.append(model.make_arc_wall(
            QVector3D(0, y, 0), QVector3D(8, y, 0), 2.0, values))
    return scene


def main():
    scene = build_scene()
    viewport = Viewport(scene)
    samples = len(model.wall_path(scene.groups[0]))

    start = time.perf_counter()
    for i in range(HOVERS):
        snap_to_wall_references(None, viewport, None, float(i * 4 % 800), float(-i % 300))
    hover_ms = (time.perf_counter() - start) * 1000.0 / HOVERS

    wall = scene.groups[0]
    values = model.read_wall(wall)
    values["thickness"] += 0.05
    start = time.perf_counter()
    EditWall(scene, wall, values).do(scene)
    edit_ms = (time.perf_counter() - start) * 1000.0

    print(f"{WALLS} curved walls x {OPENINGS} openings, {samples} samples per arc")
    print(f"hover snap: {hover_ms:.2f} ms per mouse move")
    print(f"edit thickness of one wall: {edit_ms:.1f} ms")


if __name__ == "__main__":
    main()
