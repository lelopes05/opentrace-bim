# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated real-host test of slab edit prompts."""
from types import SimpleNamespace
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D
from OpenTrace_BIM import model
from step_guide_host_fixture import OpeningGuideHostCase, APP, teardown_window


def tearDownModule():
    teardown_window()


class GuideOpening3Tests(OpeningGuideHostCase):
    def test_continuous_slab_opening_edit_announces_next_target(self):
        from OpenTrace_BIM.slab_model import DEFAULTS, make_slab
        slab = make_slab(
            [QVector3D(0, 0, 0), QVector3D(8, 0, 0),
             QVector3D(8, 6, 0), QVector3D(0, 6, 0)],
            dict(DEFAULTS),
            openings=[{
                "id": "guide-a",
                "polygon": [[2, 2, 0], [3, 2, 0],
                            [3, 3, 0], [2, 3, 0]],
                "edges": [{"type": "line"} for _ in range(4)],
            }])
        self.scene.groups.append(slab)
        self.scene.selection.add(slab)
        ctl = self.slab
        ctl._edit_slab = slab
        ctl._edit_kind = "opening_edge"
        ctl._edit_index = (0, 1)
        ctl._edit_anchor = QVector3D(3, 2.5, 0)
        ctl.begin_offset()
        self.assert_step("slab_opening.edit.offset")
        self.click((3.15, 2.5, 0))
        APP.processEvents()
        self.assertTrue(ctl.sticky.waiting)
        self.assert_step("slab_opening.edit.after")


