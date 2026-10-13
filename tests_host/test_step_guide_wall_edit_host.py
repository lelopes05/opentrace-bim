# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated real-host test of wall edit prompts."""
from types import SimpleNamespace
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D
from OpenTrace_BIM import model
from step_guide_host_fixture import OpeningGuideHostCase, APP, teardown_window


def tearDownModule():
    teardown_window()


class GuideOpening2Tests(OpeningGuideHostCase):
    def test_continuous_wall_opening_edit_announces_next_target(self):
        from OpenTrace_BIM.wall_face import WallFace
        opening = {
            "id": "guide-a", "kind": "rect", "position": 2.5,
            "width": 1.0, "height": 1.2, "sill": 0.9,
        }
        wall = model.make_wall_segment(
            QVector3D(0, 0, 0), QVector3D(5, 0, 0),
            dict(model.DEFAULTS, length=5.0, openings=[opening]))
        self.scene.groups.append(wall)
        face = WallFace(wall)
        editor = self.wall.openings
        editor._radial_target = (
            wall, "guide-a", "edge", 1,
            face.world(QVector3D(3, 1.5, 0)))
        editor._run("offset")
        self.assert_step("wall_opening.edit.offset")
        point = face.world(QVector3D(3.2, 1.5, 0))
        self.click((point.x(), point.y(), point.z()))
        APP.processEvents()
        self.assertTrue(editor.sticky.waiting)
        self.assert_step("wall_opening.edit.after")


