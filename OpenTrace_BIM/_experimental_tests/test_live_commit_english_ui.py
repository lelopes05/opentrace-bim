"""Static wiring contracts for Qt-less experimental CI.

These tests verify that direct widget signals reach the existing native
commands. They cannot substitute for a real IngeTrazo Windows UI test.
"""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]

def code(name):
    s = (ROOT / name).read_text(encoding='utf-8')
    ast.parse(s, filename=name)
    return s


class LiveCommitAndEnglishUITests(unittest.TestCase):
    def test_wall_edge_painting_waits_for_its_local_apply(self):
        s=code('ui.py')
        self.assertIn('choice.currentIndexChanged.connect(self.edge_finishes_changed)',s)
        self.assertIn('self.edge_apply_button.clicked.connect(self.apply_edge_finishes)',s)
        stage=s[s.index('def edge_finishes_changed'):s.index('def apply_edge_finishes')]
        self.assertNotIn('history.execute(',stage)
        apply=s[s.index('def apply_edge_finishes'):s.index('def defaults_changed')]
        self.assertIn('self.app.viewport.history.execute(cmd)',apply)
        self.assertIn('self.app.viewport.notify_scene_changed()',apply)

    def test_wall_edits_use_native_command_without_apply(self):
        s=code('ui.py')
        self.assertIn('self.apply_changes()',s[s.index('def defaults_changed'):s.index('def preview_length')])
        self.assertIn('EditWall(scene, self.target, values)',s)
        self.assertIn('field.setKeyboardTracking(False)',s)

    def test_common_ifc_selection_commits_directly(self):
        s=code('object_properties.py')
        self.assertIn('self.predefined.activated.connect(self.apply_ifc)',s)
        self.assertIn('self.system.editingFinished.connect(self.apply_ifc)',s)
        self.assertIn('self.code.editingFinished.connect(self.apply_ifc)',s)
        self.assertIn('self.apply_ifc()  # library selection',s)
        self.assertNotIn('QPushButton(t("Aplicar propriedades IFC"))',s)
        self.assertIn('if meta != previous:',s)

    def test_bim_fields_commit_on_finish_or_selection(self):
        s=code('bim_ui.py')
        self.assertIn('field.editingFinished.connect(self.apply_selected_metadata)',s)
        self.assertIn('combo.activated.connect(self.apply_selected_metadata)',s)
        self.assertIn('if meta != ifc_identity_data(group):',s)
        self.assertNotIn('QPushButton("Apply BIM data',s)

    def test_advanced_semantic_edits_commit_without_apply(self):
        s=code('bim_advanced_ui.py')
        self.assertIn('self.class_combo.activated.connect(self.apply_semantics)',s)
        self.assertIn('self.predef_combo.activated.connect(self.apply_semantics)',s)
        self.assertIn('self.long_name.editingFinished.connect(self.apply_semantics)',s)
        self.assertIn('self.object_type.editingFinished.connect(self.apply_semantics)',s)
        self.assertIn('if meta != ifc_identity_data(g):',s)

    def test_pset_and_ifc_appearance_commit_without_apply(self):
        s=code('bim_advanced_ui.py')
        self.assertIn('self.pset_table.itemChanged.connect(self._pset_item_changed)',s)
        self.assertIn('not getattr(self, "_loading_pset", False)',s)
        self.assertIn('self.opacity.editingFinished.connect(self.apply_style)',s)
        self.assertIn('self.apply_style()',s[s.index('def choose_color'):s.index('def _style')])
        self.assertNotIn('QPushButton(\'Apply IFC appearance',s)

    def test_georeference_follows_confirmed_edits(self):
        s=code('bim_advanced_ui.py')
        self.assertIn('widget.editingFinished.connect(self.save_geo)',s)
        self.assertIn('"Georeferencing updates when a field is confirmed."',s)

    def test_apply_preset_is_explicit_and_separate(self):
        s=code('preset_catalog.py')
        self.assertIn('Apply preset',s)
        s2=code('bim_advanced_ui.py')
        self.assertIn('Apply saved type',s2)

    def test_open_trace_english_only_does_not_rename_objects(self):
        s=code('i18n.py')
        # English unless the user chose otherwise or IngeTrazo runs in
        # Portuguese, the source language.
        section=s[s.index('def language()'):s.index('def t(')]
        self.assertIn('_LANGUAGE = "en"',section)
        self.assertIn('_host_language() == "pt-BR"',section)
        # This is only chrome translation; no global name replacement or
        # mutation of scene/material/preset identifiers in i18n.py.
        self.assertNotIn('scene.materials.update(',s)
        self.assertNotIn('group.name =',s)

    def test_major_dialog_labels_are_english(self):
        for fn in ('project_setup_dialog.py','classification_catalogue_dialog.py',
                   'catalogue_migration_dialog.py','classification_crosswalk_editor.py',
                   'layer_combinations/__init__.py','bim_advanced_ui.py'):
            s=code(fn)
            self.assertNotIn('Usar catalogues selecteds',s)
            self.assertNotIn('Apply metadados',s)
            self.assertNotIn('Definitionsções',s)
            self.assertNotIn('EXPERIMENTAL · Migrar catalogue IFC',s)

if __name__=='__main__':unittest.main()
