# SPDX-License-Identifier: GPL-3.0-or-later
"""Real but unregistered IngeTrazo meshes for basic parametric door/window.

The wall owns the cut. This module builds a *separate* leaf/frame/glass Group
and stores a link to the wall's opening; it does not mutate the host, register
UI, or invoke IFC export. Geometry is local to opening-left, wall midplane,
opening-bottom. A future placement command anchors the parent to the wall.
"""
from __future__ import annotations

import copy
import math

from PySide6.QtGui import QVector3D
from core.group import Group
from core.mesh import Mesh

from .door_window_core import normalize_fill, FillError, f01_unit_size, f01_minimum_unit


def _prism(x0, x1, y0, y1, z0, z1, *, pivot=None, angle=0.0):
    """Closed rectangular solid, optionally rotated around a hinge in plan."""
    if not (x1 > x0 and y1 > y0 and z1 > z0):
        raise FillError("Sólido de esquadria com medidas inválidas.")
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def p(x, y, z):
        if pivot is not None:
            xx, yy = x-pivot[0], y-pivot[1]
            x, y = pivot[0]+c*xx-s*yy, pivot[1]+s*xx+c*yy
        return QVector3D(x, y, z)

    corners = [
        p(x0,y0,z0), p(x1,y0,z0), p(x1,y1,z0), p(x0,y1,z0),
        p(x0,y0,z1), p(x1,y0,z1), p(x1,y1,z1), p(x0,y1,z1),
    ]
    mesh = Mesh()
    for loop in ((3,2,1,0), (4,5,6,7), (0,1,5,4),
                 (1,2,6,5), (2,3,7,6), (3,0,4,7)):
        mesh.add_face([corners[i] for i in loop])
    return mesh


def _part(name, *size, **kwargs):
    part = Group(_prism(*size, **kwargs), name=name)
    part.component = False
    return part


def _physical_f01_parts(spec, wall_thickness, wall_faces):
    """Physical F01: independent leaf, side jambs, operating/installation gaps.

    X runs across the rough cut, Y spans finished wall faces, Z is above
    the lower rough opening. The host's source station never changes here.
    """
    unit_width, unit_height = f01_unit_size(spec)
    minimum_width, _minimum_height = f01_minimum_unit(spec)
    frame = spec["frame_thickness"]
    x0 = spec["clearance_left"]
    x1 = x0 + unit_width
    z0 = spec["clearance_bottom"]
    z1 = z0 + unit_height
    trim_width = spec["trim_width"]
    trim_depth = spec["trim_thickness"]
    depth = (wall_thickness if spec["frame_depth_mode"] == "auto"
             else spec["frame_depth"])
    if depth <= 0:
        raise FillError("Profundidade do batente inválida.")
    lower_face, upper_face = wall_faces
    recess = spec["frame_recess"]
    if spec["host_face"] == "left":
        y0 = lower_face + recess
        y1 = y0 + depth
    else:
        y1 = upper_face - recess
        y0 = y1 - depth
    center_y = (y0 + y1) / 2
    leaf_thickness = spec["leaf_thickness"]
    # A manually shallow frame cannot enclose the specified physical leaf.
    if leaf_thickness >= depth:
        raise FillError("O batente deve ser mais profundo que a folha.")
    extra = (unit_width - minimum_width) / 2
    leaf_left = x0 + frame + spec["operating_gap_left"] + extra
    leaf_right = leaf_left + spec["width"]
    leaf_top = z0 + spec["height"]
    hinge = leaf_left if spec["hinge"] == "left" else leaf_right
    direction = 1 if spec["hinge"] == "left" else -1
    angle = direction * spec["swing"] * spec["model_angle"]
    pivot = (hinge, center_y)
    result = []

    def add(name, component, *bounds, **kwargs):
        part = _part(name, *bounds, **kwargs)
        part.ext = {"opentrace_component": component}
        material = spec.get("material_" + component)
        if material is not None:
            part.material = copy.deepcopy(material)
        result.append(part)
        return part

    add("Marco esquerdo", "frame", x0, x0+frame, y0, y1, z0, z1)
    add("Marco direito", "frame", x1-frame, x1, y0, y1, z0, z1)
    add("Verga do marco", "frame", x0+frame, x1-frame,
        y0, y1, z1-frame, z1)

    # Physical leaf is always EXACTLY width x height in both its 3D geometry
    # and data contract; thin independently painted front/back skins cover it.
    add("Folha de abrir", "leaf_edge", leaf_left, leaf_right,
        center_y-leaf_thickness/2, center_y+leaf_thickness/2,
        z0, leaf_top, pivot=pivot, angle=angle)
    skin = min(0.0006, leaf_thickness/8)
    for side, component, ya, yb in (
        ("A", "leaf_front", center_y-leaf_thickness/2-skin,
         center_y-leaf_thickness/2),
        ("B", "leaf_back", center_y+leaf_thickness/2,
         center_y+leaf_thickness/2+skin),
    ):
        add("Face " + side + " da folha", component,
            leaf_left, leaf_right, ya, yb, z0, leaf_top,
            pivot=pivot, angle=angle)
        if spec["leaf_variant"] == "grooved":
            # Three shallow, separately grouped face lines.
            for i in range(1, 4):
                x = leaf_left + spec["width"]*i/4
                add("Friso " + side + " " + str(i), component,
                    x-0.0015, x+0.0015,
                    ya-skin if side == "A" else yb,
                    ya if side == "A" else yb+skin,
                    z0+0.10, leaf_top-0.10, pivot=pivot, angle=angle)
        elif spec["leaf_variant"] == "panelled":
            # Two inset-looking applied raised rectangular panels, not cuts.
            border = min(0.09, spec["width"]/6, spec["height"]/8)
            for i in range(2):
                low = z0 + border + (spec["height"]-3*border)*i/2
                high = low+(spec["height"]-3*border)/2
                add("Almofada " + side + " " + str(i+1), component,
                    leaf_left+border, leaf_right-border,
                    ya-skin if side == "A" else yb,
                    ya if side == "A" else yb+skin,
                    low, high, pivot=pivot, angle=angle)

    # Alizares cover both finished faces; disabling one never affects the other.
    for side, enabled, face, material in (
        ("A", spec["trim_front_enabled"], lower_face, "trim_front"),
        ("B", spec["trim_back_enabled"], upper_face, "trim_back"),
    ):
        if not enabled:
            continue
        ya, yb = ((face-trim_depth, face) if side == "A"
                  else (face, face+trim_depth))
        add("Alizar " + side + " esquerdo", material,
            x0-trim_width, x0, ya, yb, z0, z1+trim_width)
        add("Alizar " + side + " direito", material,
            x1, x1+trim_width, ya, yb, z0, z1+trim_width)
        add("Alizar " + side + " superior", material,
            x0, x1, ya, yb, z1, z1+trim_width)
    return result


