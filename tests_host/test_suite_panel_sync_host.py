# SPDX-License-Identifier: GPL-3.0-or-later
"""Host sidebar navigation, Home sections and a single shared Qt window."""
import os
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QToolButton

from views.extension_api import ExtensionApp
from views.main_window import MainWindow
from OpenTrace_BIM import setup
from OpenTrace_BIM.host import activate_select, activate_tool
from OpenTrace_BIM.suite_panel import HOME_SECTIONS
from OpenTrace_BIM.i18n import t


class SuiteContextSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.qt=QApplication.instance() or QApplication([])
        cls.window=MainWindow()
        cls.app=ExtensionApp(cls.window,"OpenTrace_BIM")
        setup(cls.app)
        cls.suite=cls.window._arquitetura_parametrica_suite_panel

    @classmethod
    def tearDownClass(cls):
        cls.window.deleteLater()
        cls.qt.processEvents()

    def setUp(self):
        activate_select(self.app)
        self.suite._context_signature=None
        self.suite._navigation_explicit=False
        self.suite.navigation_pin.setChecked(False)
        self.suite.show_page("home",show_dock=False)
        self.suite._run_sync_context()

    def test_home_and_profiles_stay_open_while_a_wall_stays_selected(self):
        from PySide6.QtGui import QVector3D
        from OpenTrace_BIM.model import DEFAULTS, make_wall_segment
        window=self.window
        ctl = window._arquitetura_parametrica_controller
        suite = window._arquitetura_parametrica_suite_panel
        scene = window.viewport.scene
        self.assertIn("profiles", suite.pages)

        def select(wall):
            scene.selection.clear()
            scene.selection.add(wall)
            scene.version += 1
            ctl._state_key = None
            ctl.refresh()
            self.assertIs(ctl.target, wall)

        def sync_like_the_document_does():
            """Every document change queues one sync; run it in place.

            No event loop here: spinning it paints the GL viewport, which
            the offscreen platform cannot do (segfault on CI).
            """
            scene.version += 1
            suite.schedule_sync_context()
            suite._run_sync_context()

        def new_wall(y):
            wall = make_wall_segment(QVector3D(0, y, 0), QVector3D(5, y, 0),
                                     dict(DEFAULTS, length=5.0))
            scene.groups.append(wall)
            return wall

        wall_a, wall_b = new_wall(0), new_wall(3)

        # A new selection is followed once: the wall page opens.
        select(wall_a)
        suite._run_sync_context()
        self.assertIs(suite.stack.currentWidget(), suite.pages["wall"])

        # Home and Profiles are the user's choice; the wall stays selected
        # and the document keeps changing, but the page must not move.
        for key in ("home", "profiles"):
            suite.buttons[key].click()
            self.assertIs(suite.stack.currentWidget(), suite.pages[key])
            for _ in range(3):
                sync_like_the_document_does()
                self.assertIs(suite.stack.currentWidget(), suite.pages[key],
                              f"{key} page was thrown back to another page")
            suite.sync_context()
            self.assertIs(suite.stack.currentWidget(), suite.pages[key])

        # A different selection is a new context and is still followed.
        select(wall_b)
        suite._run_sync_context()
        self.assertIs(suite.stack.currentWidget(), suite.pages["wall"])

    def test_door_has_independent_live_creation_and_separate_edit_page(self):
        from OpenTrace_BIM.door_window_core import DOOR_FAMILIES
        wall = self.window._arquitetura_parametrica_controller
        tool = wall.openings.door_tool
        original = dict(tool.sizes["door"])
        original_anchor = tool.anchor
        try:
            activate_tool(self.app, "opentrace_wall_door_tool")
            self.suite.show_page("door", show_dock=False)
            self.assertIs(self.suite.stack.currentWidget(), self.suite.pages["door"])
            self.assertIsNot(self.suite.pages["door"], self.suite.pages["wall"])
            field = self.suite._door_create_fields["width"]
            field.setValue(0.90)
            self.assertAlmostEqual(tool.sizes["door"]["width"], 0.90)
            offsets = DOOR_FAMILIES["swing_single"]["clearances"]
            self.assertTrue(self.suite._door_rough_width.isReadOnly())
            self.assertAlmostEqual(self.suite._door_rough_width.value(),
                                   0.90 + offsets["left"] + offsets["right"])
            self.suite._door_anchor_buttons["right"].click()
            self.assertEqual(tool.anchor, "right")
            self.assertIs(self.app.viewport.active_tool, tool)
            unavailable = self.suite.pages["door"].findChild(
                QToolButton, "opentrace_door_free_disabled")
            self.assertIsNotNone(unavailable)
            self.assertFalse(unavailable.isEnabled())
            self.suite.show_page("door_edit", show_dock=False)
            self.assertIs(self.suite.stack.currentWidget(), self.suite.pages["door_edit"])
            self.assertIsNotNone(self.suite.pages["door_edit"].findChild(
                type(self.suite.sidebar_brand), "opentrace_door_edit_pending"))
        finally:
            tool.sizes["door"].update(original)
            tool.anchor = original_anchor
            self.suite._sync_door_editor()
            activate_select(self.app)

    def test_door_tool_opens_its_own_creation_page(self):
        activate_tool(self.app, "opentrace_wall_door_tool")
        self.suite._run_sync_context()
        self.assertIs(self.suite.stack.currentWidget(), self.suite.pages["door"])
        self.assertIsNot(self.suite.stack.currentWidget(), self.suite.pages["wall"])
        self.assertIs(self.app.viewport.active_tool,
                      self.window._arquitetura_parametrica_controller.openings.door_tool)

    def test_bim_project_arrange_do_not_block_new_selection(self):
        from PySide6.QtGui import QVector3D
        from OpenTrace_BIM.model import DEFAULTS, make_wall_segment

        suite = self.suite
        scene = self.app.scene
        wall_ctrl = self.window._arquitetura_parametrica_controller
        wall_a = make_wall_segment(QVector3D(0, 20, 0), QVector3D(3, 20, 0),
                                   dict(DEFAULTS, length=3.0))
        wall_b = make_wall_segment(QVector3D(0, 23, 0), QVector3D(3, 23, 0),
                                   dict(DEFAULTS, length=3.0))
        scene.groups.extend((wall_a, wall_b))
        try:
            def select(group):
                scene.selection.clear()
                scene.selection.add(group)
                scene.version += 1
                wall_ctrl._state_key = None
                wall_ctrl.refresh()
                suite._run_sync_context()

            activate_select(self.app)
            select(wall_a)
            self.assertIs(suite.stack.currentWidget(), suite.pages["wall"])
            for key in ("bim", "project", "arrange"):
                with self.subTest(page=key):
                    if key == "arrange":
                        suite.open_arrange()
                    else:
                        suite.user_show_page(key)
                    self.assertIs(suite.stack.currentWidget(), suite.pages[key])
                    select(wall_b if key != "project" else wall_a)
                    # The same selection keeps an explicit manual page, but
                    # a distinct selection must follow its actual editor.
                    if key == "project":
                        self.assertIs(suite.stack.currentWidget(), suite.pages[key])
                        select(wall_b)
                    self.assertIs(suite.stack.currentWidget(), suite.pages["wall"])
                    # Reestablish another signature for the next iteration.
                    select(wall_a)
            suite.user_show_page("project")
            suite.navigation_pin.click()
            self.assertTrue(suite.navigation_pin.isChecked())
            select(wall_b)
            self.assertIs(suite.stack.currentWidget(), suite.pages["project"])
            suite.navigation_pin.click()
            suite._run_sync_context()
            self.assertFalse(suite.navigation_pin.isChecked())
            self.assertIs(suite.stack.currentWidget(), suite.pages["wall"])
            self.assertIsNot(self.app.viewport.active_tool, wall_ctrl.draw_tool)
        finally:
            suite.navigation_pin.setChecked(False)
            scene.selection.clear()
            for wall in (wall_a, wall_b):
                scene.groups.remove(wall)
            scene.version += 1
            wall_ctrl._state_key = None
            wall_ctrl.refresh()
            suite._context_signature = None

    def test_home_shows_settings_and_project_only(self):
        section_names=list(self.suite._home_sections)
        self.assertEqual(section_names,["Configurações","Projeto e organização"])
        settings=self.suite._home_sections["Configurações"]
        project=self.suite._home_sections["Projeto e organização"]
        self.assertTrue(settings[1].isChecked())
        self.assertFalse(project[1].isChecked())
        self.assertEqual(settings[0].objectName(),"opentrace_section_open")
        self.assertEqual(project[0].objectName(),"opentrace_home_section")
        self.assertIs(self.suite.summary.parentWidget(),project[2])
        self.assertTrue(project[2].isHidden())
        self.assertEqual(self.suite.home.findChildren(QToolButton, "opentrace_home_wall")[0].text(),t("Parede"))
        from PySide6.QtWidgets import QLabel
        labels=[x.text() for x in self.suite.home.findChildren(QLabel)]
        self.assertNotIn("Criar elementos", labels)

    def test_home_hides_sections_without_page(self):
        self.assertEqual([item["title"] for item in HOME_SECTIONS],
                         ["Plantas","Vistas","Configurações","Projeto e organização"])
        self.assertIsNone(HOME_SECTIONS[0]["page"])
        self.assertIsNone(HOME_SECTIONS[1]["page"])
        self.assertNotIn("Plantas",self.suite._home_sections)
        self.assertNotIn("Vistas",self.suite._home_sections)
        # Build a separate Home after enabling a previously hidden page.
        definition=HOME_SECTIONS[0]
        saved=dict(self.suite._home_sections)
        previous=(self.suite.summary,self.suite.intersections,
                  self.suite.update_status,self.suite.auto_update_check,
                  self.suite.update_button,self.suite.update_manager)
        try:
            definition["page"]="wall"
            temporary=self.suite._make_home()
            self.assertIn("Plantas",self.suite._home_sections)
            self.assertTrue(temporary.findChildren(QToolButton))
        finally:
            definition["page"]=None
            temporary.deleteLater()
            self.suite._home_sections=saved
            (self.suite.summary,self.suite.intersections,
             self.suite.update_status,self.suite.auto_update_check,
             self.suite.update_button,self.suite.update_manager)=previous

    def test_palette_never_activates_a_tool(self):
        initial=self.window.viewport.active_tool
        for key in self.suite.buttons:
            with self.subTest(page=key):
                self.suite.buttons[key].click()
                self.assertIs(self.window.viewport.active_tool,initial)
        self.suite.show_page("home")
        for button in self.suite.home.findChildren(QToolButton):
            if not button.objectName().startswith("opentrace_home_"):
                continue
            with self.subTest(button=button.objectName()):
                button.click()
                self.assertIs(self.window.viewport.active_tool,initial)

    def test_mode_buttons_disabled_without_their_tool(self):
        from PySide6.QtGui import QAction
        mode=QToolButton(self.suite.panel)
        action=QAction("Mode check",mode)
        triggered=[]
        action.triggered.connect(lambda _=False:triggered.append(True))
        self.suite._mode_buttons["wall"]=[mode]
        try:
            self.suite.sync_mode_buttons()
            self.assertFalse(mode.isEnabled())
            self.assertEqual(mode.toolTip(),t("Ative a ferramenta na fileira do topo."))
            self.suite._trigger_mode("wall",action,0)
            self.assertEqual(triggered,[])
        finally:
            del self.suite._mode_buttons["wall"]
            mode.deleteLater()

    def test_active_tool_opens_its_settings_on_top(self):
        activate_tool(self.app,"opentrace_wall_opening_tool")
        self.suite._run_sync_context()
        self.assertIs(self.suite.stack.currentWidget(),self.suite.pages["wall"])
        section,toggle=self.suite._opening_section
        self.assertFalse(section.isHidden())
        self.assertTrue(toggle.isChecked())
        self.assertEqual(section.objectName(),"opentrace_section_open")
        self.assertTrue(self.suite._property_sections["wall"].isChecked())

    def test_palette_and_bar_share_opening_sizes(self):
        activate_tool(self.app,"opentrace_wall_opening_tool")
        opening=self.window._arquitetura_parametrica_controller.openings.opening_tool
        opening.set_shape("rect")
        self.suite._run_sync_context()
        self.assertIs(self.suite.stack.currentWidget(),self.suite.pages["wall"])
        field=self.suite._opening_size_fields["width"]
        bar=self.window._arquitetura_parametrica_overlay_dock.bar
        mirror=next(spin for spin,title,tool,kind,key in bar._size_controls
                    if tool is opening.place and kind()=="rect" and key=="width")
        original=opening.place.sizes["rect"]["width"]
        try:
            field.setValue(original+0.25)
            self.assertAlmostEqual(opening.place.sizes["rect"]["width"],original+0.25)
            self.assertAlmostEqual(mirror.value(),original+0.25)
            mirror.setValue(original+0.45)
            self.suite._sync_opening_section()
            self.assertAlmostEqual(field.value(),original+0.45)
        finally:
            field.setValue(original)


if __name__ == "__main__":
    unittest.main()
