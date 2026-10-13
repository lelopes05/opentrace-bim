# SPDX-License-Identifier: GPL-3.0-or-later
"""Placing openings, doors and windows on a wall, and drawing free openings.

Like Archicad: choose the tool, hover any wall and the opening slides along it
under the cursor; one click places it and the tool stays ready for the next.
No wall has to be selected first. Sizes come from presets per kind.
"""
from __future__ import annotations

import copy
import math
import uuid

from PySide6.QtGui import QVector3D
from tools.base import Tool

from .bim import new_ifc_guid
from .commands import EditWall
from .door_window_commands import CreateHostedFill
from .door_window_core import normalize_fill
from .model import WallError, path_world, read_wall, wall_opening_intervals, wall_path_kind, wall_record
from .slab_edit import _preview_lines
from .slab_model import SlabError, line_edge
from .wall_face import WallFace
from .wall_opening_edit import ANCHOR_SHIFT, execute, sheet_lines

# Starting sizes per kind, in metres: width (diameter for a circle), height, sill.
PRESETS = {
    "rect": {"width": 1.00, "height": 1.20, "sill": 0.90},
    "square": {"width": 0.60, "height": 0.60, "sill": 1.50},
    "circle": {"width": 0.60, "height": 0.60, "sill": 1.30},
    "door": {"width": 0.80, "height": 2.10, "sill": 0.00},
    "window": {"width": 1.20, "height": 1.20, "sill": 1.00},
}
KIND_NAMES = {"rect": "Abertura", "square": "Abertura quadrada", "circle": "Abertura circular",
              "door": "Porta", "window": "Janela"}
_ARC_45 = 1.0 - math.cos(math.pi / 4.0)


def _fmt(value):
    return f"{value:.2f}".replace(".", ",")


def opening_record(kind, start, size):
    """New wall opening record whose left edge sits at station ``start``."""
    width, height, sill = size["width"], size["height"], size["sill"]
    if kind == "circle":
        r = width / 2.0
        cs, cz = start + r, sill + r
        h = -r * _ARC_45  # negative: bulge outward on a counter-clockwise ring
        return {"id": uuid.uuid4().hex, "kind": "polygon",
                "polygon": [[cs, cz - r], [cs + r, cz], [cs, cz + r], [cs - r, cz]],
                "edges": [{"type": "arc", "sagitta": h} for _ in range(4)],
                "source_id": None, "ifc_global_id": new_ifc_guid()}
    return {"id": uuid.uuid4().hex, "kind": "rect", "position": start + width / 2.0,
            "width": width, "height": height, "sill": sill,
            "source_id": None, "ifc_global_id": new_ifc_guid()}


def _record_outline(item):
    if item["kind"] == "polygon":
        pts = [QVector3D(s, z, 0) for s, z in item["polygon"]]
        return pts, [dict(e) for e in item["edges"]]
    s0 = item["position"] - item["width"] / 2.0
    s1 = s0 + item["width"]
    z0, z1 = item["sill"], item["sill"] + item["height"]
    pts = [QVector3D(s0, z0, 0), QVector3D(s1, z0, 0), QVector3D(s1, z1, 0), QVector3D(s0, z1, 0)]
    return pts, [line_edge() for _ in pts]


def opening_wire(face, pts, specs):
    """Both faces of an outline plus depth lines at the corners."""
    near = sheet_lines(face, _preview_lines(pts, specs), "near")
    far = sheet_lines(face, _preview_lines(pts, specs), "far")
    depth = [(face.world(p, "near"), face.world(p, "far")) for p in pts]
    return near + far + depth


def wall_under_cursor(viewport, ctx):
    pick = getattr(viewport, "pick_group", None)
    group = pick(ctx.screen.x(), ctx.screen.y()) if callable(pick) else None
    if group is None or wall_record(group) is None:
        return None
    scene = viewport.scene
    if not scene.entity_selectable(group) or not scene.entity_visible(group):
        return None
    try:
        return group if wall_path_kind(group) in ("line", "arc") else None
    except WallError:
        return None


