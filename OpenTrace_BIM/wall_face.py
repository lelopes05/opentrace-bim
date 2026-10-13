# SPDX-License-Identifier: GPL-3.0-or-later
"""The face of a wall as a flat 2D sheet: station along the wall × height.

Wall openings are drawn and edited in this sheet exactly like slab openings are
edited in plan: a point is ``QVector3D(station, height, 0)``. For a straight
wall the sheet is a plane; for a curved wall it is the wall unrolled, and every
outline is mapped back onto the curve sample by sample, never by chords.
Heights are measured from the wall's own (possibly sloped) base.
"""
from __future__ import annotations

import bisect
import math

from PySide6.QtGui import QVector3D

from .model import (_interp_validated, _offset_path, _path_cumulative, path_world,
                    read_wall, wall_offsets)

SIDES = ("near", "far")


class WallFace:
    def __init__(self, wall, values=None):
        self.wall = wall
        self.values = values if values is not None else read_wall(wall)
        world = path_world(wall)
        self.origin_z = float(world[0].z())
        self.points, self.cum = _path_cumulative([QVector3D(p.x(), p.y(), 0.0) for p in world])
        self.length = self.cum[-1]
        low, high = wall_offsets(self.values)
        self.sides = {"near": _offset_path(self.points, low),
                      "far": _offset_path(self.points, high),
                      "mid": _offset_path(self.points, (low + high) * 0.5)}
        # Finest station step of the host path: outlines are resampled at
        # least this densely so they follow a curved wall instead of cutting it.
        steps = [b - a for a, b in zip(self.cum, self.cum[1:]) if b - a > 1e-9]
        self.step = min(steps) if len(steps) > 1 else math.inf

    # -- sheet -> world -------------------------------------------------
    def base_height(self, station):
        if self.length <= 1e-12:
            return 0.0
        base, _top, _off = _interp_validated(self.values, station / self.length)
        return base

    def _xy(self, side, station):
        pts, cum = self.sides[side], self.cum
        n = len(cum)
        if station <= 0.0 or station >= self.length:
            # Beyond an end: continue the end tangent, so an opening left past a
            # shortened wall stays visible and editable.
            i = 0 if station <= 0.0 else n - 2
            a, b = pts[i], pts[i + 1]
            span = cum[i + 1] - cum[i]
            u = (station - cum[i]) / span if span > 1e-12 else 0.0
            return a + (b - a) * u
        i = max(0, min(n - 2, bisect.bisect_right(cum, station) - 1))
        span = cum[i + 1] - cum[i]
        u = (station - cum[i]) / span if span > 1e-12 else 0.0
        return pts[i] + (pts[i + 1] - pts[i]) * u

    def world(self, p, side="near"):
        station, height = float(p.x()), float(p.y())
        xy = self._xy(side, station)
        return QVector3D(xy.x(), xy.y(), self.origin_z + self.base_height(station) + height)

    # -- world -> sheet -------------------------------------------------
    def station(self, world):
        # Project on the near face with the same per-segment parameter that
        # world() interpolates with, so sheet(world(p)) == p exactly even when
        # the face is offset (mitred) from the reference line.
        q = QVector3D(world.x(), world.y(), 0.0)
        side = self.sides["near"]
        best = None
        for i, (a, b) in enumerate(zip(side, side[1:])):
            d = b - a
            den = QVector3D.dotProduct(d, d)
            u = 0.0 if den <= 1e-12 else QVector3D.dotProduct(q - a, d) / den
            first, last = i == 0, i == len(side) - 2
            u = max(-math.inf if first else 0.0, min(math.inf if last else 1.0, u))
            dist = (q - (a + d * u)).lengthSquared()
            if best is None or dist < best[0]:
                best = (dist, self.cum[i] + (self.cum[i + 1] - self.cum[i]) * u)
        return float(best[1])

    def sheet(self, world):
        s = self.station(world)
        return QVector3D(s, float(world.z()) - self.origin_z - self.base_height(s), 0.0)

    def tangent_plane(self, station, height=0.0):
        """(point, normal) of the vertical plane touching the near face."""
        i = max(0, min(len(self.cum) - 2, bisect.bisect_right(self.cum, station) - 1))
        d = self.points[i + 1] - self.points[i]
        length = math.hypot(d.x(), d.y()) or 1.0
        normal = QVector3D(-d.y() / length, d.x() / length, 0.0)
        return self.world(QVector3D(station, height, 0.0), "near"), normal
