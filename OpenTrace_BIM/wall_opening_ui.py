# SPDX-License-Identifier: GPL-3.0-or-later
"""Wall openings in the viewport: select with one click, edit by points and edges.

The flow mirrors the slab opening editor. One click on an opening (its outline
or the empty hole) selects it and shows its corners as dots; no wall has to be
selected first. A click on a corner, on an edge line or inside the selected
opening opens the radial with the actions that fit (an edge action anchors at
the middle of the edge, where nothing is drawn); the chosen tool previews
under the mouse and one click confirms. The opening stays selected afterwards,
so the next edit is one click away.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QPen
from PySide6.QtWidgets import QMenu, QToolButton

from . import wall_cache
from .commands import EditWall
from .door_window_commands import DeleteHostedOpening
from .host import activate_select, activate_tool, host_tool, register_tool
from .i18n import t
from .icons import set_symbol_icon
from .model import WallError, read_wall, wall_record
from .overlay_safety import visible_pixel
from .palette import RadialPalette
from .slab_model import SlabError, edge_point, sample_boundary
from .wall_face import WallFace
from .wall_opening_edit import (
    ChamferWallOpeningVertexTool, CurveWallOpeningEdgeTool, FilletWallOpeningVertexTool,
    InsertWallOpeningVertexTool, MoveWallOpeningTool, MoveWallOpeningVertexTool,
    OffsetWallOpeningTool, PushWallOpeningEdgeTool, StretchWallOpeningEdgeTool,
    execute, find_opening, linked_fill, outline, store_outline,
)
from .wall_opening_place import PlaceWallOpeningTool, WallOpeningTool

KEY = "opentrace_wall_opening_"
OPENING_TOOL_KEY = "opentrace_wall_opening_tool"
DOOR_TOOL_KEY = "opentrace_wall_door_tool"
WINDOW_TOOL_KEY = "opentrace_wall_window_tool"
ORANGE = QColor("#e78b24")
INACTIVE = QColor("#6997b0")

# action -> (symbol, tooltip, tool class or None, parts it applies to, also on doors/windows)
ACTIONS = (
    ("push_edge", "⇕", "Mover esta aresta (muda largura ou altura)", PushWallOpeningEdgeTool, ("edge",), True),
    ("stretch_edge", "⇱", "Extrudar esta aresta (acrescenta dois vértices)", StretchWallOpeningEdgeTool, ("edge",), False),
    ("insert_vertex", "＋", "Inserir vértice nesta aresta", InsertWallOpeningVertexTool, ("edge",), False),
    ("curve_edge", "⌒", "Curvar esta aresta mantendo os extremos", CurveWallOpeningEdgeTool, ("edge",), False),
    ("move_vertex", "✥", "Mover este vértice", MoveWallOpeningVertexTool, ("vertex",), False),
    ("chamfer", "◩", "Chanfrar este canto", ChamferWallOpeningVertexTool, ("vertex",), False),
    ("fillet", "◜", "Arredondar este canto", FilletWallOpeningVertexTool, ("vertex",), False),
    ("delete_vertex", "⌫", "Excluir este vértice", None, ("vertex",), False),
    ("offset", "⤢", "Aumentar ou reduzir o vão por igual", OffsetWallOpeningTool, ("edge", "body"), True),
    ("move", "↔", "Mover o vão pela parede", MoveWallOpeningTool, ("edge", "vertex", "body"), True),
    ("delete", "⊘", "Excluir o vão", None, ("edge", "vertex", "body"), True),
)


def _ring(face, sampled, owner, side):
    """World ring of a sampled sheet outline and the logical edge of each piece."""
    ring, ring_owner = [], []
    n = len(sampled)
    for k in range(n):
        a, b = sampled[k], sampled[(k + 1) % n]
        pieces = 1
        if math.isfinite(face.step):
            pieces = max(1, int(math.ceil(abs(b.x() - a.x()) / face.step)))
        for i in range(pieces):
            ring.append(face.world(a + (b - a) * (i / pieces), side))
            ring_owner.append(owner[k])
    return ring, ring_owner


def _shapes(scene, wall):
    """Per opening: logical outline on the sheet and its world rings, per version."""
    def compute():
        values = wall_cache.values(scene, wall)
        face = WallFace(wall, values)
        out = []
        for item in values.get("openings", ()):
            try:
                pts, specs = outline(wall, values, item)
                sampled, owner = sample_boundary(pts, specs, with_map=True)
            except (SlabError, WallError, ValueError, KeyError):
                continue
            ring, ring_owner = _ring(face, sampled, owner, "near")
            far, _far_owner = _ring(face, sampled, owner, "far")
            out.append({
                "id": str(item["id"]), "fill": bool(item.get("source_id")),
                "pts": pts, "specs": specs, "sampled": sampled, "owner": owner,
                "near": ring, "far": far, "ring_owner": ring_owner,
                "vertices": [face.world(p) for p in pts],
                "mids": [face.world(edge_point(pts[i], pts[(i + 1) % len(pts)], specs[i], 0.5))
                         for i in range(len(pts))],
                "depth": [(face.world(p, "near"), face.world(p, "far")) for p in pts],
            })
        return out
    return wall_cache.memo(scene, ("opening_shapes", wall), compute)


def _segment_distance(px, py, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    den = dx * dx + dy * dy
    u = 0.0 if den <= 1e-12 else max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / den))
    return math.hypot(px - a[0] - u * dx, py - a[1] - u * dy)


def _inside(px, py, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


class WallOpeningEditor(QObject):
    def __init__(self, app, wall_controller):
        super().__init__(app.window)
        self.app = app
        self.walls = wall_controller
        self.active = None            # (wall, opening_id)
        self._radial_target = None    # (wall, opening_id, part, index, world_anchor)
        self.opening_tool = WallOpeningTool(self)
        self.door_tool = PlaceWallOpeningTool(self, "door")
        self.window_tool = PlaceWallOpeningTool(self, "window")
        self.tool_actions = tuple(
            self._make_tool_action(key, tool, title, tip) for key, tool, title, tip in (
                (OPENING_TOOL_KEY, self.opening_tool, "Abertura",
                 "Abertura na parede: passe sobre a parede e clique."),
                (DOOR_TOOL_KEY, self.door_tool, "Porta",
                 "Porta: passe sobre a parede e clique."),
                (WINDOW_TOOL_KEY, self.window_tool, "Janela",
                 "Janela: passe sobre a parede e clique.")))
        self._make_menu()
        self.tools = {}
        for action, _sym, _tip, cls, _parts, _fill in ACTIONS:
            if cls is not None:
                self.tools[action] = cls(self)
                register_tool(app, self.tools[action], key=KEY + action)
        self._make_radial()
        app.add_pickable(self._pick, self._on_pick, self._delete_pick)
        app.add_overlay(self._draw)
        app.viewport.installEventFilter(self)

    # -- what the rest of the plugin calls -----------------------------------
    def _make_tool_action(self, key, tool, title, tip):
        action = QAction(t(title), self.app.window)
        action.setCheckable(True)
        action.setToolTip(t(tip))
        action.triggered.connect(lambda _checked=False, k=key: self._start(k))
        register_tool(self.app, tool, action, key=key)
        return action

    def _make_menu(self):
        """The three tools live in "Ferramentas arquitetônicas", submenu "Vãos"."""
        menu = self.walls.arch_menu
        if menu is None:
            return
        sub = QMenu(t("Vãos"), menu)
        for action in self.tool_actions:
            sub.addAction(action)
        menu.insertMenu(self.walls.arch_menu_end, sub)

    def _start(self, key):
        self.walls.hide_path_palette()
        activate_tool(self.app, key)
        self.app.viewport.setFocus()

    def message(self, text, error=False):
        self.walls.message(text, error=error)

    def return_to_select(self):
        activate_select(self.app)
        self.app.viewport.setFocus()
        self.app.viewport.update()

    def select_opening(self, wall, opening_id):
        self.active = (wall, str(opening_id))
        self.walls._active_opening_wall = wall
        self.walls._active_opening_id = str(opening_id)
        self.walls._state_key = None
        self.walls.schedule_refresh()
        self.app.viewport.update()

    def edit_finished(self, wall, opening_id):
        """After an edit (or its cancel): stay on the same opening, ready again."""
        if wall is not None and wall in self.app.scene.groups:
            self.select_opening(wall, opening_id)
        self.return_to_select()

    def delete_opening(self, wall, opening_id):
        try:
            values = read_wall(wall)
            item = find_opening(values, opening_id)
            if linked_fill(self.app.scene, wall, item) is not None:
                command = DeleteHostedOpening(self.app.scene, wall, item["id"])
            else:
                values["openings"] = [o for o in values["openings"] if o is not item]
                command = EditWall(self.app.scene, wall, values)
            execute(self.app.viewport, command)
        except (WallError, SlabError, ValueError) as exc:
            self.message(str(exc), error=True)
            return
        self.active = None
        self.walls._active_opening_id = None
        self.walls._state_key = None
        self.walls.schedule_refresh()
        self.message("Vão excluído.")

    # -- picking -------------------------------------------------------------
    def _candidates(self, scene):
        editing = scene.edit_group
        if editing is not None:
            return [editing] if wall_record(editing) is not None else []
        return [g for g in scene.groups
                if wall_record(g) is not None and (wall_record(g) or {}).get("openings")
                and scene.entity_visible(g) and scene.entity_selectable(g)]

    def _screen(self, viewport, points):
        return [viewport._world_to_pixel(p) for p in points]

    def _hit_opening(self, viewport, wall, shape, px, py, threshold):
        """('vertex'|'edge'|'body', logical index or None, distance) or None."""
        best = None
        for ring in (shape["near"], shape["far"]):
            screen = self._screen(viewport, ring)
            n = len(screen)
            for k in range(n):
                a, b = screen[k], screen[(k + 1) % n]
                if a is None or b is None:
                    continue
                d = _segment_distance(px, py, a, b)
                if d <= threshold and (best is None or d < best[1]):
                    best = (shape["ring_owner"][k], d)
        if best is not None:
            return ("edge", best[0], best[1])
        if not shape["fill"]:
            for ring in (shape["near"], shape["far"]):
                screen = self._screen(viewport, ring)
                if None not in screen and _inside(px, py, screen):
                    return ("body", None, threshold)
        return None

    def _pick(self, viewport, px, py):
        threshold = max(7.0, float(getattr(viewport, "snap_threshold_px", 10.0)))
        best = None
        scene = viewport.scene
        for wall in self._candidates(scene):
            try:
                shapes = _shapes(scene, wall)
            except WallError:
                continue
            for shape in shapes:
                hit = self._hit_opening(viewport, wall, shape, px, py, threshold)
                if hit is not None and (best is None or hit[2] < best[0]):
                    best = (hit[2], str(wall.uid), shape["id"])
        return None if best is None else (best[1], best[2])

    def _wall_by_uid(self, uid):
        return next((w for w in self.app.scene.groups
                     if getattr(w, "uid", None) == uid and wall_record(w) is not None), None)

    def _on_pick(self, identity):
        if identity is None:
            # Esc or a click elsewhere. A pick dropped because the document
            # changed never reaches here, so edits keep the opening selected.
            QTimer.singleShot(0, self._release_if_unpicked)
            return
        wall = self._wall_by_uid(identity[0])
        if wall is None:
            return
        if self.app.scene.edit_group is wall:
            self.app.viewport.end_group_edit()
        self.select_opening(wall, identity[1])

    def _release_if_unpicked(self):
        if getattr(self.app.viewport, "extension_pick", None) is None:
            self.active = None
            self.walls._active_opening_id = None
            self.walls._state_key = None
            self.walls.schedule_refresh()
            self.app.viewport.update()

    def _delete_pick(self, identity):
        wall = self._wall_by_uid(identity[0]) if identity else None
        if wall is not None:
            self.delete_opening(wall, identity[1])

    def _active_shape(self):
        if self.active is None:
            return None, None
        wall, oid = self.active
        if wall not in self.app.scene.groups:
            self.active = None
            return None, None
        try:
            shape = next((s for s in _shapes(self.app.scene, wall) if s["id"] == oid), None)
        except WallError:
            shape = None
        return wall, shape

    def _hit_active(self, px, py):
        """Part of the selected opening under the cursor, for the radial."""
        wall, shape = self._active_shape()
        if shape is None:
            return None
        vp = self.app.viewport
        threshold = max(8.0, float(getattr(vp, "snap_threshold_px", 10.0)))
        for i, p in enumerate(shape["vertices"]):
            q = vp._world_to_pixel(p)
            if q is not None and math.hypot(px - q[0], py - q[1]) <= threshold:
                return wall, shape, "vertex", i, p
        hit = self._hit_opening(vp, wall, shape, px, py, threshold)
        if hit is None:
            return None
        kind, index, _d = hit
        if kind == "edge":
            return wall, shape, "edge", index, shape["mids"][index]
        sheet_centre = sum((p for p in shape["pts"][1:]), shape["pts"][0]) / len(shape["pts"])
        return wall, shape, "body", None, WallFace(wall).world(sheet_centre)

    def eventFilter(self, obj, event):
        if obj is not self.app.viewport:
            return False
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if (self.active is not None and event.modifiers() == Qt.NoModifier
                    and self.app.viewport.active_tool is host_tool(self.app, "select")):
                self.delete_opening(*self.active)
                return True
            return False
        if event.type() != QEvent.MouseButtonPress or event.button() != Qt.LeftButton:
            return False
        if self.radial.isVisible():
            self.radial.hide()
        if (event.modifiers() != Qt.NoModifier
                or self.app.viewport.active_tool is not host_tool(self.app, "select")):
            return False
        hit = self._hit_active(event.position().x(), event.position().y())
        if hit is None:
            return False
        wall, shape, part, index, anchor = hit
        self._show_radial(event.globalPosition().toPoint(), wall, shape, part, index, anchor)
        return True

    # -- radial ----------------------------------------------------------------
    def _make_radial(self):
        self.radial = RadialPalette(self.app.window, popup=False, role="edit")
        self.radial.setObjectName("opentrace_wall_opening_radial")
        self.buttons = {}
        for action, symbol, tip, _cls, _parts, _fill in ACTIONS:
            button = QToolButton(self.radial)
            set_symbol_icon(button, symbol)
            button.setToolTip(t(tip))
            button.setAutoRaise(True)
            button.setFixedSize(34, 34)
            button.clicked.connect(lambda _c=False, a=action: self._run(a))
            self.radial.row.addWidget(button)
            self.buttons[action] = button
        self.radial.hide()

    def _show_radial(self, global_pos, wall, shape, part, index, anchor):
        self._radial_target = (wall, shape["id"], part, index, anchor)
        for action, _sym, _tip, _cls, parts, on_fill in ACTIONS:
            shown = part in parts and (on_fill or not shape["fill"])
            if action == "delete_vertex":
                shown = shown and len(shape["pts"]) > 3
            self.buttons[action].setVisible(shown)
        self.radial.show_at(global_pos)

    def _run(self, action):
        self.radial.hide()
        if self._radial_target is None:
            return
        wall, oid, part, index, anchor = self._radial_target
        if action == "delete":
            self.delete_opening(wall, oid)
            return
        if action == "delete_vertex":
            self._delete_vertex(wall, oid, index)
            return
        try:
            self.tools[action].arm(wall, (oid, index or 0), anchor)
        except (SlabError, WallError) as exc:
            self.message(str(exc), error=True)
            return
        activate_tool(self.app, KEY + action)
        self.app.viewport.setFocus()

    def _delete_vertex(self, wall, oid, index):
        try:
            values = read_wall(wall)
            pts, specs = outline(wall, values, find_opening(values, oid))
            n = len(pts)
            if n <= 3:
                raise SlabError("O vão precisa manter pelo menos três vértices.")
            keep = [k for k in range(n) if k != index % n]
            new_specs = [dict(specs[a]) if keep[(i + 1) % len(keep)] == (a + 1) % n
                         else {"type": "line"} for i, a in enumerate(keep)]
            execute(self.app.viewport,
                    store_outline(self.app.scene, wall, oid, [pts[k] for k in keep], new_specs))
            self.message("Vértice do vão excluído.")
        except (SlabError, WallError, ValueError, StopIteration) as exc:
            self.message(str(exc), error=True)
        self.select_opening(wall, oid)

    # -- drawing ----------------------------------------------------------------
    def _draw(self, viewport, painter):
        wall, active = self._active_shape()
        if active is None:
            return
        try:
            shapes = _shapes(viewport.scene, wall)
        except WallError:
            return

        def polyline(points, closed=True):
            pixels = [visible_pixel(viewport, p) for p in points]
            pairs = zip(pixels, pixels[1:] + (pixels[:1] if closed else []))
            for a, b in pairs:
                if a is not None and b is not None:
                    painter.drawLine(QPointF(*a), QPointF(*b))

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(INACTIVE, 1.0, Qt.DashLine))
        for shape in shapes:
            if shape is not active:
                polyline(shape["near"])
        painter.setPen(QPen(ORANGE, 2.0))
        polyline(active["near"])
        polyline(active["far"])
        for a, b in active["depth"]:
            polyline([a, b], closed=False)
        painter.setPen(QPen(ORANGE, 1.5))
        painter.setBrush(QColor("white"))
        for p in active["vertices"]:
            q = visible_pixel(viewport, p)
            if q is not None:
                painter.drawEllipse(QRectF(q[0] - 4.5, q[1] - 4.5, 9, 9))