class _OnAnyWall(Tool):
    uses_snap = True
    wireframe_color = (0.91, 0.55, 0.14, 1.0)

    def __init__(self, controller):
        self.controller = controller
        self.wall = None
        self.face = None
        self._face_key = None

    def _face_for(self, viewport, wall):
        key = (id(wall), viewport.scene.version)
        if key != self._face_key:
            self.face = WallFace(wall)
            self._face_key = key
        self.wall = wall
        return self.face

    def _sheet(self, ctx):
        snap = getattr(ctx, "snap", None)
        world = snap.point if snap is not None and getattr(snap, "point", None) is not None else ctx.world
        return self.face.sheet(world)


class PlaceWallOpeningTool(_OnAnyWall):
    """One click places an opening, door or window on the wall under the cursor."""

    name = "Colocar abertura"
    description = "Colocar abertura, porta ou janela numa parede."
    vcb_label = "Posição"

    def __init__(self, controller):
        super().__init__(controller)
        self.kind = "rect"
        self.anchor = "center"
        self.sizes = copy.deepcopy(PRESETS)
        self.item = None
        self.station = None

    def prepare(self, kind, anchor="center"):
        if kind not in PRESETS:
            raise WallError("Tipo de abertura desconhecido.")
        self.kind, self.anchor = kind, anchor
        self.item = None

    def on_activate(self, viewport):
        self.controller.message(
            f"{KIND_NAMES[self.kind]}: passe o mouse sobre uma parede e clique para colocar; "
            "digite a distância do início da parede para posicionar exato. Esc encerra.")

    def on_deactivate(self, viewport):
        self.wall = self.face = self.item = self.station = None
        self._face_key = None
        viewport.update()

    def _candidate(self, station):
        size = self.sizes[self.kind]
        start = station - ANCHOR_SHIFT[self.anchor] * size["width"]
        return opening_record(self.kind, start, size)

    def _check(self, item):
        values = read_wall(self.wall)
        values["openings"] = list(values.get("openings", [])) + [copy.deepcopy(item)]
        wall_opening_intervals(values, path_world(self.wall))
        return values

    def on_hover(self, ctx):
        wall = wall_under_cursor(ctx.viewport, ctx)
        if wall is None:
            self.item = None
        else:
            try:
                self._face_for(ctx.viewport, wall)
                self.station = self._sheet(ctx).x()
                self.item = self._candidate(self.station)
            except WallError:
                self.item = None
        ctx.viewport.update()

    def _place(self, viewport, item):
        values = self._check(item)
        if self.kind in ("door", "window"):
            size = self.sizes[self.kind]
            start = item["position"] - item["width"] / 2.0
            spec = normalize_fill({
                "id": uuid.uuid4().hex, "host_id": str(self.wall.uid), "opening_id": item["id"],
                "kind": self.kind, "anchor": self.anchor,
                "position": start + ANCHOR_SHIFT[self.anchor] * item["width"],
                "width": size["width"], "height": size["height"], "sill": size["sill"]})
            command = CreateHostedFill(viewport.scene, self.wall, spec)
        else:
            command = EditWall(viewport.scene, self.wall, values)
        execute(viewport, command)
        self.controller.message(f"{KIND_NAMES[self.kind]} colocada.")
        self.controller.select_opening(self.wall, item["id"])

    def on_click(self, ctx):
        try:
            self.on_hover(ctx)
            if self.item is None:
                raise WallError("Clique sobre uma parede paramétrica.")
            self._place(ctx.viewport, self.item)
        except (WallError, SlabError, ValueError) as exc:
            self.controller.message(str(exc), error=True)
        ctx.viewport.update()

    def on_value(self, viewport, value):
        try:
            if self.wall is None:
                raise WallError("Passe o mouse sobre a parede antes de digitar a posição.")
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise WallError("Digite a distância do início da parede.")
            self._place(viewport, self._candidate(float(value)))
            return True
        except (WallError, SlabError, ValueError) as exc:
            self.controller.message(str(exc), error=True)
            return False

    def rubber_band_lines(self):
        if self.item is None or self.face is None:
            return []
        return opening_wire(self.face, *_record_outline(self.item))

    def value_label(self):
        if self.item is None or self.face is None:
            return None
        pts, _specs = _record_outline(self.item)
        s0 = min(p.x() for p in pts)
        s1 = max(p.x() for p in pts)
        bottom = QVector3D((s0 + s1) / 2.0, min(p.y() for p in pts), 0)
        return (f"← {_fmt(s0)}   {_fmt(self.face.length - s1)} →", self.face.world(bottom))

    def on_cancel(self, viewport):
        self.controller.return_to_select()


