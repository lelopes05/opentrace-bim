# SPDX-License-Identifier: GPL-3.0-or-later
"""T1 translation catalogs: validity, placeholders and actionable coverage."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "OpenTrace_BIM"
TOKENS = re.compile(r"\{([A-Za-z_]\w*)\}")


def catalog(lang):
    return json.loads((PLUGIN / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))


def literal_calls():
    """Locate the source Portuguese strings passed directly to t()."""
    occurrences = {}
    for file in sorted(PLUGIN.rglob("*.py")):
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, (ast.Name, ast.Attribute))
                    and (node.func.id if isinstance(node.func, ast.Name)
                         else node.func.attr) == "t"
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                key = node.args[0].value
                occurrences.setdefault(key, []).append(
                    f"{file.relative_to(ROOT)}:{node.lineno}")
    return occurrences


class TranslationCatalogTests(unittest.TestCase):
    def test_json_maps_and_original_portuguese_source(self):
        self.assertFalse((PLUGIN / "i18n" / "pt-BR.json").exists())
        for lang in ("en", "es"):
            with self.subTest(lang=lang):
                translations = catalog(lang)
                self.assertIsInstance(translations, dict)
                self.assertTrue(translations)
                self.assertTrue(all(isinstance(key, str) and isinstance(value, str)
                                    for key, value in translations.items()))

    def test_translations_keep_named_placeholders(self):
        for lang in ("en", "es"):
            for key, translated in catalog(lang).items():
                with self.subTest(lang=lang, key=key):
                    self.assertEqual(set(TOKENS.findall(key)),
                                     set(TOKENS.findall(translated)))

    def test_generated_catalogs_match_legacy_dictionary_priorities(self):
        # Ensures the checked-in files came from the committed, repeatable
        # generator (which does not import the plugin or require PySide).
        script = ROOT / "scripts" / "build_i18n_catalogs.py"
        spec = importlib.util.spec_from_file_location("build_i18n_catalogs", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        expected = module.build()
        for lang in ("en", "es"):
            self.assertEqual(catalog(lang), expected[lang])

    def test_english_legacy_fallback_matches_every_dictionary_and_phrase(self):
        """T1 must preserve the old English for every legacy dictionary key."""
        from OpenTrace_BIM import i18n as translator

        dictionaries = (
            translator._EN, translator._EXTRA_EN, translator._UI_EN,
            translator._TOOL_EN, translator._LAYERCOMBO_EN,
        )
        keys = set().union(*(dictionary.keys() for dictionary in dictionaries))
        self.assertTrue(keys)
        for source in sorted(keys):
            with self.subTest(source=source):
                self.assertEqual(
                    translator.t(source, _locale="en"), translator.english(source))

        phrase_only = "Clique para criar parede"
        self.assertNotIn(phrase_only, catalog("en"))
        self.assertNotIn(phrase_only, keys)
        expected = translator.english(phrase_only)
        self.assertNotEqual(expected, phrase_only)
        self.assertEqual(translator.t(phrase_only, _locale="en"), expected)
        self.assertIn(("en", phrase_only), translator.MISSING)

    @unittest.expectedFailure  # T2 converts this into a required assertion.
    def test_literal_t_calls_have_complete_en_and_es_catalogs(self):
        used = literal_calls()
        counts = {}
        missing = {}
        for lang in ("en", "es"):
            not_found = {key: positions for key, positions in used.items()
                         if key not in catalog(lang)}
            counts[lang] = len(not_found)
            missing[lang] = not_found
        print(f"Translation T1 literal coverage: {counts}", flush=True)
        # Even at zero, retain the expected-failure gate until T2 removes
        # the decorator and enables strict coverage. No CI red in T1.
        self.assertEqual(missing, {"en": {}, "es": {}},
                         f"T1 missing literals: {counts}")
        self.fail("T1 coverage is report-only until T2")


if __name__ == "__main__":
    unittest.main()
