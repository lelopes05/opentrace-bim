# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare compiled Rust with Python arrangement logic; no Qt required."""
from __future__ import annotations

import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from OpenTrace_BIM import arrange_core, rust_bridge


def close(a, b):
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-10), (x, y)


def main():
    rust_bridge._library()
    rng = random.Random(440)
    comparisons = 0
    for n in range(2, 13):
        for _ in range(70):
            bounds = []
            for _ in range(n):
                items = []
                for _ in range(3):
                    lo = rng.uniform(-20.0, 20.0)
                    items.append((lo, lo + rng.uniform(0.0, 3.0)))
                bounds.append(tuple(items))
            for axis in (0, 1, 2):
                for edge in ("min", "center", "max"):
                    close(arrange_core.align_offsets(bounds, axis, edge), rust_bridge.align_offsets(bounds, axis, edge))
                    comparisons += 1
                if n >= 3:
                    try:
                        python = arrange_core.distribute_offsets(bounds, axis)
                    except ValueError:
                        try:
                            rust_bridge.distribute_offsets(bounds, axis)
                        except ValueError:
                            pass
                        else:
                            raise AssertionError("Rust did not reject overlapping bounds")
                    else:
                        close(python, rust_bridge.distribute_offsets(bounds, axis))
                    comparisons += 1
    print(f"Rust/Python comparisons passed: {comparisons}")


if __name__ == "__main__":
    main()