def build_fill_parts(raw, *, wall_thickness=0.10, wall_faces=None):
    """Build one opening-filling object as named parametric geometric parts.

    A door has three frame parts plus one swinging leaf. A window has a
    four-sided frame, optional mullions, and glass units. All geometry is
    real manifold host Mesh data; the fill remains separate from its wall.
    """
    spec = normalize_fill(raw)
    thickness = float(wall_thickness)
    if not math.isfinite(thickness) or thickness <= 0.002:
        raise FillError("Espessura da parede inválida.")
    if wall_faces is None:
        wall_faces = (-thickness/2, thickness/2)
    if spec["kind"] == "door" and spec.get("f01_layout") == "physical":
        return _physical_f01_parts(spec, thickness, wall_faces)
    f = spec["frame_thickness"]
    if spec["kind"] == "door":
        x0 = spec["clearance_left"]
        z0 = spec["clearance_bottom"]
        w = spec.get("unit_width", spec["width"])
        h = spec.get("unit_height", spec["height"])
    else:
        x0 = z0 = 0.0
        w, h = spec["width"], spec["height"]
    x1, z1 = x0 + w, z0 + h
    if f >= min(w, h) / 2:
        raise FillError("Marco muito grande para o vão.")
    depth = max(thickness, f)
    y0, y1 = -depth / 2, depth / 2
    parts = [
        _part("Marco esquerdo", x0, x0 + f, y0, y1, z0, z1),
        _part("Marco direito", x1 - f, x1, y0, y1, z0, z1),
        _part("Verga do marco", x0 + f, x1 - f, y0, y1, z1 - f, z1),
    ]
    if spec["kind"] == "door":
        leaf = spec["leaf_thickness"]
        if leaf >= thickness:
            raise FillError("A folha deve ser menos espessa que a parede.")
        hinge = x0 + f if spec["hinge"] == "left" else x1 - f
        sign = 1 if spec["hinge"] == "left" else -1
        rotation = sign * spec["swing"] * spec["model_angle"]
        parts.append(_part(
            "Folha de abrir", x0 + f, x1 - f, -leaf / 2, leaf / 2,
            z0, z1 - f, pivot=(hinge, 0.0), angle=rotation,
        ))
    else:
        parts.append(_part("Marco inferior", f, w-f, y0, y1, 0, f))
        panels = spec["panes"]
        panel_width = (w-2*f)/panels
        if panel_width <= 2*f:
            raise FillError("Largura insuficiente para a quantidade de folhas.")
        for i in range(1, panels):
            x = f+panel_width*i
            parts.append(_part(f"Montante {i}", x-f/2, x+f/2,
                               y0, y1, f, h-f))
        glass_thickness = spec.get("glass_thickness", min(.006, thickness/3))
        if glass_thickness >= thickness:
            raise FillError("Vidro é mais espesso que a parede.")
        for i in range(panels):
            a = f+panel_width*i + (f/2 if i else 0)
            b = f+panel_width*(i+1) - (f/2 if i+1 < panels else 0)
            parts.append(_part(f"Vidro {i+1}", a, b,
                               -glass_thickness/2, glass_thickness/2, f, h-f))
    if spec["kind"] == "window":
        frame_material = spec.get("material_window_frame")
        glass_material = spec.get("material_window_glass")
        for part in parts:
            material = (glass_material if part.name.startswith("Vidro ")
                        else frame_material)
            if material is not None:
                part.material = copy.deepcopy(material)
    return parts


