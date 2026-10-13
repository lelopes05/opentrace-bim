# SPDX-License-Identifier: GPL-3.0-or-later
"""T1 report-only real-host audit, without rewriting finished widgets.

Each locale runs in a separate process: constructing several MainWindows in
one offscreen Qt process is unsafe in the current host. No module patching.
"""
from __future__ import annotations

import ast
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "OpenTrace_BIM"
REPORT = ROOT / "i18n_report.md"
LANGUAGES = ("en", "es", "pt-BR")
MARKER = "OPENTRACE_I18N_AUDIT:"
PORTUGUESE_IN_EN = frozenset("çãõáàâéêíóôú")
PORTUGUESE_IN_ES = frozenset("çãõâêô")


def catalogs():
    return {
        lang: json.loads((PLUGIN / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        for lang in ("en", "es")
    }


def source_inventory():
    """Literal -> origin and static UI call sites without translation."""
    literals: dict[str, list[str]] = {}
    unwrapped = []
    methods = {
        "setText", "setTitle", "setToolTip", "setStatusTip",
        "setPlaceholderText", "setWindowTitle", "setTabText",
        "setItemText", "setAccessibleName", "addItem", "addTab",
        "addAction", "setWhatsThis", "setTextFormat",
    }
    constructors = {"QLabel", "QPushButton", "QToolButton", "QGroupBox",
                    "QAction", "QCheckBox", "QRadioButton", "QDockWidget"}

    def contains_t(node):
        return any(isinstance(child, ast.Call)
                   and (isinstance(child.func, ast.Name)
                        and child.func.id == "t"
                        or isinstance(child.func, ast.Attribute)
                        and child.func.attr == "t")
                   for child in ast.walk(node))

    for path in sorted(PLUGIN.rglob("*.py")):
        if path.name == "i18n.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = str(path.relative_to(ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.setdefault(node.value, []).append(f"{rel}:{node.lineno}")
            if not isinstance(node, ast.Call):
                continue
            name = (node.func.id if isinstance(node.func, ast.Name)
                    else node.func.attr if isinstance(node.func, ast.Attribute)
                    else "")
            if name not in methods | constructors or not node.args:
                continue
            if contains_t(node):
                continue
            for arg in node.args[:2]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.strip():
                    unwrapped.append((rel, node.lineno, arg.value))
    return literals, unwrapped


def collect_chrome(window, maps, literal_locations):
    """Every available plugin widget label/title/tooltip and related actions."""
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (
        QAbstractButton, QComboBox, QDockWidget, QGroupBox, QLabel,
        QLineEdit, QTabWidget, QWidget,
    )
    root = window._arquitetura_parametrica_master_dock
    results = []
    seen = set()

    def add(text, owner):
        if isinstance(text, str) and text.strip():
            key = (text, owner)
            if key not in seen:
                seen.add(key)
                results.append({"text": text, "widget": owner})

    for widget in [root, *root.findChildren(QWidget)]:
        label = type(widget).__name__
        if isinstance(widget, QLabel):
            add(widget.text(), f"{label}.text")
        if isinstance(widget, QAbstractButton):
            add(widget.text(), f"{label}.text")
        if isinstance(widget, QGroupBox):
            add(widget.title(), f"{label}.title")
        if isinstance(widget, QDockWidget):
            add(widget.windowTitle(), f"{label}.windowTitle")
        if isinstance(widget, QLineEdit):
            add(widget.placeholderText(), f"{label}.placeholder")
        if isinstance(widget, QComboBox) and not widget.isEditable():
            for n in range(widget.count()):
                add(widget.itemText(n), f"{label}.item[{n}]")
        if isinstance(widget, QTabWidget):
            for n in range(widget.count()):
                add(widget.tabText(n), f"{label}.tab[{n}]")
        add(widget.toolTip(), f"{label}.toolTip")
        add(widget.windowTitle(), f"{label}.windowTitle")

    # Actions can be window-owned even when rendered in an OpenTrace toolbar
    # or in the host's 'Architecture tools' submenu. Include all actions that
    # have a literal or translated string coming from the plugin sources.
    known = set(literal_locations)
    known.update(maps["en"])
    known.update(maps["es"])
    known.update(maps["en"].values())
    known.update(maps["es"].values())
    actions = list(root.findChildren(QAction))
    for action in window.findChildren(QAction):
        if action.text() in known or action.toolTip() in known:
            actions.append(action)
    for action in actions:
        add(action.text(), "QAction.text")
        add(action.toolTip(), "QAction.toolTip")
    return results


def inspect_locale(lang):
    """Child process: a real MainWindow and real plugin (no translate_widget)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from core.i18n import set_language
    from views.main_window import MainWindow
    from views.extension_api import ExtensionApp
    from OpenTrace_BIM import setup
    from OpenTrace_BIM.i18n import MISSING, language, ui_locale

    qt = QApplication.instance() or QApplication([])
    window = MainWindow(defer_extensions=True)
    try:
        set_language(lang)
        # Explicit, test-only setup switch. Host extension discovery is still
        # exercised, with the real Qt document and actions.
        setup(ExtensionApp(window, "OpenTrace_BIM"), translate_widgets=False)
        window.load_extensions()
        qt.processEvents()
        if language() != lang:
            raise AssertionError(f"Host locale {lang} resolved to {language()}")
        maps = catalogs()
        locations, _ = source_inventory()
        chrome = collect_chrome(window, maps, locations)
        portuguese = set(maps["en"]) | set(maps["es"])
        english_values = set(maps["en"].values()) - portuguese
        issues = []
        for item in chrome:
            value = item["text"]
            reasons = []
            if lang in ("en", "es"):
                target = maps[lang]
                if value in portuguese and value in target and value != target[value]:
                    reasons.append("Portuguese source left untranslated")
                if value in portuguese and value not in target:
                    reasons.append("Missing exact catalog translation")
                forbidden = PORTUGUESE_IN_EN if lang == "en" else PORTUGUESE_IN_ES
                if any(letter in value.lower() for letter in forbidden):
                    reasons.append("Portuguese-only characters")
            elif value in english_values:
                reasons.append("English value visible in Portuguese UI")
            if reasons:
                issues.append({**item, "reason": "; ".join(reasons),
                               "source": (locations.get(value) or ["dynamic / not found"])[0]})
        return {
            "lang": lang, "visible_scanned": len(chrome),
            "failed": len(issues), "issues": issues,
            "missing_at_runtime": sorted(source for locale, source in MISSING
                                         if locale == lang),
            "locale": ui_locale().name(),
        }
    finally:
        window.deleteLater()
        qt.processEvents()


def report(results):
    locations, raw_sites = source_inventory()
    count_by_file = Counter(path for path, line, text in raw_sites)
    maps = catalogs()
    # The standalone catalog generator supplies a transparent list of
    # context-sensitive phrase pieces that are intentionally excluded.
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location("opentrace_i18n_builder",
                                  ROOT / "scripts" / "build_i18n_catalogs.py")
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    original = builder.legacy_dictionaries()
    merged = {}
    for name in builder.PRIORITY_LOW_TO_HIGH:
        merged.update(original[name])
    excluded = {k: v for k, v in merged.items() if not builder.is_safe_key(k)}
    lines = [
        "# OpenTrace BIM — T1 interface translation audit",
        "",
        "Report-only in T1. Locale-specific widget rewriting was disabled.",
        "Full enforcement belongs to T2 after the interface branches merge.",
        "",
        "## Summary",
        "",
        "| Locale | Examined chrome | Failed visible strings | Missing `t()` translations | QLocale |",
        "|---|---:|---:|---:|---|",
    ]
    for item in results:
        lines.append(f'| {item["lang"]} | {item["visible_scanned"]} | '
                     f'{item["failed"]} | {len(item["missing_at_runtime"])} | '
                     f'{item["locale"]} |')
    lines += ["", "## Raw visible-string creation calls (without t()) by file",
              "", "| File | Count |", "|---|---:|"]
    for path, count in sorted(count_by_file.items()):
        lines.append(f"| `{path}` | {count} |")
    lines += ["", f"Total static call sites: **{len(raw_sites)}**.", "",
              "## Failed visible strings, source location and widget", ""]
    for item in results:
        lines += [f'### {item["lang"]} — {item["failed"]} issues', ""]
        for finding in item["issues"]:
            lines.append(f'- `{finding["source"]}` · {finding["widget"]}: '
                         f'{finding["text"]!r} — {finding["reason"]}')
        lines += ["", "### Missing t() lookups during startup", ""]
        for missing in item["missing_at_runtime"]:
            source = (locations.get(missing) or ["dynamic / not found"])[0]
            lines.append(f"- `{source}`: {missing!r}")
        lines.append("")
    lines += ["## Legacy translations that may change meaning", "",
              "These were deliberately withheld from the new JSON catalog "
              "because they are context-dependent fragments, not complete UI messages.",
              ""]
    for key, value in sorted(excluded.items()):
        lines.append(f"- {key!r} → {value!r}")
    lines += ["", "`_PHRASE_EN` substitutions are not included in either JSON catalog. "
              "They can combine words with the wrong grammatical context.",
              "",
              "### Duplicate precedence review", ""]
    for key in sorted(set().union(*(set(original[n]) for n in builder.PRIORITY_LOW_TO_HIGH))):
        values = [original[n][key] for n in builder.PRIORITY_LOW_TO_HIGH
                  if key in original[n]]
        if len(set(values)) > 1:
            lines.append(f"- {key!r}: {values!r}; final (legacy) = {merged[key]!r}")
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return len(raw_sites)


class HostTranslationCoverageTests(unittest.TestCase):
    def test_audit_produces_report(self):
        results = []
        for lang in LANGUAGES:
            command = [sys.executable, str(Path(__file__).resolve()),
                       "--audit-child", lang]
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            finished = subprocess.run(command, env=env, cwd=str(ROOT),
                                      capture_output=True, text=True, timeout=120)
            self.assertEqual(finished.returncode, 0,
                             f"{lang} audit child error:\n{finished.stderr[-3500:]}\n"
                             f"{finished.stdout[-1200:]}")
            payload = [line[len(MARKER):] for line in finished.stdout.splitlines()
                       if line.startswith(MARKER)]
            self.assertEqual(len(payload), 1, finished.stdout[-1200:])
            results.append(json.loads(payload[0]))
        static_count = report(results)
        self.assertTrue(REPORT.is_file())
        print("T1 i18n audit:", [(r["lang"], r["failed"],
                                   len(r["missing_at_runtime"])) for r in results],
              "unwrapped sites:", static_count, flush=True)

    @unittest.expectedFailure
    def test_coverage_is_report_only_until_t2(self):
        self.assertTrue(REPORT.is_file())
        self.fail("T1 coverage is intentionally non-blocking; see i18n_report.md")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--audit-child":
        print(MARKER + json.dumps(inspect_locale(sys.argv[2]), ensure_ascii=False))
    else:
        unittest.main()
