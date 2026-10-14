# SPDX-License-Identifier: GPL-3.0-or-later
"""Editing wall openings with the slab opening tools, on the wall's face.

Every slab opening tool works on a closed outline in a horizontal plane. A wall
opening is the same kind of outline on the wall's face sheet (see
:mod:`wall_face`): station × height. The tools below are the slab tools with
only their data access swapped — where the outline comes from, how the cursor
lands on the sheet, how the preview is drawn and how the result is stored —
so inserting, moving and merging vertices, stretching, curving, chamfering,
rounding and offsetting behave exactly as they do on a slab.

Rectangular openings stay parametric rectangles (position, width, sill,
height) as long as an edit keeps them rectangular. A free opening becomes a
polygon when an edit breaks the rectangle; a door or window refuses that edit.
"""
from __future__ import annotations

import copy
import math

from PySide6.QtCore import QTimer
from PySide6.QtGui import QVector3D
from tools.base import AxisMagnet, Tool

from .commands import EditWall
from .door_window_commands import EditHostedFill, _fill_record
from .door_window_core import FillError, normalize_fill
from .model import WallError, path_world, read_wall, wall_opening_intervals
from .slab_edit import _preview_lines
from .slab_model import SlabError, line_edge, normalize_edge_specs, sample_boundary
from .step_guide import show_step, step_text
from .slab_opening_edit import (
    _OpeningEditBase, ChamferOpeningVertexTool, CurveOpeningEdgeTool, FilletOpeningVertexTool,
    InsertOpeningVertexTool, MoveOpeningVertexTool, OffsetOpeningTool,
    StretchOpeningEdgeTool,
)
from .wall_face import WallFace

ANCHOR_SHIFT = {"left": 0.0, "center": 0.5, "right": 1.0}


# -- the opening as an outline on the face sheet ------------------------------

def find_opening(values, opening_id):
    for item in values.get("openings", ()):
        if str(item.get("id")) == str(opening_id):
            return item
    raise SlabError("A abertura não está mais disponível.")


def linked_fill(scene, wall, item):
    """The door/window Group filling this opening, if any."""
    if not item.get("source_id"):
        return None
    for group in getattr(scene, "groups", ()):
        rec = _fill_record(group)
        if (rec and rec.get("host_id") == getattr(wall, "uid", None)
                and rec.get("opening_id") == item.get("id")
                and rec.get("source_id") == item.get("source_id")):
            return group
    return None


def rect_span(wall, values, item):
    """Stations actually cut by a rectangular opening (curved walls widen it)."""
    try:
        cut = wall_opening_intervals(dict(values, openings=[item]), path_world(wall))
    except WallError:
        cut = []
    if cut and not cut[0].get("cut_clipped"):
        return float(cut[0]["s0"]), float(cut[0]["s1"])
    half = float(item["width"]) / 2.0
    return float(item["position"]) - half, float(item["position"]) + half


def outline(wall, values, item):
    """(points as QVector3D(station, height, 0), edge specs) of an opening."""
    if item.get("kind") == "polygon":
        pts = [QVector3D(float(s), float(z), 0.0) for s, z in item["polygon"]]
        return pts, normalize_edge_specs(item.get("edges"), len(pts))
    s0, s1 = rect_span(wall, values, item)
    z0 = float(item["sill"])
    z1 = z0 + float(item["height"])
    pts = [QVector3D(s0, z0, 0), QVector3D(s1, z0, 0), QVector3D(s1, z1, 0), QVector3D(s0, z1, 0)]
    return pts, [line_edge() for _ in pts]


def axis_rectangle(pts, specs):
    """(s0, s1, z0, z1) when the outline is still an upright rectangle."""
    if len(pts) != 4 or any(s.get("type") == "arc" for s in specs):
        return None
    tol = 1e-7
    for a, b in zip(pts, pts[1:] + pts[:1]):
        if abs(a.x() - b.x()) > tol and abs(a.y() - b.y()) > tol:
            return None
    xs = sorted({round(p.x(), 9) for p in pts})
    zs = sorted({round(p.y(), 9) for p in pts})
    if len(xs) != 2 or len(zs) != 2:
        return None
    return xs[0], xs[1], zs[0], zs[1]


