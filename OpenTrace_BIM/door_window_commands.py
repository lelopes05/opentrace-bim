# SPDX-License-Identifier: GPL-3.0-or-later
"""Undoable hosted door/window operations for IngeTrazo (stage 02).

The opening is always part of the wall; the fill is always a separate scene
Group. Both changes happen inside ONE host history Command. No tools are
registered by importing this module. Stage 01's wall generator must be present
before using floor-reaching doors or top-cut openings in the UI.
"""
from __future__ import annotations

import copy

from PySide6.QtGui import QMatrix4x4
from core.history import Command

from .bim import new_ifc_guid
from .commands import EditWall, root_edit_allowed
from .door_window_core import FillError, normalize_fill, opening_request, reverse_swing
from .door_window_geometry import place_fill_on_wall
from .model import KEY, read_wall


def _fill_record(group):
    ext = getattr(group, "ext", None)
    rec = ext.get(KEY) if isinstance(ext, dict) else None
    return rec if isinstance(rec, dict) and rec.get("kind") in ("door", "window") else None


def _assert_unique(scene, spec, *, except_group=None):
    """Avoid duplicate fill identities and double occupancy of one opening."""
    for item in list(scene.groups):
        if item is except_group:
            continue
        rec = _fill_record(item)
        if rec is None:
            continue
        if rec.get("source_id") == spec["id"]:
            raise FillError("Já existe uma esquadria com este identificador.")
        if (rec.get("host_id"), rec.get("opening_id")) == (
                spec["host_id"], spec["opening_id"]):
            raise FillError("Este vão já possui uma porta ou janela.")


def _wall_values_with_fill(wall, spec, *, allow_existing=False):
    """Return an updated wall record, preserving other openings and GUIDs."""
    if getattr(wall, "uid", None) != spec["host_id"]:
        raise FillError("A esquadria deve apontar para a parede selecionada.")
    values = read_wall(wall)
    existing = list(values.get("openings", ()))
    matches = [o for o in existing if o.get("id") == spec["opening_id"]]
    if len(matches) > 1:
        raise FillError("IDs duplicados de aberturas na mesma parede.")
    old = matches[0] if matches else None
    if old is not None:
        source = old.get("source_id")
        if source and source != spec["id"]:
            raise FillError("O vão já pertence a outro objeto.")
        if not allow_existing and source == spec["id"]:
            raise FillError("O vão já está reservado para esta esquadria.")
    opening_guid = old.get("ifc_global_id") if old else None
    if not opening_guid:
        opening_guid = new_ifc_guid()
    request = opening_request(spec, opening_guid=opening_guid)
    if old is not None:
        # Preserve extension-specific opening metadata and IFC property sets.
        merged = copy.deepcopy(old)
        merged.update(request)
        request = merged
    values["openings"] = [
        request if item is old else copy.deepcopy(item) for item in existing
    ] if old is not None else existing + [request]
    return values


class CreateHostedFill(Command):
    """Create/reuse the wall cut and insert its fill in one Undo/Redo step."""

    def __init__(self, scene, wall, raw):
        root_edit_allowed(scene)
        # Only newly created F01 instances use the physically coherent
        # dimensions. Saved pre-recovery schema-2 and schema-1 instances
        # have no marker and keep their original cut until explicit migration.
        created = copy.deepcopy(raw)
        if (created.get("kind") == "door"
                and created.get("schema") not in (1, "1")
                and "f01_layout" not in created):
            created["f01_layout"] = "physical"
        self.spec = normalize_fill(created)
        _assert_unique(scene, self.spec)
        self.wall = wall
        if not self.spec.get("ifc_global_id"):
            self.spec["ifc_global_id"] = new_ifc_guid()
        values = _wall_values_with_fill(wall, self.spec)
        self.wall_edit = EditWall(scene, wall, values)
        self.group = None
        self.index = None

    def do(self, scene):
        _assert_unique(scene, self.spec)
        if self.wall not in scene.groups:
            raise FillError("A parede não está no documento.")
        if self.group is not None and self.group in scene.groups:
            raise FillError("A esquadria já está no documento.")
        # The EditWall operation owns the topology and its own rollback state.
        self.wall_edit.do(scene)
        try:
            if self.group is None:
                self.group = place_fill_on_wall(self.spec, self.wall)
                self.group.ifc["global_id"] = self.spec["ifc_global_id"]
                from .creation_properties import apply_creation_properties
                apply_creation_properties(self, scene, [self.group], self.spec["kind"])
            if self.index is None:
                self.index = len(scene.groups)
            scene.groups.insert(min(self.index, len(scene.groups)), self.group)
            scene.version += 1
        except Exception:
            if self.group in scene.groups:
                scene.groups.remove(self.group)
            self.wall_edit.undo(scene)
            raise

    def undo(self, scene):
        if self.group not in scene.groups:
            raise FillError("A esquadria não está no documento.")
        scene.groups.remove(self.group)
        scene.selection.discard(self.group)
        self.wall_edit.undo(scene)
        scene.version += 1


