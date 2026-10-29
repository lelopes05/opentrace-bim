"""US NCS layer template: names and combinations stay consistent.

Loads ``layer_combinations/us_ncs.py`` on its own (no IngeTrazo/PySide6).
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OpenTrace_BIM" / "layer_combinations" / "us_ncs.py"


def _load():
    spec = importlib.util.spec_from_file_location("us_ncs_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecordingCombo:
    """Stands in for the template's make_combo and keeps the arguments."""

    def __init__(self):
        self.calls = []

    def __call__(self, name, show_prefixes=(), show_exact=(), lock_prefixes=(),
                 lock_exact=(), hide_exact=(), group_overrides=None):
        self.calls.append(dict(name=name, show_prefixes=show_prefixes,
                               show_exact=show_exact, lock_prefixes=lock_prefixes,
                               lock_exact=lock_exact, hide_exact=hide_exact))
        return {"name": name}


class UsNcsTemplateTest(unittest.TestCase):
    def setUp(self):
        self.ncs = _load()
        self.names = [name for name, _folder, _group in self.ncs.LAYER_DEFS]

    def test_layer_names_are_unique_and_follow_ncs(self):
        self.assertEqual(len(self.names), len(set(self.names)))
        pattern = re.compile(r"^[ACEFGILMPST]-[A-Z]{4}(-[A-Z]{4})?$")
        for name in self.names:
            if name != "Layer 0":
                self.assertRegex(name, pattern)

    def test_disciplines_are_read_from_the_first_field(self):
        self.assertEqual(self.ncs.discipline("A-WALL-EXTR"), "A")
        self.assertEqual(self.ncs.discipline("M-HVAC-DUCT"), "M")
        self.assertEqual(self.ncs.discipline("Layer 0"), "Layer 0")

    def test_combinations_only_name_existing_layers_and_disciplines(self):
        recorder = RecordingCombo()
        combos = self.ncs.combinations(recorder)
        known = set(self.names)
        disciplines = {self.ncs.discipline(n) for n in self.names}
        for call in recorder.calls:
            for key in ("show_exact", "lock_exact", "hide_exact"):
                self.assertLessEqual(set(call[key]), known, (call["name"], key))
            for key in ("show_prefixes", "lock_prefixes"):
                self.assertLessEqual(set(call[key]), disciplines,
                                     (call["name"], key))
        names = [c["name"] for c in combos]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn(self.ncs.DEFAULT_COMBINATION, names)

    def test_every_layer_has_a_folder_and_a_valid_group(self):
        for name, folder, group in self.ncs.LAYER_DEFS:
            self.assertTrue(folder.strip(), name)
            self.assertIn(group, range(0, 8), name)


if __name__ == "__main__":
    unittest.main()
