# SPDX-License-Identifier: GPL-3.0-or-later
"""Session creation defaults applied inside native creation commands."""
import copy
from core.layers import DEFAULT_LAYER, assign_layer
from .bim import ifc_identity_data

def creation_defaults(scene):
    """Session-only defaults per modelling tool; never a second layer registry."""
    if not hasattr(scene, "_opentrace_creation_properties"):
        scene._opentrace_creation_properties = {}
    return scene._opentrace_creation_properties


def apply_creation_properties(command, scene, groups, kind):
    """Called inside creation commands, once: redo retains original values."""
    if getattr(command, "_properties_initialized", False):
        return
    defaults = creation_defaults(scene).get(kind, {})
    name = defaults.get("layer", DEFAULT_LAYER)
    if scene.layer(name) is None:
        name = DEFAULT_LAYER
    for group in groups:
        # An explicit template layer wins unless a user selected a destination.
        if "layer" in defaults or not getattr(group, "layer", None):
            assign_layer(group, name)
        if defaults.get("ifc"):
            meta = ifc_identity_data(group)
            meta.update(copy.deepcopy(defaults["ifc"]))
            group.ifc = meta
    command._properties_initialized = True
