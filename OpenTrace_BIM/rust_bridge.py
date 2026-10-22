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
            "or unset OPENTRACE_RUST_BACKEND to use Python."
        )
    lib = ctypes.CDLL(str(path))
    inputs = [
        ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.c_size_t,
    ]
    lib.opentrace_align.argtypes = inputs + [ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
    lib.opentrace_align.restype = ctypes.c_int
    lib.opentrace_distribute.argtypes = inputs + [ctypes.POINTER(ctypes.c_double)]
    lib.opentrace_distribute.restype = ctypes.c_int
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
