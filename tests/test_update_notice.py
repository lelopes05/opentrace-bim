# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure regression tests: catalog-only notices never install plugin files."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from OpenTrace_BIM.updater import (
    catalog_entry, catalog_whats_new, compare_versions, _version_key,
)


class UpdateNoticePureTests(unittest.TestCase):
    def test_version_comparison(self):
        cases = (
            ("0.12.9", "0.14.0", -1),
            ("0.14.0", "0.14.0", 0),
            ("v0.14.0", "0.14", 0),
            ("0.14.0rc1", "0.14.0", -1),
            ("0.14.0-beta.2", "0.14.0rc1", -1),
            ("0.14.0.dev3", "0.14.0a1", -1),
            ("0.14.0+build.3", "0.14.0", 0),
            ("0.14.0.post1", "0.14.0", 1),
            ("0.14.1", "0.14.0", 1),
        )
        for left, right, expected in cases:
            with self.subTest(left=left, right=right):
                self.assertEqual(compare_versions(left, right), expected)
                self.assertEqual(compare_versions(right, left), -expected)
        with self.assertRaises(ValueError):
            _version_key("not-a-version")

    def test_reads_opentrace_entry_from_catalog_json(self):
        example = {
            "format": 1,
            "extensions": [
                {"id": "unrelated", "version": "999.0"},
                {
                    "id": "opentrace_bim",
                    "version": "0.14.0",
                    "whats_new": "New wall and door tools",
                },
            ],
        }
        entry = catalog_entry(json.dumps(example).encode("utf-8"))
        self.assertEqual(entry["version"], "0.14.0")
        self.assertEqual(catalog_whats_new(entry), "New wall and door tools")
        self.assertEqual(catalog_whats_new({"summary": "General description"}), "")
        self.assertEqual(catalog_entry(json.dumps(example))["id"], "opentrace_bim")
        with self.assertRaises(ValueError):
            catalog_entry({"extensions": [{"id": "not_opentrace", "version": "5.0"}]})
        with self.assertRaises(ValueError):
            catalog_entry({"extensions": [{"id": "opentrace_bim"}]})

    def test_no_package_download_or_installation_functions_remain(self):
        updater = (Path(__file__).resolve().parents[1]
                   / "OpenTrace_BIM" / "updater.py").read_text(encoding="utf-8")
        forbidden = (
            "_install_package", "_extract_package", "_validate_package",
            "_safe_zip_members", "_request_bytes", "zipfile",
            "shutil", "threading", "urllib.request", "QProgressDialog",
        )
        for name in forbidden:
            with self.subTest(forbidden=name):
                self.assertNotIn(name, updater)


if __name__ == "__main__":
    unittest.main()