def store_outline(scene, wall, opening_id, pts, specs):
    """The history command that gives this opening the outline (pts, specs)."""
    values = read_wall(wall)
    ops = copy.deepcopy(values.get("openings", []))
    item = next(o for o in ops if str(o.get("id")) == str(opening_id))
    fill = linked_fill(scene, wall, item)
    rect = axis_rectangle(pts, specs)
    if item.get("kind") != "polygon" and rect is not None:
        s0, s1, z0, z1 = rect
        old0, old1 = rect_span(wall, values, item)
        # Width is the clear width; on a curved wall the cut span is wider.
        # Scale it with the span so the clear width follows the edit.
        scale = (s1 - s0) / (old1 - old0) if old1 - old0 > 1e-9 else 1.0
        width = float(item["width"]) * scale
        if fill is not None:
            spec = normalize_fill(_fill_record(fill)["params"])
            # The rectangle editor operates on the ROUGH opening; the
            # linked F01 stores the physical leaf dimensions separately.
            # Apply the change of cut size to the nominal leaf, never copy
            # the entire cut width/height into the leaf record.
            changes = {
                "width": spec["width"] + width - float(item["width"]),
                "height": spec["height"] + (z1-z0) - float(item["height"]),
                "sill": z0,
                "position": s0 + ANCHOR_SHIFT[spec["anchor"]] * (s1-s0),
            }
            return EditHostedFill(scene, wall, fill, changes)
        item.update(position=(s0 + s1) / 2.0, width=width, sill=z0, height=z1 - z0)
    else:
        if fill is not None:
            raise SlabError("Porta e janela mantêm o vão retangular.")
        item.pop("position", None), item.pop("width", None)
        item.pop("sill", None), item.pop("height", None)
        item["kind"] = "polygon"
        item["polygon"] = [[p.x(), p.y()] for p in pts]
        item["edges"] = [dict(s) for s in normalize_edge_specs(specs, len(pts))]
    values["openings"] = ops
    return EditWall(scene, wall, values)


def execute(viewport, command):
    viewport.history.execute(command)
    if viewport.history.last_error:
        raise SlabError(viewport.history.last_error)
    viewport.notify_scene_changed()


def sheet_lines(face, lines, side="near"):
    """Map preview line pairs from the sheet onto the wall, following its curve."""
    out = []
    for a, b in lines:
        pieces = 1
        if math.isfinite(face.step):
            pieces = max(1, int(math.ceil(abs(b.x() - a.x()) / face.step)))
        prev = face.world(a, side)
        for k in range(1, pieces + 1):
            cur = face.world(a + (b - a) * (k / pieces), side)
            out.append((prev, cur))
            prev = cur
    return out


# -- slab tools, re-homed on the wall face -----------------------------------

class _OnWallFace:
    """Mixin: swaps a slab opening tool's data access for a wall opening's."""

    wireframe_color = (0.91, 0.55, 0.14, 1.0)
    face = wall = opening_id = _plane = _start_sheet = None

    # The slab tools keep start_point in their own plane; the host reads it in
    # world space (inference guides, axis lock), so translate on the way out.
    @property
    def start_point(self):
        if self._start_sheet is None or self.face is None:
            return None
        return self.face.world(self._start_sheet)

    @start_point.setter
    def start_point(self, value):
        self._start_sheet = None if value is None else QVector3D(value)

    def arm(self, wall, token, anchor):
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            raise SlabError("Selecione novamente uma aresta ou vértice da abertura.")
        try:
            self.face = WallFace(wall)
        except WallError as exc:
            raise SlabError(str(exc)) from exc
        self.wall = wall
        self.opening_id = token[0]
        # The slab tools read these two names; keep them meaningful.
        self.slab, self.opening_index = wall, 0
        self.index = int(token[1])
        sheet_anchor = self.face.sheet(anchor)
        self._plane = self.face.tangent_plane(sheet_anchor.x(), sheet_anchor.y())
        super().arm(wall, (0, self.index), sheet_anchor)

    def reset(self):
        super().reset()
        self.face = None
        self.wall = None
        self.opening_id = None
        self._plane = None

    def drag_plane(self, viewport):
        return getattr(self, "_plane", None)

    def point(self, ctx):
        snap = getattr(ctx, "snap", None)
        world = snap.point if snap is not None and getattr(snap, "point", None) is not None else ctx.world
        return self.face.sheet(world)

    def _data(self):
        if getattr(self, "wall", None) is None:
            raise SlabError("Selecione novamente a abertura.")
        try:
            values = read_wall(self.wall)
            item = find_opening(values, self.opening_id)
            pts, specs = outline(self.wall, values, item)
        except WallError as exc:
            raise SlabError(str(exc)) from exc
        if len(pts) < 3:
            raise SlabError("A abertura precisa manter pelo menos três vértices.")
        return None, 0, item, pts, specs

    def _commit(self, viewport, pts, specs, message):
        try:
            execute(viewport, store_outline(viewport.scene, self.wall, self.opening_id, pts, specs))
        except (WallError, FillError, StopIteration) as exc:
            raise SlabError(str(exc)) from exc
        self.controller.message(message)
        wall, oid = self.wall, self.opening_id
        self.reset()
        QTimer.singleShot(0, lambda: self.controller.edit_finished(wall, oid))

    def rubber_band_lines(self):
        lines = super().rubber_band_lines()
        return sheet_lines(self.face, lines) if lines and self.face is not None else []

    def value_label(self):
        label = super().value_label() if hasattr(super(), "value_label") else None
        if label and len(label) > 1 and self.face is not None:
            return (label[0], self.face.world(label[1]))
        return label


