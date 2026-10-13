# SPDX-License-Identifier: GPL-3.0-or-later
"""The sidebar follows a NEW tool or selection and never undoes the user's page choice."""
import os
import unittest


class SuiteContextSyncTests(unittest.TestCase):
    def test_home_and_profiles_stay_open_while_a_wall_stays_selected(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QVector3D
        from PySide6.QtWidgets import QApplication
        from views.extension_api import ExtensionApp
        from views.main_window import MainWindow
        from OpenTrace_BIM import setup
        from OpenTrace_BIM.model import DEFAULTS, make_wall_segment

        qt = QApplication.instance() or QApplication([])
        window = MainWindow()
        try:
            setup(ExtensionApp(window, "OpenTrace_BIM"))
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
        finally:
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
