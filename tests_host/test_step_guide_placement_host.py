# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated real-host test of placement prompts."""
from types import SimpleNamespace
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D
from OpenTrace_BIM import model
from step_guide_host_fixture import OpeningGuideHostCase, APP, teardown_window


def tearDownModule():
    teardown_window()


class GuideOpening1Tests(OpeningGuideHostCase):
    def test_opening_placement_and_next_target(self):
        from OpenTrace_BIM.host import activate_tool
        from OpenTrace_BIM.wall_face import WallFace
        from OpenTrace_BIM.wall_opening_ui import OPENING_TOOL_KEY
        wall = model.make_wall_segment(
            QVector3D(0, 0, 0), QVector3D(5, 0, 0),
            dict(model.DEFAULTS, length=5.0, openings=[]))
        self.scene.groups.append(wall)
        face = WallFace(wall)
        activate_tool(self.app, OPENING_TOOL_KEY)
        self.assert_step("opening.rect.hover")
        world = face.world(QVector3D(2, 1.4, 0), "near")
        ctx = SimpleNamespace(
            viewport=self.viewport, world=world, snap=None,
            screen=QPointF(0, 0), modifiers=Qt.NoModifier)
        self.viewport.active_tool.on_hover(ctx)
        self.viewport.active_tool.on_click(ctx)
        APP.processEvents()
        self.assert_step("opening.rect.placed")
        self.assertEqual(len(model.read_wall(wall)["openings"]), 1)


