# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared architecture menu groups using the EXISTING creation actions.

The menus provide a discoverable workspace taxonomy without registering tools
again or touching the wall/slab/opening editing palettes.
"""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu


def install_workspace_menu(suite):
    """Attach creation and organization categories to the existing host menu.

    It is safe to call again if a panel is reconstructed; no duplicate menu
    hierarchy or extension actions are created.
    """
    wall=suite.controllers.get("wall")
    root=getattr(wall,"arch_menu",None)
    if not isinstance(root,QMenu):
        return {}
    existing=root.findChild(QMenu,"opentrace_workspace_create",)
    if existing is not None:
        return {"create":existing,"organize":root.findChild(
            QMenu,"opentrace_workspace_organize")}

    # The wall controller initially registers a minimal Parede submenu. Replace
    # ONLY this menu entry; do not delete, recreate or re-register its QActions.
    for action in tuple(root.actions()):
        sub=action.menu()
        if sub is not None and sub.title()=="Parede" and (
                getattr(wall,"simple_wall_action",None) in sub.actions()):
            root.removeAction(action)

    create=QMenu("Criar",root)
    create.setObjectName("opentrace_workspace_create")
    wall_menu=create.addMenu("Paredes")
    for attr in ("simple_wall_action","composite_wall_action","curve_action"):
        action=getattr(wall,attr,None)
        if action is not None:
            wall_menu.addAction(action)

    structural=create.addMenu("Elementos estruturais")
    for key,label in (("slab","Laje"),("column","Pilar"),("beam","Viga")):
        if suite.controllers.get(key) is not None:
            action=QAction(label,structural)
            action.setObjectName("opentrace_create_"+key)
            action.triggered.connect(
                lambda _=False,k=key:suite.user_show_page(k))
            structural.addAction(action)

    openings=create.addMenu("Vãos e esquadrias")
    openings.setObjectName("opentrace_workspace_openings")
    # The very same tool actions as the "Vãos" submenu; none are created here.
    for action in wall.openings.tool_actions:
        openings.addAction(action)

    organize=QMenu("Organizar e inspecionar",root)
    organize.setObjectName("opentrace_workspace_organize")
    for label,callback in (
        ("Informações do Projeto",lambda:suite.show_page("project")),
        ("BIM / IFC",lambda:suite.show_page("bim")),
        ("Alinhar e distribuir X/Y/Z",suite.open_arrange),
    ):
        action=QAction(label,organize)
        action.triggered.connect(lambda _=False,cb=callback:cb())
        organize.addAction(action)

    root.addMenu(create)
    root.addMenu(organize)
    return {"create":create,"organize":organize}