def _wall_tool(base, tool_name, text):
    return type(base.__name__.replace("Opening", "WallOpening"), (_OnWallFace, base),
                {"name": tool_name, "description": text})


class _InsertOnClickedEdge(InsertOpeningVertexTool):
    """Insert on the edge actually clicked, not only the one the radial opened on."""

    def on_click(self, ctx):
        try:
            _o, _oi, _it, pts, specs = self._data()
            p = self.point(ctx)
            sampled, owner = sample_boundary(pts, specs, with_map=True)
            n = len(sampled)
            best = None
            for k in range(n):
                a, b = sampled[k], sampled[(k + 1) % n]
                d = b - a
                den = d.x() * d.x() + d.y() * d.y()
                t = 0.0 if den <= 1e-12 else max(0.0, min(1.0, ((p.x() - a.x()) * d.x()
                                                               + (p.y() - a.y()) * d.y()) / den))
                dist = math.hypot(p.x() - a.x() - d.x() * t, p.y() - a.y() - d.y() * t)
                if best is None or dist < best[0]:
                    best = (dist, owner[k])
            if best is not None:
                self.index = best[1]
        except SlabError:
            pass  # the base click reports the same error to the user
        super().on_click(ctx)


InsertWallOpeningVertexTool = _wall_tool(
    _InsertOnClickedEdge, "Inserir vértice no vão", "Inserir um vértice na aresta clicada do vão.")
StretchWallOpeningEdgeTool = _wall_tool(
    StretchOpeningEdgeTool, "Puxar aresta do vão", "Puxar uma aresta do vão na face da parede.")
MoveWallOpeningVertexTool = _wall_tool(
    MoveOpeningVertexTool, "Mover vértice do vão", "Mover ou unir um vértice do vão.")
CurveWallOpeningEdgeTool = _wall_tool(
    CurveOpeningEdgeTool, "Curvar aresta do vão", "Curvar uma aresta do vão mantendo os extremos.")
ChamferWallOpeningVertexTool = _wall_tool(
    ChamferOpeningVertexTool, "Chanfrar vértice do vão", "Chanfrar um canto do vão.")
FilletWallOpeningVertexTool = _wall_tool(
    FilletOpeningVertexTool, "Arredondar vértice do vão", "Arredondar um canto do vão.")
OffsetWallOpeningTool = _wall_tool(
    OffsetOpeningTool, "Offset do vão", "Aumentar ou reduzir o vão inteiro por igual.")


class _PushEdge(_OpeningEditBase):
    """Move one edge parallel to itself; a rectangle stays a rectangle."""

    def arm(self, slab, token, anchor):
        super().arm(slab, token, anchor)
        _o, _oi, _it, self.original, self.specs = self._data()
        n = len(self.original)
        a, b = self.original[self.index % n], self.original[(self.index + 1) % n]
        d = b - a
        length = math.hypot(d.x(), d.y())
        if length < 1e-6:
            raise SlabError("A aresta do vão é curta demais.")
        self.normal = QVector3D(-d.y() / length, d.x() / length, 0)

    def reset(self):
        super().reset()
        self.original = self.specs = self.normal = None

    def _candidate(self, p):
        shift = self.normal * QVector3D.dotProduct(p - self.anchor, self.normal)
        n = len(self.original)
        pts = [QVector3D(v) for v in self.original]
        for k in (self.index % n, (self.index + 1) % n):
            pts[k] = pts[k] + shift
        return pts, [dict(s) for s in self.specs]

    def on_hover(self, ctx):
        self.hover = self.point(ctx)
        ctx.viewport.update()

    def on_click(self, ctx):
        try:
            self._commit(ctx.viewport, *self._candidate(self.point(ctx)), "Aresta do vão movida.")
        except SlabError as exc:
            self.controller.message(str(exc), error=True)
        ctx.viewport.update()

    def rubber_band_lines(self):
        return [] if self.hover is None else _preview_lines(*self._candidate(self.hover))


