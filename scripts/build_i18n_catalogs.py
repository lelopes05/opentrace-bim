#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the OpenTrace JSON catalogs from the legacy exact-match dictionaries.

Run once with: python scripts/build_i18n_catalogs.py
No plugin import or PySide6 dependency. This script is not included in the
installable OpenTrace_BIM/ directory.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OpenTrace_BIM" / "i18n.py"
DEST = ROOT / "OpenTrace_BIM" / "i18n"
PRIORITY_LOW_TO_HIGH = (
    "_EN", "_EXTRA_EN", "_UI_EN", "_TOOL_EN", "_LAYERCOMBO_EN",
)
# Context-dependent fragments are not safe to translate as standalone strings.
# _PHRASE_EN is NEVER imported into the catalogs.
UNSAFE_EXACT = {"Não foi", "Há um"}


def is_safe_key(key: str) -> bool:
    """Keep whole labels/messages; defer concatenated phrase pieces to T2."""
    return (bool(key) and key == key.strip() and not key.startswith((".", ",", "'"))
            and not key.endswith("(") and key not in UNSAFE_EXACT)


def legacy_dictionaries(path: Path = SOURCE) -> dict[str, dict[str, str]]:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = {}
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for name in node.targets:
            if isinstance(name, ast.Name) and name.id in (*PRIORITY_LOW_TO_HIGH, "_ES"):
                obj = ast.literal_eval(node.value)
                if not isinstance(obj, dict):
                    raise TypeError(f"{name.id} is not a dictionary")
                if not all(isinstance(k, str) and isinstance(v, str)
                           for k, v in obj.items()):
                    raise TypeError(f"{name.id} contains non-string entries")
                result[name.id] = obj
    return result


def build() -> dict[str, dict[str, str]]:
    legacy = legacy_dictionaries()
    merged: dict[str, str] = {}
    for name in PRIORITY_LOW_TO_HIGH:
        merged.update(legacy[name])
    return {
        "en": {key: value for key, value in merged.items() if is_safe_key(key)},
        "es": {key: value for key, value in legacy["_ES"].items() if is_safe_key(key)},
    }


def main() -> None:
    DEST.mkdir(exist_ok=True)
    for lang, mapping in build().items():
        target = DEST / f"{lang}.json"
        target.write_text(json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True)
                          + "\n", encoding="utf-8")
        print(f"{target.relative_to(ROOT)}: {len(mapping)} entries")


if __name__ == "__main__":
    main()