class DrawWallOpeningTool(_OnAnyWall):
    """Free opening: click its corners on a wall face; click the first to close."""

    name = "Desenhar abertura livre"
    description = "Desenhar uma abertura poligonal na face de uma parede."
    CLOSE_PX = 10.0

    def __init__(self, controller):
        super().__init__(controller)
        self.points = []
        self.hover = None

    def on_activate(self, viewport):
        self.points, self.hover = [], None
        self.controller.message("Clique os cantos da abertura na face da parede; "
                                "clique no primeiro para fechar. Esc cancela.")

    def on_deactivate(self, viewport):
        self.points, self.hover, self.wall, self.face = [], None, None, None
        self._face_key = None
        viewport.update()

    @property
    def start_point(self):
        return self.face.world(self.points[-1]) if self.points and self.face else None

    def drag_plane(self, viewport):
        if not self.points or self.face is None:
            return None
        return self.face.tangent_plane(self.points[-1].x(), self.points[-1].y())

    def on_hover(self, ctx):
        if not self.points:
            wall = wall_under_cursor(ctx.viewport, ctx)
            if wall is None:
                self.hover = None
                ctx.viewport.update()
                return
            self._face_for(ctx.viewport, wall)
        self.hover = self._sheet(ctx)
        ctx.viewport.update()

    def _closes(self, ctx):
        if len(self.points) < 3:
            return False
        first = ctx.viewport._world_to_pixel(self.face.world(self.points[0]))
        return first is not None and math.hypot(ctx.screen.x() - first[0],
                                                ctx.screen.y() - first[1]) <= self.CLOSE_PX

    def on_click(self, ctx):
        try:
            if not self.points:
                wall = wall_under_cursor(ctx.viewport, ctx)
                if wall is None:
                    raise WallError("Comece clicando sobre a face de uma parede.")
                self._face_for(ctx.viewport, wall)
            if self._closes(ctx):
                self._commit(ctx.viewport)
            else:
                self.points.append(self._sheet(ctx))
        except (WallError, SlabError, ValueError) as exc:
            self.controller.message(str(exc), error=True)
        ctx.viewport.update()

    def _commit(self, viewport):
        item = {"id": uuid.uuid4().hex, "kind": "polygon",
                "polygon": [[p.x(), p.y()] for p in self.points],
                "edges": [{"type": "line"} for _ in self.points],
                "source_id": None, "ifc_global_id": new_ifc_guid()}
        values = read_wall(self.wall)
        values["openings"] = list(values.get("openings", [])) + [item]
        execute(viewport, EditWall(viewport.scene, self.wall, values))
        self.controller.message("Abertura livre criada.")
        wall = self.wall
        self.points, self.hover = [], None
        self.controller.select_opening(wall, item["id"])

    def rubber_band_lines(self):
        if self.face is None:
            return []
        chain = self.points + ([self.hover] if self.hover is not None else [])
        lines = list(zip(chain, chain[1:]))
        if len(chain) >= 3:
            lines.append((chain[-1], chain[0]))
        return sheet_lines(self.face, lines)

    def on_cancel(self, viewport):
        if self.points:
            self.points, self.hover = [], None
            viewport.update()
        else:
            self.controller.return_to_select()
