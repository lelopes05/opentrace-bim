# SPDX-License-Identifier: GPL-3.0-or-later
"""Choose the Python or Rust calculation engine without changing the Qt UI.

Python remains the default. To exercise the native code after building it,
launch IngeTrazo with OPENTRACE_RUST_BACKEND=1 in its environment.
Explicit selection fails visibly when the Rust library is missing.
"""
from __future__ import annotations

import os
from . import arrange_core


def active_backend():
    return "rust" if os.environ.get("OPENTRACE_RUST_BACKEND") == "1" else "python"


def _backend():
    if active_backend() == "rust":
        from . import rust_bridge
        return rust_bridge
    return arrange_core


def align_offsets(bounds, axis, edge):
    return _backend().align_offsets(bounds, axis, edge)


def distribute_offsets(bounds, axis):
    return _backend().distribute_offsets(bounds, axis)
