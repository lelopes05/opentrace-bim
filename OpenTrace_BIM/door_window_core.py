# SPDX-License-Identifier: GPL-3.0-or-later
"""Host-independent parameter contracts for doors and windows (stage 02).

A fill is a SEPARATE parametric object, identified by a stable id and linked
to a wall opening by opening_id/source_id. No Qt, scene writes, meshes, IFC
exports, UI hooks or release side effects occur when this module is imported.

All distances are metres. The station is the location of the chosen anchor
(left, centre, right) on the wall reference line; changing width keeps this
anchor fixed. One swing switch flips the *direction*, not the host opening.
"""
from __future__ import annotations

import math
import copy

SCHEMA = 1  # Window schema; window records remain unchanged.
SCHEMA_DOOR = 2
DOOR_FAMILIES = {
    "swing_single": {
        "code": "F01", "name": "Abrir · 1 folha", "enabled": True,
        "clearances": {"left": 0.04, "right": 0.04, "top": 0.04, "bottom": 0.0},
    },
    "swing_double": {"code": "F02", "name": "Abrir · 2 folhas", "enabled": False},
    "sliding_surface": {"code": "F03", "name": "Correr aparente", "enabled": False},
    "sliding_pocket": {"code": "F04", "name": "Correr embutida", "enabled": False},
    "composite": {"code": "F05", "name": "Composta", "enabled": False},
    "pivot": {"code": "F06", "name": "Pivotante", "enabled": False},
    "folding": {"code": "F07", "name": "Articulada/camarão/sanfonada", "enabled": False},
    "revolving_special": {"code": "F08", "name": "Vaivém/giratória/especial", "enabled": False},
}
ANCHORS = ("left", "center", "right")
KINDS = ("door", "window")
HINGES = ("left", "right")
F01_VARIANTS = ("plain", "grooved", "panelled")
# A technical starting allowance, not a certified installation tolerance.
# The moving-leaf gap is independent of the 40 mm construction clearances.
F01_OPERATING_GAP = 0.003



class FillError(ValueError):
    pass


