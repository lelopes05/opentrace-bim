# SPDX-License-Identifier: GPL-3.0-or-later
"""Derived wall geometry shared by snaps and overlays, computed once per document version.

Hover snaps run on every mouse move and overlays on every frame. Both asked for
the same wall paths again and again, and a curved wall re-reads, re-validates
and re-samples its whole record each time. Those values only change when the
document changes, so they are memoised against ``scene.version`` and dropped
as soon as it moves. Tools that edit geometry keep calling ``model`` directly.
"""
from __future__ import annotations

from . import model
from .model import WallError


class _VersionMemo:
    def __init__(self):
        self._version_key = None
        self._items = {}

    def get(self, scene, key, compute):
        version_key = (id(scene), scene.version)
        if version_key != self._version_key:
            self._items.clear()
            self._version_key = version_key
        try:
            ok, value = self._items[key]
        except KeyError:
            try:
                ok, value = True, compute()
            except WallError as exc:
                ok, value = False, exc
            self._items[key] = (ok, value)
        if not ok:
            raise value
        return value


_memo = _VersionMemo()


def _wall_value(scene, name, group, compute):
    # The Group object itself is part of the key: it is hashed by identity and
    # kept alive until the version changes, so a recycled id() cannot collide.
    return _memo.get(scene, (name, group), lambda: tuple(compute(group)))


def base_path(scene, group):
    return _wall_value(scene, "base_path", group, model.base_path_world)


def top_path(scene, group):
    return _wall_value(scene, "top_path", group, model.top_path_world)


def base_vertices(scene, group):
    return _wall_value(scene, "base_vertices", group, model.base_reference_vertices_world)


def top_vertices(scene, group):
    return _wall_value(scene, "top_vertices", group, model.top_reference_vertices_world)


def arc_center(scene, group):
    """World arc centre, or None for a wall that is not a single arc."""
    def compute():
        if model.wall_path_kind(group) != "arc":
            return None
        return model.arc_center_world(group)
    return _memo.get(scene, ("arc_center", group), compute)


def values(scene, group):
    """Validated parameters (read-only view: callers must not mutate them)."""
    return _memo.get(scene, ("values", group), lambda: model.read_wall(group))


def junction_aliases(scene, base=None):
    from .junctions import junction_snap_aliases
    return _memo.get(scene, ("junction_aliases", base),
                     lambda: tuple(junction_snap_aliases(scene, base)))