def make_fill_group(raw, *, wall_thickness=0.10, wall_faces=None):
    """A free, unplaced fill assembly ready for hosted placement.

    No global ID is generated here: the caller chooses persistent identifiers
    before build and stores the same fill ID in the wall opening source_id.
    """
    spec = normalize_fill(raw)
    group = Group(name=spec["name"])
    group.adopt(build_fill_parts(
        spec, wall_thickness=wall_thickness, wall_faces=wall_faces))
    group.component = False
    group.ext = {
        "arquitetura_parametrica": {
            "schema": spec["schema"],
            "kind": spec["kind"],
            "host_id": spec["host_id"],
            "opening_id": spec["opening_id"],
            "source_id": spec["id"],
            "params": copy.deepcopy(spec),
        }
    }
    group.ifc = {"class": "IfcDoor" if spec["kind"] == "door"
                 else "IfcWindow", "name": spec["name"],
                 "overall_width": spec["width"],
                 "overall_height": spec["height"]}
    if spec["kind"] == "door":
        from .door_window_core import wallhole_size
        group.ifc["overall_width"], group.ifc["overall_height"] = wallhole_size(spec)
        group.ifc["predefined_type"] = "DOOR"
    if spec.get("ifc_global_id"):
        group.ifc["global_id"] = spec["ifc_global_id"]
    return group


def place_fill_on_wall(raw, wall_group):
    """Create an uninserted fill object aligned with an existing hosted void.

    Call only after an opening request with the same source_id was committed
    to the wall through EditWall. This does not touch the wall or scene.
    Real hosted walls supply a world-space reference path and local elevation.
    """
    from .door_window_core import station_span, wallhole_span, wallhole_size
    from .model import (
        WallError, _path_cumulative, _point_on_path_distance, path_world,
        profile_at_fraction, read_wall, wall_offsets,
    )
    from PySide6.QtGui import QMatrix4x4

    spec = normalize_fill(raw)
    if getattr(wall_group, "uid", None) != spec["host_id"]:
        raise FillError("O ID do hospedeiro não corresponde à parede escolhida.")
    try:
        values = read_wall(wall_group)
    except WallError as exc:
        raise FillError(f"Parede de destino inválida: {exc}") from exc
    opening = next((item for item in values["openings"]
                    if item.get("id") == spec["opening_id"]), None)
    if opening is None or opening.get("source_id") != spec["id"]:
        raise FillError("O vão não está associado a esta porta ou janela.")
    if opening.get("kind") != "rect":
        raise FillError("O objeto paramétrico básico exige vão retangular.")
    from .door_window_core import center_station
    if spec["kind"] == "door":
        left, right = wallhole_span(spec)
        expected_width, expected_height = wallhole_size(spec)
        expected_center = (left + right) / 2
    else:
        left, right = station_span(spec)
        expected_width, expected_height = spec["width"], spec["height"]
        expected_center = center_station(spec)
    if (abs(opening["width"] - expected_width) > 1.0e-5
            or abs(opening["height"] - expected_height) > 1.0e-5
            or abs(opening["sill"] - spec["sill"]) > 1.0e-5
            or abs(opening["position"] - expected_center) > 1.0e-5):
        raise FillError("Posição, peitoril e dimensões da esquadria devem acompanhar o vão.")

    points, cumulative = _path_cumulative(path_world(wall_group))
    L = cumulative[-1]
    if left < .02 or right > L-.02:
        raise FillError("A esquadria está fora dos limites de ancoragem da parede.")
    # For curved walls, the origin is the left station and rotation follows
    # the local chord: the leaf itself remains straight and parametrically
    # linked to the host's reference station.
    point = _point_on_path_distance(points, cumulative, left)
    center = _point_on_path_distance(points, cumulative, (left+right)/2)
    end = _point_on_path_distance(points, cumulative, right)
    tangent = end-point
    tangent.setZ(0)
    if tangent.length() < 1.0e-8:
        raise FillError("Trajetória da parede degenerada na região do vão.")
    tangent.normalize()
    normal = QVector3D(-tangent.y(), tangent.x(), 0)
    lo, hi = wall_offsets(values)
    offset = (lo + hi) / 2
    # Use the overall finished faces, including every composite finish layer.
    finished_depth = hi - lo
    b, _t, _xy = profile_at_fraction(values, left/L)
    assembly = make_fill_group(
        spec, wall_thickness=finished_depth,
        wall_faces=(lo-offset, hi-offset))
    matrix = QMatrix4x4()
    matrix.translate(point.x()+normal.x()*offset,
                     point.y()+normal.y()*offset,
                     point.z()+b+spec["sill"])
    matrix.rotate(math.degrees(math.atan2(tangent.y(), tangent.x())),
                  0, 0, 1)
    assembly.xform = matrix
    return assembly
