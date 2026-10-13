# SPDX-License-Identifier: GPL-3.0-or-later
"""Installed-package discovery smoke test on the actual IngeTrazo host."""
from pathlib import Path
import shutil
import tempfile
import unittest


class InstallationSmokeTests(unittest.TestCase):
    def test_host_discovers_extracted_opentrace_bim_folder(self):
        from core.extensions import discover_plugins

        root = Path(__file__).resolve().parents[1] / "OpenTrace_BIM"
        self.assertTrue((root / "__init__.py").is_file())
        with tempfile.TemporaryDirectory() as td:
            archive_root = Path(td)
            shutil.copytree(root, archive_root / "OpenTrace_BIM",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            # This is precisely the directory IngeTrazo reads once the
            # single artifact ZIP is extracted into its plugin directory.
            plugins, errors = discover_plugins([archive_root])
            self.assertEqual(errors, [])
            named = [p for p in plugins if p.stem == "OpenTrace_BIM"]
            self.assertEqual(len(named), 1)
            self.assertTrue(callable(named[0].setup))


    def test_real_main_window_initializes_opentrace_toolbar_and_opening_editor(self):
        """Catch the 'all default plugin buttons disappeared' startup regression.

        Discovery/import alone is NOT enough: the actual setup(app) must
        construct its Qt palette and dock using a real IngeTrazo MainWindow.
        """
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from views.main_window import MainWindow
        from views.extension_api import ExtensionApp
        from OpenTrace_BIM import setup

        qt=QApplication.instance() or QApplication([])
        window=MainWindow()
        try:
            setup(ExtensionApp(window,"OpenTrace_BIM"))
            ctl=getattr(window,"_arquitetura_parametrica_controller",None)
            self.assertIsNotNone(ctl,"setup did not create wall controller")
            self.assertIsNotNone(getattr(ctl,"toolbar",None))
            button=ctl.opening_toolbar_button
            self.assertEqual(button.objectName(),"opentrace_opening_toolbar_button")
            self.assertIs(button.parent(),ctl.toolbar)
            self.assertEqual(button.defaultAction().text(),"Abertura")
            self.assertEqual(len(button.menu().actions()),4)  # rect, square, circle, free
            # Openings are not created from the wall's radial palette.
            self.assertIsNone(getattr(ctl,"opening_btn",None))
            self.assertTrue(getattr(ctl,"opening_selector",None))
            self.assertTrue(getattr(ctl,"opening_fields",None))
            self.assertIsNotNone(getattr(window,"_arquitetura_parametrica_suite_panel",None))
            # Integrated interface modules must coexist with the live opening UI.
            suite=window._arquitetura_parametrica_suite_panel
            self.assertIn("project",suite.pages)
            from PySide6.QtCore import Qt
            self.assertEqual(suite.buttons["wall"].toolButtonStyle(),Qt.ToolButtonTextUnderIcon)
            self.assertEqual(suite.buttons["wall"].accessibleName(),"Parede")
            self.assertEqual(window._arquitetura_parametrica_suite_panel.master_dock.windowTitle(),"OpenTrace BIM")
            self.assertEqual(suite.panel.findChild(
                __import__("PySide6.QtWidgets",fromlist=["QLabel"]).QLabel,
                "opentrace_sidebar_brand").text(),"OpenTrace BIM")
            self.assertEqual(len(suite._editor_sections),3)
            self.assertFalse(suite._mode_buttons.get("wall"),
                             "The sidebar must not recreate the old text mode toolbar")
            for section,editor in suite._editor_sections:
                self.assertIs(editor.parentWidget(),section.body)
                section.toggle.click()
                self.assertFalse(section.body.isVisible())
                section.toggle.click()
                self.assertTrue(section.toggle.isChecked())
            fold=suite._property_sections["wall"]
            self.assertTrue(fold.isChecked())
            fold.click()
            self.assertFalse(fold.isChecked())
            self.assertIn("▸",fold.text())
            fold.click()
            self.assertTrue(fold.isChecked())
            self.assertIn("▾",fold.text())
            self.assertEqual(suite.project_info_button.accessibleName(),"Informações do Projeto")
            self.assertEqual(suite.arrange_button.accessibleName(),"Alinhar e distribuir objetos")
            self.assertEqual(suite.help_button.accessibleName(),"Ajuda OpenTrace BIM")
            suite.open_help()
            self.assertEqual(suite._help_dialog.chapters.currentRow(),0)
            self.assertIn("O que há de novo",suite._help_dialog.article.toPlainText())
            suite.open_help("opening_edit")
            self.assertIn("Aberturas e esquadrias",suite._help_dialog.article.toPlainText())
            suite._help_dialog.close()
            old_tool=window.viewport.active_tool
            suite.project_info_button.click()
            self.assertIs(suite.stack.currentWidget(),suite.pages["project"])
            self.assertIs(window.viewport.active_tool,old_tool)
            from unittest.mock import patch
            with patch("PySide6.QtWidgets.QMessageBox.warning",
                       side_effect=AssertionError("Arrange palette failed to open")):
                suite.open_arrange()
            self.assertIsNotNone(suite._arrange_panel)
            self.assertEqual(suite._arrange_panel.axis.count(),3)
            self.assertIn("arrange",suite.pages)
            self.assertIs(suite.stack.currentWidget(),suite.pages["arrange"])
            self.assertIsNone(suite._arrange_dock,"XYZ must use the existing sidebar, not open a second dock")
            bim=window._arquitetura_parametrica_bim_controller
            for part in ("project_identity_section","project_people_section","project_structure_section"):
                self.assertIsNotNone(getattr(bim,part,None))
            self.assertIs(window.viewport.active_tool,old_tool)
            # The organized menus REUSE the existing opening creation actions.
            creation=suite.workspace_menus["create"]
            organizer=suite.workspace_menus["organize"]
            self.assertEqual(creation.title(),"Criar")
            self.assertEqual(organizer.title(),"Organizar e inspecionar")
            voids=creation.findChild(
                __import__("PySide6.QtWidgets",fromlist=["QMenu"]).QMenu,
                "opentrace_workspace_openings")
            self.assertIsNotNone(voids)
            for action in ctl.opening_toolbar_menu.actions():
                self.assertIn(action,voids.actions())
            self.assertEqual(
                [a.text() for a in creation.actions() if a.menu()],
                ["Paredes","Elementos estruturais","Vãos e esquadrias"])
            suite.show_page("wall")
            self.assertIs(suite.stack.currentWidget(),suite.pages["wall"])
            self.assertIs(window.viewport.active_tool,old_tool)
            # B3b is not a static row of duplicated modelling actions:
            # a single toolbar changes its real method controls per tool.
            bar = suite.context_bar
            self.assertEqual(bar.objectName(),"opentrace_contextual_bar")
            self.assertIs(bar.parent(),ctl.toolbar)
            self.assertTrue(window.toolBarBreak(ctl.toolbar),
                            "Context Info Box must have its OWN row below native tools")
            self.assertIn("wall",bar.pages)
            self.assertIn("slab",bar.pages)
            self.assertIn("opening_edit",bar.pages)
            self.assertIn("polygon_edit",bar.pages)
            self.assertEqual(len([k for k in bar.pages if k.endswith("_edit") and k.startswith(("door","window"))]),0)
            self.assertEqual(bar._context_key(),"idle")
            self.assertEqual(
                [ctl.toolbar.widgetForAction(a) for a in ctl.toolbar.actions()
                 if a.isVisible()],
                [bar])
            ctl.action.trigger()
            bar.refresh()
            self.assertEqual(bar._context_key(),"wall")
            bar._wall_mode("rect_diagonal")
            self.assertEqual(ctl.tool.mode,"rect_diagonal")
            bar.refresh()
            self.assertTrue(any(btn.isChecked() for btn,_ in bar._mode_controls))
            mirror=next(w for w,source in bar._mirrors
                        if source is ctl.fields["thickness"])
            ctl.fields["thickness"].setValue(0.34)
            bar.refresh()
            self.assertAlmostEqual(mirror.value(),0.34)
            mirror.setValue(0.29)
            self.assertAlmostEqual(ctl.fields["thickness"].value(),0.29)
            bar.toggle_collapsed()
            self.assertFalse(bar.stack.isVisible())
            self.assertEqual(bar._context_key(),"wall")
            bar.toggle_collapsed()
            self.assertTrue(bar.stack.isVisibleTo(bar))
            ctl.begin_hosted_fill("door","left")
            bar.refresh()
            self.assertEqual(bar._context_key(),"door")
            # Existing creation and editor actions are still shared.
            self.assertIn(ctl.simple_wall_action,
                          suite.workspace_menus["create"].actions()[0].menu().actions())
        finally:
            window.deleteLater()
            qt.processEvents()


    def test_setup_after_window_is_shown_puts_the_sidebar_in_the_side_tray(self):
        """IngeTrazo 0.5.8 runs setup(app) once the window is on screen.

        The app starts with MainWindow(defer_extensions=True) and loads the
        extensions afterwards; the panel must still become one tab of the
        side tray, registered under the stable dock name, and open on demand.
        """
        import os
        os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
        from PySide6.QtWidgets import QApplication
        from views.main_window import MainWindow
        from views.extension_api import ExtensionApp
        from OpenTrace_BIM import setup

        qt=QApplication.instance() or QApplication([])
        window=MainWindow(defer_extensions=True)
        try:
            window.show()
            qt.processEvents()
            setup(ExtensionApp(window,"OpenTrace_BIM"))
            suite=window._arquitetura_parametrica_suite_panel
            dock=window.extension_panels().get("extension_OpenTrace_BIM_parametric_architecture")
            self.assertIsNotNone(dock,"the sidebar is not registered as an extension panel")
            self.assertIs(dock,suite.master_dock)
            self.assertIs(dock.widget(),suite.panel)
            self.assertTrue(dock.isHidden(),"the sidebar must start closed")
            suite.show_page("wall")
            self.assertFalse(dock.isHidden())
            self.assertIs(suite.stack.currentWidget(),suite.pages["wall"])
        finally:
            window.deleteLater()
            qt.processEvents()


    def test_live_qt_opening_editor_updates_correct_wall_void(self):
        """Real Qt signal: selecting B and editing width must not modify A."""
        import os
        os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
        from PySide6.QtGui import QVector3D
        from PySide6.QtWidgets import QApplication
        from views.main_window import MainWindow
        from views.extension_api import ExtensionApp
        from OpenTrace_BIM import setup
        from OpenTrace_BIM.model import DEFAULTS, make_wall_segment, read_wall

        qt=QApplication.instance() or QApplication([])
        window=MainWindow()
        try:
            setup(ExtensionApp(window,"OpenTrace_BIM"))
            ctl=window._arquitetura_parametrica_controller
            scene=window.viewport.scene
            wall=make_wall_segment(QVector3D(0,0,0),QVector3D(5,0,0),
                dict(DEFAULTS,length=5.0,openings=[
                    {"id":"edit-A","position":1.0,"width":.7,
                     "sill":.7,"height":1.2},
                    {"id":"edit-B","position":3.5,"width":.7,
                     "sill":.8,"height":1.1}]))
            scene.groups.append(wall)
            scene.selection.add(wall)
            scene.version+=1
            ctl._state_key=None
            ctl.refresh()
            self.assertIs(ctl.target,wall)
            self.assertEqual(ctl.opening_selector.count(),2)
            self.assertEqual(ctl._fields_opening_id,"edit-A")
            ctl.opening_selector.setCurrentIndex(1)
            self.assertEqual(ctl._fields_opening_id,"edit-B")
            self.assertAlmostEqual(ctl.opening_fields["width"].value(),.7)
            ctl.opening_fields["width"].setValue(.9)
            model=read_wall(wall)
            self.assertAlmostEqual(model["openings"][0]["width"],.7)
            self.assertAlmostEqual(model["openings"][1]["width"],.9)
            self.assertAlmostEqual(model["openings"][1]["sill"],.8)
            self.assertAlmostEqual(model["openings"][1]["height"],1.1)
            # A: a second/third change still addresses B after the first
            # scene-version invalidation; the contextual field writes through
            # the same controller (no duplicate opening state).
            suite=window._arquitetura_parametrica_suite_panel
            bar=suite.context_bar
            bar._key=None
            # Selection by the actual opening combobox sets the wall/ID pair.
            self.assertEqual(ctl._active_opening_id,"edit-B")
            scene.version+=1
            ctl._state_key=None
            ctl.refresh()
            self.assertEqual(ctl._fields_opening_id,"edit-B")
            ctl.opening_fields["width"].setValue(1.0)
            ctl.opening_fields["width"].setValue(1.1)
            model=read_wall(wall)
            self.assertAlmostEqual(model["openings"][0]["width"],.7)
            self.assertAlmostEqual(model["openings"][1]["width"],1.1)
            # Switching from the list to the Info Box does not implicitly
            # select another void; source field still owns EditWall/history.
            bar.refresh()
            self.assertEqual(bar._context_key(),"opening_edit")
            self.assertIs(bar.stack.currentWidget(),bar.pages["opening_edit"][0])
            quick=next(w for w,source in bar._mirrors
                       if source is ctl.opening_fields["width"])
            self.assertAlmostEqual(quick.value(),1.1)
            quick.setValue(1.2)
            self.assertAlmostEqual(read_wall(wall)["openings"][0]["width"],.7)
            self.assertAlmostEqual(read_wall(wall)["openings"][1]["width"],1.2)
            # Failed history execution must retain the controller's selected ID.
            from unittest.mock import patch
            before=ctl._active_opening_id
            with patch.object(window.viewport.history,"execute",
                              side_effect=ValueError("reject deletion")):
                ctl.delete_wall_opening()
            self.assertEqual(ctl._active_opening_id,before)
            self.assertEqual(len(read_wall(wall)["openings"]),2)
        finally:
            window.deleteLater()
            qt.processEvents()


if __name__ == "__main__":
    unittest.main()
