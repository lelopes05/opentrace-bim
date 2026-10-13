# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure source-contract checks, with no host or PySide6 dependency."""
import ast
import csv
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "OpenTrace_BIM"
GUIDE = PLUGIN / "step_guide.py"


def declared_steps():
    tree = ast.parse(GUIDE.read_text(encoding="utf-8"))
    assignment = next(node for node in tree.body
                      if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "STEPS"
                              for target in node.targets))
    return ast.literal_eval(assignment.value)


class StepGuideContractTests(unittest.TestCase):
    def test_every_declared_step_matches_approved_csv(self):
        with (ROOT / "docs" / "guia_passos.csv").open(encoding="utf-8", newline="") as stream:
            approved = {row["id"]: row["proposta"] for row in csv.DictReader(stream)}
        steps = declared_steps()
        self.assertTrue(steps)
        for step_id, text in steps.items():
            self.assertIn(step_id, approved)
            self.assertEqual(text, approved[step_id])

    def test_every_referenced_step_exists(self):
        steps = declared_steps()
        used = set()
        for path in PLUGIN.rglob("*.py"):
            if path.name == "step_guide.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if (isinstance(node.func, ast.Name)
                        and node.func.id == "show_step"
                        and len(node.args) >= 3
                        and isinstance(node.args[2], ast.Constant)
                        and isinstance(node.args[2].value, str)):
                    used.add(node.args[2].value)
        self.assertTrue(used, "No tool emits a guide step")
        self.assertFalse(used - steps.keys())

    def test_show_step_persists_for_ten_minutes(self):
        tree = ast.parse(GUIDE.read_text(encoding="utf-8"))
        hold = next(node.value.value for node in tree.body
                    if isinstance(node, ast.Assign) and any(
                        isinstance(target, ast.Name) and target.id == "STEP_HOLD_MS"
                        for target in node.targets))
        self.assertEqual(hold, 600000)


if __name__ == "__main__":
    unittest.main()