PushWallOpeningEdgeTool = _wall_tool(
    _PushEdge, "Mover aresta do vão", "Mover uma aresta do vão; largura ou altura mudam.")


class MoveWallOpeningTool(AxisMagnet, Tool):
    """Slide the whole opening along its wall and up or down; one click confirms."""

    name = "Mover vão"
    description = "Mover o vão ao longo da parede e na altura."
    uses_snap = True
    wireframe_color = (0.91, 0.55, 0.14, 1.0)
    vcb_label = "Deslocamento"

    def __init__(self, controller):
        self.controller = controller
        self.step_id = "wall_opening.edit.move"
        self.reset()

    def reset(self):
        self.wall = self.face = self.opening_id = None
        self.origin = self.hover = self.start_point = None
        self.points = self.specs = None
        self._plane = None

    def arm(self, wall, token, anchor):
        try:
            self.face = WallFace(wall)
            values = read_wall(wall)
            self.opening_id = token[0] if isinstance(token, (tuple, list)) else token
            self.points, self.specs = outline(wall, values, find_opening(values, self.opening_id))
        except WallError as exc:
            raise SlabError(str(exc)) from exc
        self.wall = wall
        self.origin = self.face.sheet(anchor)
        self.start_point = QVector3D(anchor)
        self._plane = self.face.tangent_plane(self.origin.x(), self.origin.y())

    def drag_plane(self, viewport):
        return self._plane

    def on_activate(self, viewport):
        show_step(self, viewport, "wall_opening.edit.move")

    def on_deactivate(self, viewport):
        self.reset()
        self.controller.clear_sticky()
        self.controller.app.window.statusBar().clearMessage()
        viewport.update()

    def status_clause(self):
        # Kept for hosts newer than IngeTrazo 0.5.8.
        return step_text(self.step_id)

    def _delta(self, sheet_point):
        return QVector3D(sheet_point.x() - self.origin.x(), sheet_point.y() - self.origin.y(), 0)

    def _sheet(self, ctx):
        snap = getattr(ctx, "snap", None)
        world = snap.point if snap is not None and getattr(snap, "point", None) is not None else ctx.world
        return self.face.sheet(world)

    def _moved(self, delta):
        return [p + delta for p in self.points], [dict(s) for s in self.specs]

    def on_hover(self, ctx):
        if self.face is not None:
            self.hover = self._sheet(ctx)
            ctx.viewport.update()

    def _apply(self, viewport, delta):
        execute(viewport, store_outline(viewport.scene, self.wall, self.opening_id,
                                        *self._moved(delta)))
        self.controller.message("Vão movido.")
        wall, oid = self.wall, self.opening_id
        self.reset()
        QTimer.singleShot(0, lambda: self.controller.edit_finished(wall, oid))

    def on_click(self, ctx):
        try:
            self._apply(ctx.viewport, self._delta(self._sheet(ctx)))
        except (SlabError, WallError, FillError, StopIteration) as exc:
            self.controller.message(str(exc), error=True)
        ctx.viewport.update()

    def on_value(self, viewport, value):
        """Typed distance along the wall, in the direction the cursor went."""
        try:
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise SlabError("Digite uma distância.")
            sign = -1.0 if self.hover is not None and self.hover.x() < self.origin.x() else 1.0
            self._apply(viewport, QVector3D(sign * abs(float(value)), 0, 0))
            return True
        except (SlabError, WallError, FillError, StopIteration) as exc:
            self.controller.message(str(exc), error=True)
            return False

    def on_cancel(self, viewport):
        wall, oid = self.wall, self.opening_id
        self.reset()
        self.controller.edit_finished(wall, oid)
        viewport.update()

    def rubber_band_lines(self):
        if self.hover is None or self.points is None:
            return []
        return sheet_lines(self.face, _preview_lines(*self._moved(self._delta(self.hover))))