def _number(value, label, *, positive=False, minimum=None):
    if isinstance(value, bool):
        raise FillError(f"{label}: número inválido.")
    try:
        result = float(value.replace(",", ".").strip() if isinstance(value, str) else value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise FillError(f"{label}: número inválido.") from exc
    if not math.isfinite(result):
        raise FillError(f"{label}: número não finito.")
    if positive and result <= 0:
        raise FillError(f"{label}: medida deve ser positiva.")
    if minimum is not None and result < minimum:
        raise FillError(f"{label}: medida abaixo do mínimo.")
    return result


def migrate_door(raw):
    """Migrate a legacy hosted door without changing its cut or appearance.

    Migration is non-destructive for unknown extension metadata. The schema-1
    open_angle is replaced by independent plan/model angles.
    """
    if not isinstance(raw, dict) or str(raw.get("kind", "")).lower() != "door":
        raise FillError("Migração exige registro de porta.")
    schema = raw.get("schema", 1)
    if schema in (2, "2"):
        return copy.deepcopy(raw)
    if schema not in (1, "1", None):
        raise FillError(f"Versão de porta não suportada (schema {schema}).")
    result = copy.deepcopy(raw)
    angle = result.pop("open_angle", 90)
    result.update({
        "schema": SCHEMA_DOOR,
        "family_key": "swing_single",
        "host_mode": "hosted",
        "clearance_left": 0.0, "clearance_right": 0.0,
        "clearance_top": 0.0, "clearance_bottom": 0.0,
        "plan_angle": angle, "model_angle": angle,
    })
    # The legacy default anchor was left, unlike a new schema-2 door.
    result.setdefault("anchor", "left")
    return result


def _door_schema(raw):
    schema = raw.get("schema", 1)
    if schema in (1, "1", None):
        return migrate_door(raw)
    if schema in (2, "2"):
        return copy.deepcopy(raw)
    try:
        newer = int(schema)
    except (TypeError, ValueError, OverflowError) as exc:
        raise FillError(f"Schema de porta inválido: {schema}.") from exc
    if newer > SCHEMA_DOOR:
        raise FillError(
            f"Porta salva por versão mais nova do OpenTrace BIM (schema {newer}).")
    raise FillError(f"Versão de porta não suportada (schema {schema}).")


def normalize_fill(raw):
    """Validate a door/window object while preserving stable references."""
    if not isinstance(raw, dict):
        raise FillError("Porta ou janela precisa ser um registro.")
    kind = str(raw.get("kind", "")).lower()
    if kind not in KINDS:
        raise FillError("Tipo de esquadria inválido.")
    if kind == "door":
        raw = _door_schema(raw)
        family_key = str(raw.get("family_key", "swing_single"))
        family = DOOR_FAMILIES.get(family_key)
        if family is None:
            raise FillError("Família de porta desconhecida.")
        if not family["enabled"]:
            raise FillError("Família em desenvolvimento.")
        host_mode = str(raw.get("host_mode", "hosted"))
        if host_mode not in ("hosted", "free"):
            raise FillError("Modo de hospedagem inválido.")
    uid = str(raw.get("id") or "").strip()
    host_id = str(raw.get("host_id") or "").strip()
    opening_id = str(raw.get("opening_id") or "").strip()
    if kind == "window" or (kind == "door" and host_mode == "hosted"):
        if not uid or not host_id or not opening_id:
            raise FillError("Objeto, parede e abertura precisam de IDs persistentes.")
    elif not uid or host_id or opening_id:
        raise FillError("Porta livre exige ID próprio, sem parede ou abertura.")
    anchor = str(raw.get("anchor", "center" if kind == "door" else "left")).lower()
    if anchor not in ANCHORS:
        raise FillError("Âncora inválida.")
    defaults = {"door": (0.90, 2.10, 0.0), "window": (1.20, 1.20, 0.90)}
    dw, dh, ds = defaults[kind]
    width = _number(raw.get("width", dw), "Largura", positive=True)
    height = _number(raw.get("height", dh), "Altura", positive=True)
    sill = _number(raw.get("sill", ds), "Peitoril", minimum=0.0)
    position = _number(raw.get("position"), "Posição")
    if width < 0.05 or height < 0.05 or width > 100 or height > 100:
        raise FillError("Dimensões fora dos limites de projeto.")
    frame = _number(raw.get("frame_thickness", 0.04), "Espessura do marco", positive=True)
    if frame >= min(width, height)/2:
        raise FillError("Marco muito grande para o vão.")
    out = {
        "schema": SCHEMA_DOOR if kind == "door" else SCHEMA,
        "id": uid, "kind": kind,
        "host_id": host_id, "opening_id": opening_id,
        "anchor": anchor, "position": position,
        "width": width, "height": height, "sill": sill,
        "frame_thickness": frame,
        "name": str(raw.get("name") or ("Porta" if kind == "door" else "Janela")),
    }
    if kind == "door":
        hinge = str(raw.get("hinge", "left")).lower()
        if hinge not in HINGES:
            raise FillError("Lado da dobradiça inválido.")
        swing = raw.get("swing", 1)
        if swing not in (-1, 1) or isinstance(swing, bool):
            raise FillError("Giro precisa ser +1 ou -1.")
        out.update({
            "hinge": hinge, "swing": swing,
            "leaf_thickness": _number(raw.get("leaf_thickness", 0.035),
                                      "Espessura da folha", positive=True),
            "family_key": family_key, "host_mode": host_mode,
            "plan_angle": _number(raw.get("plan_angle", 90), "Ângulo da planta"),
            "model_angle": _number(raw.get("model_angle", 0), "Ângulo do modelo"),
        })
        # Pre-recovery schema-2 instances lack f01_layout: preserve their
        # existing rough cuts and dimensions. Creation stamps physical layout.
        layout = str(raw.get("f01_layout", "legacy"))
        if layout not in ("legacy", "physical"):
            raise FillError("Modo dimensional F01 inválido.")
        if "f01_layout" in raw:
            out["f01_layout"] = layout
        if layout == "physical":
            variant = str(raw.get("leaf_variant", "plain"))
            if variant not in F01_VARIANTS:
                raise FillError("Variante F01 desconhecida.")
            out["leaf_variant"] = variant
            for axis in ("left", "right", "top"):
                out["operating_gap_" + axis] = _number(
                    raw.get("operating_gap_" + axis, F01_OPERATING_GAP),
                    "Folga operacional " + axis, minimum=0)
            mode = str(raw.get("frame_depth_mode", "auto"))
            if mode not in ("auto", "manual"):
                raise FillError("Profundidade do batente: modo inválido.")
            out["frame_depth_mode"] = mode
            if mode == "manual":
                out["frame_depth"] = _number(
                    raw.get("frame_depth", 0.10),
                    "Profundidade do batente", positive=True)
            out["host_face"] = str(raw.get("host_face", "left"))
            if out["host_face"] not in ("left", "right"):
                raise FillError("Face de referência inválida.")
            out["frame_recess"] = _number(
                raw.get("frame_recess", 0), "Recuo do batente", minimum=0)
            out["trim_front_enabled"] = bool(raw.get("trim_front_enabled", True))
            out["trim_back_enabled"] = bool(raw.get("trim_back_enabled", True))
            out["trim_width"] = _number(
                raw.get("trim_width", 0.06), "Largura do alizar", positive=True)
            out["trim_thickness"] = _number(
                raw.get("trim_thickness", 0.012),
                "Espessura do alizar", positive=True)
            # Independent native host material dictionaries per component.
            for component in ("leaf_front", "leaf_back", "leaf_edge", "frame",
                              "trim_front", "trim_back", "hardware"):
                key = "material_" + component
                if key in raw:
                    if raw[key] is not None and not isinstance(raw[key], dict):
                        raise FillError("Material de componente inválido: " + key)
                    out[key] = copy.deepcopy(raw[key])
        # Unit sizes are explicit instance overrides only. Without a key,
        # the unit follows the nominal width/height at evaluation time.
        for axis, label in (("width", "Largura do conjunto"),
                            ("height", "Altura do conjunto")):
            key = "unit_" + axis
            if key in raw:
                out[key] = _number(raw[key], label, positive=True)
        for side in ("left", "right", "top", "bottom"):
            out["clearance_" + side] = _number(
                raw.get("clearance_" + side, family["clearances"][side]),
                "Folga " + side, minimum=0.0)
        if layout == "physical":
            minimum_width = (width + 2 * frame +
                             out["operating_gap_left"] +
                             out["operating_gap_right"])
            minimum_height = height + frame + out["operating_gap_top"]
            if "unit_width" in out and out["unit_width"] < minimum_width - 1e-9:
                raise FillError("Conjunto menor que folha, marco e folgas móveis.")
            if "unit_height" in out and out["unit_height"] < minimum_height - 1e-9:
                raise FillError("Conjunto menor que folha e travessa superior.")
            if out["trim_thickness"] >= out["trim_width"]:
                raise FillError("Alizar: espessura deve ser menor que largura.")
        for angle in ("plan_angle", "model_angle"):
            if not 0 <= out[angle] <= 180:
                raise FillError(f"{angle}: ângulo fora do intervalo de 0 a 180°.")
    else:
        out["panes"] = int(raw.get("panes", 1))
        if not 1 <= out["panes"] <= 16:
            raise FillError("Quantidade de folhas inválida.")
    for key in ("ifc_global_id", "type_name", "material_name"):
        if raw.get(key):
            out[key] = str(raw[key])
    if kind == "door":
        # Retain extension/vendor fields without altering their values.
        preserved = copy.deepcopy(raw)
        preserved.pop("open_angle", None)
        preserved.update(out)
        return preserved
    return out


def station_span(raw):
    """Nominal leaf stations, with door anchors measured on the rough opening."""
    spec = normalize_fill(raw)
    if spec["kind"] == "door":
        rough_left, _rough_right = wallhole_span(spec)
        if spec.get("f01_layout") == "physical":
            start = (rough_left + spec["clearance_left"]
                     + spec["frame_thickness"] + spec["operating_gap_left"]
                     + (f01_unit_size(spec)[0] - f01_minimum_unit(spec)[0]) / 2)
        else:
            unit_width = spec.get("unit_width", spec["width"])
            start = rough_left + spec["clearance_left"] + (unit_width - spec["width"]) / 2
    else:
        shift = {"left": 0.0, "center": 0.5, "right": 1.0}[spec["anchor"]]
        start = spec["position"] - shift * spec["width"]
    return start, start + spec["width"]


def center_station(raw):
    a, b = station_span(raw)
    return (a+b)/2


def f01_minimum_unit(raw):
    """Physical assembly minimum around an unaltered nominal leaf."""
    spec = normalize_fill(raw)
    if spec["kind"] != "door" or spec.get("f01_layout") != "physical":
        raise FillError("Cálculo físico exige F01 com construção física.")
    f = spec["frame_thickness"]
    return (spec["width"] + 2*f + spec["operating_gap_left"]
            + spec["operating_gap_right"],
            spec["height"] + f + spec["operating_gap_top"])


def f01_unit_size(raw):
    """External unit dimensions, distinct from leaf and installation gaps."""
    spec = normalize_fill(raw)
    if spec.get("f01_layout") == "physical":
        width, height = f01_minimum_unit(spec)
        return spec.get("unit_width", width), spec.get("unit_height", height)
    return (spec.get("unit_width", spec["width"]),
            spec.get("unit_height", spec["height"]))


def wallhole_size(raw):
    """Physical rough opening for a door; nominal dimensions stay unchanged."""
    spec = normalize_fill(raw)
    if spec["kind"] != "door":
        raise FillError("Vão de obra calculado apenas para portas.")
    unit_width, unit_height = f01_unit_size(spec)
    return (unit_width + spec["clearance_left"] + spec["clearance_right"],
            unit_height + spec["clearance_top"] + spec["clearance_bottom"])


def wallhole_span(raw):
    """Left/right rough-cut stations, keeping the chosen unit anchor fixed."""
    spec = normalize_fill(raw)
    if spec["kind"] != "door":
        raise FillError("Vão de obra calculado apenas para portas.")
    shift = {"left": 0.0, "center": 0.5, "right": 1.0}[spec["anchor"]]
    cut_width, _cut_height = wallhole_size(spec)
    left = spec["position"] - shift * cut_width
    return left, left + cut_width


def reverse_swing(raw):
    """Invert door clockwise/counterclockwise in exactly one operation."""
    spec = normalize_fill(raw)
    if spec["kind"] != "door":
        raise FillError("Somente portas de abrir possuem inversão de giro.")
    spec["swing"] *= -1
    return spec


def opening_request(raw, *, opening_guid=None):
    """Host opening request, with fill linked to independent object by source_id.

    Does NOT create a 3D element and does NOT call the host or IFC writer.
    Geometry generation belongs to the wall; this record tells it which void
    corresponds to the parametric fill.
    """
    spec = normalize_fill(raw)
    if spec["kind"] == "door" and spec["host_mode"] == "free":
        raise FillError("Porta livre não solicita abertura na parede.")
    if spec["kind"] == "door":
        left, right = wallhole_span(spec)
        cut_width, cut_height = wallhole_size(spec)
        cut_center = (left + right) / 2
    else:
        cut_width, cut_height = spec["width"], spec["height"]
        cut_center = center_station(spec)
    return {
        "id": spec["opening_id"], "kind": "rect",
        "position": cut_center,
        "width": cut_width, "sill": spec["sill"],
        "height": cut_height, "source_id": spec["id"],
        "ifc_global_id": opening_guid,
        "fill": {
            "class": "IfcDoor" if spec["kind"] == "door" else "IfcWindow",
            "global_id": spec.get("ifc_global_id"),
            "name": spec["name"],
            "overall_width": spec["width"],
            "overall_height": spec["height"],
        },
    }


def hotspots(raw):
    """Architectural edit permissions tied to the physical corners.

    Each point can change width; ONLY the top three can edit height and
    ONLY bottom three can edit position (via the radial choice UI).
    """
    spec = normalize_fill(raw)
    left, right = station_span(spec)
    z0 = spec["sill"]
    z1 = z0 + spec["height"]
    out = []
    for row, z in (("bottom", z0), ("top", z1)):
        for at, x in (("left", left), ("center", (left+right)/2), ("right", right)):
            out.append({
                "id": f"{row}-{at}",
                "station": x,
                "elevation": z,
                "controls": ("width", "position") if row == "bottom"
                            else ("width", "height"),
            })
    return out


def door_leaf_plan(raw):
    """Simple exact 2D leaf at the requested opening angle, not a scene mesh.

    Returns hinge, leaf tip and sampled arc (in local station/depth plane).
    +1/-1 switches swing direction. In plan, closed leaf lies on the wall.
    """
    spec = normalize_fill(raw)
    if spec["kind"] != "door":
        raise FillError("Apenas portas possuem folha de giro.")
    left, right = station_span(spec)
    hinge = left if spec["hinge"] == "left" else right
    direction = 1 if spec["hinge"] == "left" else -1
    angle = math.radians(spec["plan_angle"])*spec["swing"]
    def at(radians):
        return [hinge + direction*spec["width"]*math.cos(radians),
                direction*spec["width"]*math.sin(radians)]
    arc = [at(angle*i/16) for i in range(17)]
    return {"hinge": [hinge, 0.0], "tip": at(angle), "arc": arc}


def window_mullions(raw):
    """Model-plane station/elevation dividers for a simple fixed-glazing window."""
    spec = normalize_fill(raw)
    if spec["kind"] != "window":
        raise FillError("Somente janelas possuem montantes de vidro.")
    left, right = station_span(spec)
    return [
        {"station": left+(right-left)*i/spec["panes"],
         "bottom": spec["sill"], "top": spec["sill"]+spec["height"]}
        for i in range(1, spec["panes"])
    ]


def reanchor_fill(raw, anchor):
    """Select left/center/right anchor without physically moving the fill.

    Only the representation of the station changes, never the two endpoints.
    """
    spec = normalize_fill(raw)
    target = str(anchor).lower()
    if target not in ANCHORS:
        raise FillError("Âncora inválida.")
    left, right = (wallhole_span(spec) if spec["kind"] == "door"
                   else station_span(spec))
    spec["anchor"] = target
    spec["position"] = {"left": left, "center": (left + right) / 2,
                        "right": right}[target]
    return normalize_fill(spec)


def edit_from_hotspot(raw, point_id, action, value):
    """Apply a radial-handle operation, preserving all stable IDs.

    Width/height values are full dimensions in metres; position is the NEW
    station of the selected lower hotspot in the wall's reference frame.
    Permission checks live here, not just in the presentation layer.
    """
    spec = normalize_fill(raw)
    hit = next((p for p in hotspots(spec) if p["id"] == point_id), None)
    if hit is None or action not in hit["controls"]:
        raise FillError("Operação não permitida neste hotspot.")
    measure = _number(value, str(action))
    if action == "position":
        spec["position"] += measure-hit["station"]
    elif action == "width":
        spec["width"] = measure
    elif action == "height":
        spec["height"] = measure
    return normalize_fill(spec)