class EditHostedFill(Command):
    """Edit dimensions, anchor, position or swing without replacing the Group.

    The original Group UID, IFC GUID and opening GUID survive all history moves.
    Hotspot permissions are enforced at the UI boundary; any accepted property
    edit is validated here and re-cuts the wall when dimensions change.
    """

    def __init__(self, scene, wall, group, changes):
        root_edit_allowed(scene)
        if group not in scene.groups or wall not in scene.groups:
            raise FillError("Parede ou esquadria fora do documento.")
        rec = _fill_record(group)
        if rec is None:
            raise FillError("O objeto selecionado não é uma esquadria paramétrica.")
        old = normalize_fill(rec.get("params"))
        _assert_unique(scene, old, except_group=group)
        if old["host_id"] != wall.uid or rec.get("source_id") != old["id"]:
            raise FillError("Referência da esquadria à parede inconsistente.")
        updated = dict(old)
        for key, value in changes.items():
            if key in ("unit_width", "unit_height") and value is None:
                # Switch back from manufacturer override to derived unit size.
                updated.pop(key, None)
            else:
                updated[key] = value
        self.spec = normalize_fill(updated)
        for key in ("id", "host_id", "opening_id", "kind", "ifc_global_id"):
            if self.spec.get(key) != old.get(key):
                raise FillError("Não é permitido trocar a identidade da esquadria.")
        self.wall = wall
        self.group = group
        requested_wall = _wall_values_with_fill(wall, self.spec, allow_existing=True)
        # Reversing swing, changing anchor label or hinge never affects the
        # host void. Do not rebuild a potentially huge curved wall for it.
        self.wall_edit = (EditWall(scene, wall, requested_wall)
                          if requested_wall != read_wall(wall) else None)
        self.before = self._state(group)
        self.after = None

    @staticmethod
    def _state(group):
        return (list(group.children), copy.deepcopy(group.ext),
                copy.deepcopy(group.ifc), QMatrix4x4(group.xform), group.name)

    def _apply(self, scene, state):
        children, ext, ifc, xform, name = state
        self.group.children = list(children)
        self.group.ext = copy.deepcopy(ext)
        self.group.ifc = copy.deepcopy(ifc)
        self.group.xform = QMatrix4x4(xform)
        self.group.name = name
        scene.version += 1

    def do(self, scene):
        if self.group not in scene.groups:
            raise FillError("A esquadria foi removida do documento.")
        if self.wall_edit is not None:
            self.wall_edit.do(scene)
        try:
            if self.after is None:
                staged = place_fill_on_wall(self.spec, self.wall)
                # Carry across custom metadata/IFC overrides, not just the
                # generated frame and leaf meshes.
                generated = copy.deepcopy(_fill_record(staged))
                staged.ext = copy.deepcopy(self.group.ext)
                staged.ext[KEY] = generated
                staged.ifc = copy.deepcopy(self.group.ifc)
                staged.ifc["name"] = self.spec["name"]
                if self.spec["kind"] == "door":
                    from .door_window_core import wallhole_size
                    staged.ifc["overall_width"], staged.ifc["overall_height"] = wallhole_size(self.spec)
                else:
                    staged.ifc["overall_width"] = self.spec["width"]
                    staged.ifc["overall_height"] = self.spec["height"]
                staged.name = self.spec["name"]
                self.after = self._state(staged)
            self._apply(scene, self.after)
        except Exception:
            if self.wall_edit is not None:
                self.wall_edit.undo(scene)
            raise

    def undo(self, scene):
        self._apply(scene, self.before)
        if self.wall_edit is not None:
            self.wall_edit.undo(scene)


