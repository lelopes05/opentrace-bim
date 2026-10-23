# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated, backwards-compatible editable details of a traditional grooved door.

Dimensions are metres. The historical appearance is 3 vertical 3 mm grooves,
100 mm clear at both ends. Independent of the glazed-leaf grid contract.
"""
from __future__ import annotations
import math
from . import rust_bridge as _rust_geometry

DEFAULT_GROOVES = {
    'groove_count': 3,
    'groove_width': .003,
    'groove_end_margin': .10,
    'groove_offset': 0.,
}


def normalize_grooves(raw, width, height):
    values = {}
    try:
        for key, default in DEFAULT_GROOVES.items():
            value = raw.get(key, default)
            if isinstance(value, bool):
                raise ValueError(key)
            if key == 'groove_count':
                if isinstance(value, float) and value.is_integer():
                    value=int(value)
                if type(value) is not int or not 1 <= value <= 12:
                    raise ValueError(key)
            else:
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError(key)
            values[key] = value
        count = values['groove_count']
        thickness = values['groove_width']
        margin = values['groove_end_margin']
        offset = values['groove_offset']
        if not .001 <= thickness <= .03:
            raise ValueError('groove_width')
        if margin < .01 or margin >= (height - .02)/2:
            raise ValueError('groove_end_margin')
        spacing = width/(count + 1)
        if spacing <= thickness + .005:
            raise ValueError('groove_count')
        if abs(offset) + thickness/2 + .01 >= spacing:
            raise ValueError('groove_offset')
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('Invalid groove dimensions, count or offset for this leaf.') from exc
    return values


def groove_spans(raw, width, height):
    data = normalize_grooves(raw, width, height)
    n = data['groove_count']
    w = data['groove_width']
    offset = data['groove_offset']
    margin = data['groove_end_margin']
    yield from _rust_geometry.groove_spans(n, width, height, w, margin, offset)
