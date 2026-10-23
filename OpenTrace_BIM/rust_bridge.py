# SPDX-License-Identifier: GPL-3.0-or-later
"""ctypes adapter for the dependency-free OpenTrace Rust geometry core.

Keeps the original Python validation/errors; passes only flattened float64
bounding boxes across the C ABI. Does not import Qt or mutate model objects.
"""
from __future__ import annotations

import ctypes
from functools import lru_cache
from pathlib import Path
import sys

from . import arrange_core


def _binary_name():
    if sys.platform == "win32":
        return "opentrace_rust_core.dll"
    if sys.platform == "darwin":
        return "libopentrace_rust_core.dylib"
    return "libopentrace_rust_core.so"


@lru_cache(maxsize=1)
def _library():
    path = Path(__file__).resolve().parent / "rust_core" / "target" / "release" / _binary_name()
    if not path.is_file():
        raise RuntimeError(
            "OpenTrace 0.44.0 Rust: native library is missing at "
            f"{path}. Build it with 'cargo build --release' in rust_core, "
            "Check that the compiled 0.44.0 Rust plugin was installed correctly."
        )
    lib = ctypes.CDLL(str(path))
    inputs = [
        ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.c_size_t,
    ]
    lib.opentrace_align.argtypes = inputs + [ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
    lib.opentrace_align.restype = ctypes.c_int
    lib.opentrace_distribute.argtypes = inputs + [ctypes.POINTER(ctypes.c_double)]
    lib.opentrace_distribute.restype = ctypes.c_int
    xy_ptr = ctypes.POINTER(ctypes.c_double)
    lib.opentrace_intersects_xy.argtypes = [xy_ptr, ctypes.c_double]
    lib.opentrace_intersects_xy.restype = ctypes.c_int
    lib.opentrace_area_xy.argtypes = [xy_ptr, ctypes.c_size_t]
    lib.opentrace_area_xy.restype = ctypes.c_double
    lib.opentrace_point_in_polygon.argtypes = [ctypes.c_double, ctypes.c_double, xy_ptr, ctypes.c_size_t]
    lib.opentrace_point_in_polygon.restype = ctypes.c_int
    lib.opentrace_arc_xy.argtypes = [
        ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
        ctypes.c_double, ctypes.c_double, ctypes.c_double,
        ctypes.c_size_t, ctypes.c_size_t, ctypes.c_int, xy_ptr,
    ]
    lib.opentrace_arc_xy.restype = ctypes.c_int
    lib.opentrace_vertical_beam.argtypes = [xy_ptr, ctypes.c_size_t, ctypes.c_double, ctypes.c_double, ctypes.c_double, xy_ptr]
    lib.opentrace_vertical_beam.restype = ctypes.c_int
    lib.opentrace_prism_vertices.argtypes = [xy_ptr, xy_ptr, ctypes.c_double, xy_ptr]
    lib.opentrace_prism_vertices.restype = ctypes.c_int
    lib.opentrace_door_grooves.argtypes = [
        ctypes.c_size_t, ctypes.c_double, ctypes.c_double, ctypes.c_double,
        ctypes.c_double, ctypes.c_double, xy_ptr,
    ]
    lib.opentrace_door_grooves.restype = ctypes.c_int
    return lib


def _values(bounds):
    flat = [float(value) for item in bounds for pair in item for value in pair]
    return (ctypes.c_double * len(flat))(*flat)


def align_offsets(bounds, axis, edge):
    arrange_core._check(bounds, axis)
    if edge not in ("min", "center", "max"):
        raise ValueError("Referência de alinhamento inválida.")
    if len(bounds) < 2:
        raise ValueError("Selecione pelo menos dois objetos.")
    key = {"min": 0, "center": 1, "max": 2}[edge]
    values = _values(bounds)
    result = (ctypes.c_double * len(bounds))()
    status = _library().opentrace_align(values, len(bounds), axis, key, result)
    if status != 0:
        raise RuntimeError(f"OpenTrace Rust alignment error (code {status}).")
    return list(result)


def distribute_offsets(bounds, axis):
    arrange_core._check(bounds, axis)
    if len(bounds) < 3:
        raise ValueError("Selecione pelo menos três objetos para distribuir.")
    values = _values(bounds)
    result = (ctypes.c_double * len(bounds))()
    status = _library().opentrace_distribute(values, len(bounds), axis, result)
    if status == 2:
        raise ValueError("Os objetos ocupam mais espaço do que o intervalo disponível.")
    if status != 0:
        raise RuntimeError(f"OpenTrace Rust distribution error (code {status}).")
    return list(result)


def _xy_values(points):
    flat = [float(component) for p in points for component in p[:2]]
    return (ctypes.c_double * len(flat))(*flat)


def signed_area(points):
    if len(points) < 3:
        return 0.0
    return _library().opentrace_area_xy(_xy_values(points), len(points))


def point_in_polygon(point, polygon):
    if len(polygon) < 3:
        return False
    status = _library().opentrace_point_in_polygon(
        float(point[0]), float(point[1]), _xy_values(polygon), len(polygon))
    if status < 0:
        raise RuntimeError("Rust point-in-polygon failure")
    return bool(status)


def segments_intersect(a, b, c, d, tol=1e-9):
    values = _xy_values((a, b, c, d))
    status = _library().opentrace_intersects_xy(values, float(tol))
    if status < 0:
        raise RuntimeError("Rust segment intersection failure")
    return bool(status)


def sample_arc_xy(a, b, sagitta, *, step_deg=5.0, max_segment=0.20,
                  max_samples=256, min_spans=4, opening=False):
    cap = int(max_samples)
    if not (2 <= cap <= 16384):
        raise ValueError("Invalid maximum arc tessellation")
    result = (ctypes.c_double * ((cap + 1) * 2))()
    n = _library().opentrace_arc_xy(
        float(a[0]), float(a[1]), float(b[0]), float(b[1]), float(sagitta),
        float(step_deg), float(max_segment), cap, int(min_spans), int(opening), result)
    if n < 2:
        raise RuntimeError(f"Rust arc sampling failure (code {n})")
    return [(result[2*i], result[2*i+1]) for i in range(n)]


def beam_vertical_z(positions, length, rise, sagitta):
    if not positions:
        return []
    inputs = (ctypes.c_double * len(positions))(*(float(s) for s in positions))
    output = (ctypes.c_double * len(positions))()
    status = _library().opentrace_vertical_beam(
        inputs, len(positions), float(length), float(rise), float(sagitta), output)
    if status == 2:
        raise ValueError("A curvatura vertical gera retorno sobre si mesma; reduza a flecha.")
    if status:
        raise RuntimeError(f"Rust beam profile failure (code {status})")
    return list(output)


def prism_vertices(x0, x1, y0, y1, z0, z1, *, pivot=None, angle=0.0):
    bounds = (ctypes.c_double * 6)(x0, x1, y0, y1, z0, z1)
    pivot_values = None if pivot is None else (ctypes.c_double * 2)(*pivot)
    output = (ctypes.c_double * 24)()
    status = _library().opentrace_prism_vertices(bounds, pivot_values, float(angle), output)
    if status:
        raise ValueError("Rust prism geometry failure")
    return [tuple(output[3*i:3*i+3]) for i in range(8)]


def groove_spans(count, width, height, thickness, margin, offset):
    result = (ctypes.c_double * (count*4))()
    status = _library().opentrace_door_grooves(
        int(count), float(width), float(height), float(thickness),
        float(margin), float(offset), result)
    if status:
        raise RuntimeError("Rust door groove geometry failure")
    return [(index+1, *tuple(result[index*4:index*4+4])) for index in range(count)]