def reverse_hosted_door(scene, wall, group):
    """Build one single Undo/Redo command for the UI's reverse-swing button."""
    rec = _fill_record(group)
    if rec is None:
        raise FillError("Selecione uma porta paramétrica.")
    return EditHostedFill(scene, wall, group,
                          {"swing": reverse_swing(rec["params"])["swing"]})

class DeleteHostedOpening(Command):
    """Remove one hosted void and its independent door/window atomically.

    Both Undo and Redo preserve the fill object, UID and IFC identity.
    """

    def __init__(self, scene, wall, opening_id):
        root_edit_allowed(scene)
        values = read_wall(wall)
        opening = next((o for o in values["openings"]
                        if o.get("id") == opening_id), None)
        if opening is None:
            raise FillError("A abertura não existe mais na parede.")
        self.wall = wall
        self.group = None
        for candidate in scene.groups:
            rec = _fill_record(candidate)
            if (rec and rec.get("host_id") == wall.uid
                    and rec.get("opening_id") == opening_id):
                self.group = candidate
                break
        if opening.get("source_id") and self.group is None:
            raise FillError("A abertura está ligada a uma esquadria ausente.")
        self.index = scene.groups.index(self.group) if self.group else None
        values["openings"] = [o for o in values["openings"]
                              if o.get("id") != opening_id]
        self.wall_edit = EditWall(scene, wall, values)

    def do(self, scene):
        self.wall_edit.do(scene)
        if self.group is not None:
            if self.group not in scene.groups:
                self.wall_edit.undo(scene)
                raise FillError("A esquadria vinculada não está mais no documento.")
            scene.groups.remove(self.group)
            scene.selection.discard(self.group)
            scene.version += 1

    def undo(self, scene):
        self.wall_edit.undo(scene)
        if self.group is not None:
            scene.groups.insert(min(self.index, len(scene.groups)), self.group)
            scene.version += 1

def _generated_shape_signature(group):
    """Detect host-dependent vertex/trim/face changes even at constant depth.

    A manually sized jamb can keep the same depth while its position within
    the new finished wall changes. Comparing depth alone silently misses that.
    """
    return tuple(
        (part.name, tuple(
            (round(v.position.x(), 8), round(v.position.y(), 8),
             round(v.position.z(), 8)) for v in part.mesh.vertices))
        for part in group.children
    )


def sync_hosted_fill_placements(scene, *, host_id=None):
    """Synchronize transforms and wall-dependent frame meshes without new IDs.

    The wall and fill parameters are stored by undoable commands. Their
    meshes are derived render data, regenerated upon host dimensional change.
    """
    from .model import wall_record
    walls = {getattr(wall, "uid", None): wall for wall in scene.groups
             if wall_record(wall) is not None
             and (host_id is None or wall.uid == host_id)}
    changed = 0
    for group in list(scene.groups):
        rec = _fill_record(group)
        if rec is None or (host_id is not None and rec.get("host_id") != host_id):
            continue
        wall = walls.get(rec.get("host_id"))
        if wall is None:
            continue
        try:
            target = place_fill_on_wall(rec["params"], wall)
        except (FillError, ValueError, KeyError):
            # A temporarily incompatible host never deletes a saved fill.
            continue
        updated = False
        if _generated_shape_signature(group) != _generated_shape_signature(target):
            old_parts = {part.name: part for part in group.children}
            for part in target.children:
                old = old_parts.get(part.name)
                if old is not None:
                    if part.material is None:
                        part.material = copy.deepcopy(old.material)
                    part.layer = old.layer
            group.children = list(target.children)
            updated = True
        if group.xform != target.xform:
            group.xform = QMatrix4x4(target.xform)
            updated = True
        if updated:
            changed += 1
    return changed
