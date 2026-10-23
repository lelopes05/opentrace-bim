# SPDX-License-Identifier: GPL-3.0-or-later
"""The installed 0.44.0 Rust package always uses its compiled native core.

No environment variables, activation buttons or silent Python fallback.
"""
from . import rust_bridge

def active_backend():
    return "rust"

def align_offsets(bounds, axis, edge):
    return rust_bridge.align_offsets(bounds, axis, edge)

def distribute_offsets(bounds, axis):
    return rust_bridge.distribute_offsets(bounds, axis)
