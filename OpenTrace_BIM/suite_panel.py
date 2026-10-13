# SPDX-License-Identifier: GPL-3.0-or-later
"""Integrated OpenTrace BIM sidebar: compact task navigation and live editors."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QStackedWidget, QToolButton, QVBoxLayout,
    QWidget,
)

from . import __version__
from .icons import icon
from .preset_catalog import builtins
from .profile_library import load_profiles
from .i18n import t

# Home entries are ordered; a missing page suppresses its entire section.
# Keys refer to existing pages, never to modelling tool actions.
HOME_SECTIONS = (
    {"title": "Plantas", "page": None, "icon": "home", "entries": ()},
    {"title": "Vistas", "page": None, "icon": "home", "entries": ()},
    {"title": "Configurações", "page": "wall", "icon": "wall", "entries": (
        ("Parede", "wall", "wall"), ("Laje", "slab", "slab"),
        ("Pilar", "column", "column"), ("Viga", "beam", "beam"),
    )},
    {"title": "Projeto e organização", "page": "project", "icon": "bim", "entries": (
        ("Informações", "bim", "project"),
        ("Alinhar / distribuir", "move", "arrange"),
        ("Perfis complexos", "profile", "profiles"),
        ("BIM / IFC", "bim", "bim"),
    )},
)


class ArchitectureSuitePanel:
    PAGE_INFO=(
        ("home","Início","home"),("wall","Parede","wall"),
        ("slab","Laje","slab"),("column","Pilar","column"),
        ("beam","Viga","beam"),("membrane","Membrana","slab"),
        ("profiles","Perfis","profile"),("bim","BIM","bim"),
    )
    def __init__(self,app,wall=None,slab=None,column=None,beam=None,profiles=None,bim=None,membrane=None,master_dock=None):
        self.app=app;self.controllers={"wall":wall,"slab":slab,"column":column,"beam":beam,"membrane":membrane,"profiles":profiles,"bim":bim}
        self._sync_queued=False;self._last_active_tool_id=id(getattr(self.app.viewport,"active_tool",None))
        self._mode_buttons={}
        self._home_sections={}
        self._opening_size_fields={}
        self._opening_section=None
        self._property_sections={}
        self._editor_sections=[]
        self._help_dialog=None
        self._arrange_panel = None
        self._arrange_dock = None
        self.panel=QWidget();self.panel.setMinimumSize(0,0)
        # Lifecycle-owned timers: unlike unparented QTimer.singleShot, they
        # cannot invoke Python methods after a document/window is destroyed.
        self._context_timer=QTimer(self.panel)
        self._context_timer.setSingleShot(True)
        self._context_timer.timeout.connect(self._run_sync_context)
        self._auto_check_timer=QTimer(self.panel)
        self._auto_check_timer.setSingleShot(True)
        self._auto_check_timer.timeout.connect(self._auto_check_updates_on_startup)
        root=QVBoxLayout(self.panel);root.setContentsMargins(4,4,4,4);root.setSpacing(4)
        # Two-level HEADER: brand/actions above, legible horizontal page
        # tabs below. The host still owns the real QDockWidget and title.
        header=QFrame(self.panel)
        header.setObjectName("opentrace_sidebar_header")
        h=QHBoxLayout(header)
        h.setContentsMargins(9,6,8,6);h.setSpacing(6)
        brand=QLabel("OpenTrace BIM",header)
        brand.setObjectName("opentrace_sidebar_brand")
        brand.setStyleSheet("font-size:13pt; font-weight:700;")
        h.addWidget(brand);h.addStretch(1)
        self.arrange_button=QToolButton(header)
        self.arrange_button.setText("↔")
        self.arrange_button.setToolTip("Alinhar e distribuir objetos em X, Y e Z")
        self.arrange_button.setAccessibleName("Alinhar e distribuir objetos")
        self.arrange_button.setFixedSize(QSize(32,32))
        self.arrange_button.clicked.connect(self.open_arrange)
        h.addWidget(self.arrange_button)
        self.project_info_button=QToolButton(header)
        self.project_info_button.setText("ⓘ")
        self.project_info_button.setToolTip("Informações do Projeto")
        self.project_info_button.setAccessibleName("Informações do Projeto")
        self.project_info_button.setFixedSize(QSize(32,32))
        self.project_info_button.clicked.connect(lambda: self.show_page("project"))
        h.addWidget(self.project_info_button)
        self.help_button=QToolButton(header)
        self.help_button.setText("?")
        self.help_button.setFixedSize(QSize(32,32))
        self.help_button.setToolTip("Manual contextual e Sobre")
        self.help_button.setAccessibleName("Ajuda OpenTrace BIM")
        self.help_button.clicked.connect(self.open_help)
        h.addWidget(self.help_button)
        root.addWidget(header)
        self.nav=QFrame(self.panel)
        self.nav.setObjectName("opentrace_sidebar_navigation")
        navlay=QHBoxLayout(self.nav)
        navlay.setContentsMargins(0,2,0,2);navlay.setSpacing(1)
        self.group=QButtonGroup(self.panel)
        self.group.setExclusive(True)
        self.buttons={}
        for key,label,ico in self.PAGE_INFO:
            b=QToolButton(self.nav)
            b.setObjectName("opentrace_nav_"+key)
            b.setCheckable(True)
            b.setAutoRaise(True)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIcon(icon(ico))
            b.setIconSize(QSize(22,22))
            b.setMinimumSize(QSize(43,48))
            b.setText(label)
            b.setToolTip(label)
            b.setAccessibleName(label)
            b.setStyleSheet(
                "QToolButton{font-size:9px;border:0;border-bottom:2px solid transparent;}"
                "QToolButton:hover{background:palette(midlight);}"
                "QToolButton:checked{border-bottom:2px solid palette(highlight);"
                "background:palette(midlight);}")
            b.clicked.connect(lambda _=False,k=key:self.user_show_page(k))
            navlay.addWidget(b,1);self.group.addButton(b);self.buttons[key]=b
        root.addWidget(self.nav)
        self.stack=QStackedWidget();self.stack.setMinimumSize(0,0);root.addWidget(self.stack,1);self.pages={}
        self.home=self._make_home();self._add_page("home",self.home)
        # Membrane stays visible in the roadmap without loading any membrane
        # controller/tool code.  This page is informational only.
        self._add_page("membrane", self._make_membrane_notice())
        # The only dock is allocated through ExtensionApp.add_panel in setup.
        # The host owns its placement, saved tab group and left/right side.
        if master_dock is None:
            raise ValueError("OpenTrace BIM requires the host-registered master dock")
        self.master_dock=master_dock
        self.master_dock.setWidget(self.panel)
        self.master_dock.setWindowTitle("OpenTrace BIM")
        self.master_dock.hide()
        for key in ("wall","slab","column","beam","profiles","bim"):
            ctrl=self.controllers.get(key)
            if ctrl is None or not hasattr(ctrl,"panel"):continue
            page=ctrl.panel
            wrapped=self._wrap_controller_page(key,ctrl,page)
            self._add_page(key,wrapped)
            ctrl.dock=self.master_dock
        bim_ctrl=self.controllers.get("bim")
        if bim_ctrl is not None and getattr(bim_ctrl, "project_panel", None) is not None:
            self._add_page("project", bim_ctrl.project_panel)
        else:
            self.project_info_button.setEnabled(False)
        self.show_page("home",show_dock=False);self._wire();self.refresh_home();self.sync_mode_buttons()
        from .workspace_menu import install_workspace_menu
        self.workspace_menus = install_workspace_menu(self)
        # The viewport overlay creates the contextual bar with an explicit
        # overlay reference after the sidebar is ready.
        self.context_bar = None
        self._auto_check_timer.start(1800)

    def _add_page(self,key,widget):
        self.pages[key]=widget;self.stack.addWidget(widget)

    def _make_membrane_notice(self):
        w=QWidget();lay=QVBoxLayout(w);lay.setContentsMargins(12,12,12,12);lay.setSpacing(8)
        title=QLabel("<b style='font-size:14pt'>Membrana — Em avaliação</b>")
        title.setWordWrap(True);lay.addWidget(title)
        body=QLabel("Ferramenta temporariamente desativada enquanto o fluxo de modelagem é revisado.")
        body.setWordWrap(True);body.setStyleSheet("color:#666;");lay.addWidget(body)
        note=QLabel("A ferramenta experimental não está carregada nesta versão.")
        note.setWordWrap(True);lay.addWidget(note);lay.addStretch(1)
        return w

    def _make_home(self):
        """Home navigation is data-driven and never selects a host tool."""
        w=QWidget()
        lay=QVBoxLayout(w)
        lay.setContentsMargins(10,8,10,8)
        lay.setSpacing(7)
        subtitle=QLabel(t("Modelagem arquitetônica paramétrica"))
        subtitle.setStyleSheet("color:palette(mid);font-size:10pt;")
        lay.addWidget(subtitle)
        for definition in HOME_SECTIONS:
            if definition["page"] is None:
                continue
            section=QFrame(w)
            section.setObjectName("opentrace_home_section")
            section.setProperty("home_section", definition["title"])
            section_lay=QVBoxLayout(section)
            section_lay.setContentsMargins(0,0,0,0)
            section_lay.setSpacing(4)
            toggle=QToolButton(section)
            toggle.setCheckable(True)
            toggle.setChecked(definition["title"]=="Configurações")
            toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            toggle.setIcon(icon(definition["icon"]))
            toggle.setText(t(definition["title"]))
            toggle.setAccessibleName(t(definition["title"]))
            body=QWidget(section)
            grid=QGridLayout(body)
            grid.setContentsMargins(0,0,0,0)
            grid.setSpacing(5)
            for index,(title, glyph, page) in enumerate(definition["entries"]):
                button=QToolButton(body)
                button.setObjectName("opentrace_home_"+page)
                button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                button.setIcon(icon(glyph))
                button.setIconSize(QSize(25,25))
                button.setText(t(title))
                button.setToolTip(t(title))
                button.setMinimumHeight(40)
                button.setStyleSheet(
                    "QToolButton{border:1px solid palette(mid);"
                    "border-radius:5px;padding:5px;text-align:left;}"
                    "QToolButton:hover{background:palette(midlight);}")
                if page=="arrange":
                    button.clicked.connect(self.open_arrange)
                else:
                    button.clicked.connect(lambda _=False,p=page:self.user_show_page(p))
                grid.addWidget(button,index//2,index%2)
            def expand(opened, frame=section, content=body, control=toggle):
                frame.setObjectName("opentrace_section_open" if opened
                                    else "opentrace_home_section")
                content.setVisible(opened)
                control.setArrowType(Qt.DownArrow if opened else Qt.RightArrow)
                frame.style().unpolish(frame)
                frame.style().polish(frame)
            toggle.toggled.connect(expand)
            section_lay.addWidget(toggle)
            section_lay.addWidget(body)
            expand(toggle.isChecked())
            self._home_sections[definition["title"]]=(section,toggle,body)
            lay.addWidget(section)
        self.summary=QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:palette(mid);font-size:9pt;")
        project_grid=self._home_sections["Projeto e organização"][2].layout()
        project_grid.addWidget(self.summary,2,0,1,2)
        self.intersections=QLabel()
        self.intersections.setWordWrap(True)
        self.intersections.setStyleSheet("color:palette(mid);font-size:9pt;")
        project_grid.addWidget(self.intersections,3,0,1,2)

        update_box=QFrame();update_box.setFrameShape(QFrame.StyledPanel)
        update_lay=QVBoxLayout(update_box);update_lay.setContentsMargins(8,8,8,8);update_lay.setSpacing(6)
        update_lay.addWidget(QLabel(f"<b>OpenTrace BIM {__version__}</b>"))
        self.update_status=QLabel(
            "Consulta apenas o catálogo oficial. Nenhum pacote é instalado sem confirmação."
        )
        self.update_status.setWordWrap(True);self.update_status.setStyleSheet("color:#666;")
        update_lay.addWidget(self.update_status)

        self.auto_update_check=QCheckBox("Verificar atualizações automaticamente")
        self.update_button=QPushButton("Verificar atualizações")
        update_lay.addWidget(self.auto_update_check);update_lay.addWidget(self.update_button)
        project_grid.addWidget(update_box,4,0,1,2)

        self.update_manager=None
        try:
            from .updater import (
                UpdateManager, auto_check_enabled, set_auto_check_enabled,
            )
            self.update_manager=UpdateManager(w)
            self.auto_update_check.setChecked(auto_check_enabled())
            self.auto_update_check.toggled.connect(set_auto_check_enabled)
            self.auto_update_check.toggled.connect(self._auto_update_toggled)
            self.update_button.clicked.connect(
                lambda: self.update_manager.check(manual=True)
            )
        except Exception as exc:
            self.auto_update_check.setEnabled(False)
            self.update_button.setEnabled(False)
            self.update_status.setText(
                f"Updates are unavailable in this installation: {type(exc).__name__}: {exc}"
            )

        lay.addStretch(1);return w

    def _actions_for(self,key,ctrl):
        names={
            "wall":("simple_wall_action","composite_wall_action"),
            "slab":("simple_action","composite_action"),
            "column":("action",),"beam":("action",),"profiles":("action",),
        }.get(key,("action",))
        out=[]
        for name in names:
            action=getattr(ctrl,name,None)
            if action is not None and action not in out:out.append(action)
        return out

    def _organize_editor_sections(self,key,ctrl,page):
        # Organize ACTUAL editor widgets without cloning form values or
        # rewriting handlers. Only wall widgets are explicitly segmented;
        # other controllers retain their proven form/layout unchanged.
        if key!="wall":
            return
        from .panel_sections import EditorSection
        layout=page.layout()
        if layout is None:
            return
        for attr, title in (
            ("form_widget","Geometria e propriedades"),
            ("layer_editor","Composição e camadas"),
            ("opening_widget","Vãos e esquadrias"),
        ):
            widget=getattr(ctrl,attr,None)
            if widget is None: continue
            index=layout.indexOf(widget)
            if index<0: continue
            initial_hidden=widget.isHidden()
            layout.removeWidget(widget)
            section=EditorSection(title,widget,parent=page)
            section.setObjectName("opentrace_wall_section_"+attr)
            layout.insertWidget(index,section)
            widget.setVisible(not initial_hidden)
            def mark_open(opened, frame=section, original="opentrace_wall_section_"+attr):
                frame.setObjectName("opentrace_section_open" if opened else original)
            section.toggle.toggled.connect(mark_open)
            mark_open(section.toggle.isChecked())
            self._editor_sections.append((section,widget))
        self._sync_editor_sections()

    def _sync_editor_sections(self):
        for section,widget in self._editor_sections:
            # Explicit form hiding is driven by selected tool/structure;
            # collapsing the body does not mean the editor is inapplicable.
            section.setVisible(not widget.isHidden())

    def _wrap_controller_page(self,key,ctrl,page):
        wrapper=QWidget();wrapper.setMinimumSize(0,0)
        self._organize_editor_sections(key,ctrl,page)
        lay=QVBoxLayout(wrapper);lay.setContentsMargins(0,0,0,0);lay.setSpacing(4)
        # The OLD text buttons (Simple wall / Composite wall / Curved wall)
        # were a duplicate toolbar INSIDE the properties panel. Construction
        # methods now live in the ONE contextual Info Box. QActions themselves
        # remain registered, and their menu/keyboard bindings are untouched.
        # Controller forms can be tall. A scroll container prevents their size
        # hints from forcing the top-level window away from its restored size.
        page.setMinimumSize(0,0)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame);scroll.setMinimumSize(0,0);scroll.setWidget(page)
        # Do not detach/rebuild the existing editor: the section only
        # collapses its VIEW, preserving widgets, values and Undo handlers.
        toggle=QToolButton(wrapper)
        toggle.setObjectName("opentrace_properties_"+key)
        toggle.setCheckable(True)
        toggle.setChecked(True)
        toggle.setToolButtonStyle(Qt.ToolButtonTextOnly)
        toggle.setText("▾ Propriedades detalhadas")
        toggle.setToolTip("Recolher ou expandir a edição detalhada")
        toggle.setAccessibleName("Propriedades detalhadas")
        def switch_properties(expanded, sc=scroll, bt=toggle):
            sc.setVisible(expanded)
            bt.setText(("▾" if expanded else "▸")+" Propriedades detalhadas")
        toggle.toggled.connect(switch_properties)
        toggle.setStyleSheet("QToolButton{font-weight:700;text-align:left;"
                             "border:0;border-bottom:1px solid palette(mid);"
                             "padding:7px;}")
        toggle.toggled.connect(
            lambda opened, frame=wrapper: frame.setObjectName(
                "opentrace_section_open" if opened else "opentrace_properties_page"))
        wrapper.setObjectName("opentrace_section_open")
        lay.addWidget(toggle)
        if key=="wall":
            self._create_opening_section(lay, wrapper)
        lay.addWidget(scroll,1)
        self._property_sections[key]=toggle
        return wrapper

    def _opening_tool_and_kind(self):
        wall=self.controllers["wall"]
        active=self.app.viewport.active_tool
        opening=wall.openings
        if active is opening.opening_tool:
            shape=opening.opening_tool.shape
            return (opening.opening_tool.place, shape)
        if active is opening.door_tool:
            return (opening.door_tool, "door")
        if active is opening.window_tool:
            return (opening.window_tool, "window")
        return (None,None)

    def _create_opening_section(self, layout, parent):
        """Mirror the existing tool.sizes dictionaries, never copy their state."""
        section=QFrame(parent)
        section.setObjectName("opentrace_wall_opening_section")
        outer=QVBoxLayout(section)
        outer.setContentsMargins(1,3,1,3)
        toggle=QToolButton(section)
        toggle.setCheckable(True)
        toggle.setChecked(True)
        toggle.setText(t("Vão"))
        toggle.setAccessibleName(t("Vão"))
        toggle.setArrowType(Qt.DownArrow)
        body=QWidget(section)
        grid=QGridLayout(body)
        for index,(key,title) in enumerate((
            ("width","Largura"), ("height","Altura"), ("sill","Peitoril"),
        )):
            label=QLabel(t(title),body)
            field=QDoubleSpinBox(body)
            field.setObjectName("opentrace_opening_"+key)
            field.setDecimals(2)
            field.setRange(0 if key=="sill" else 0.05,100.0)
            field.setSingleStep(0.05)
            field.setSuffix(" m")
            field.setKeyboardTracking(False)
            field.valueChanged.connect(
                lambda value,k=key:self._set_opening_size(k,value))
            grid.addWidget(label,index,0)
            grid.addWidget(field,index,1)
            self._opening_size_fields[key]=field
        def expand(opened):
            body.setVisible(opened)
            section.setObjectName("opentrace_section_open" if opened
                                  else "opentrace_wall_opening_section")
            toggle.setArrowType(Qt.DownArrow if opened else Qt.RightArrow)
        toggle.toggled.connect(expand)
        outer.addWidget(toggle)
        outer.addWidget(body)
        expand(True)
        layout.addWidget(section)
        self._opening_section=(section,toggle)
        section.hide()

    def _set_opening_size(self,key,value):
        tool,kind=self._opening_tool_and_kind()
        if tool is None or kind is None or kind=="free":
            return
        tool.sizes[kind][key]=value
        if kind in ("square","circle") and key=="width":
            tool.sizes[kind]["height"]=value
        self._sync_opening_section()
        bar=self.context_bar
        if bar is not None:
            bar.refresh()
        self.app.viewport.update()

    def _sync_opening_section(self):
        if self._opening_section is None:
            return
        tool,kind=self._opening_tool_and_kind()
        section,toggle=self._opening_section
        showing=tool is not None
        section.setVisible(showing)
        if not showing:
            return
        if not toggle.isChecked():
            toggle.setChecked(True)
        for key,field in self._opening_size_fields.items():
            enabled=(kind!="free" and not
                     (key=="height" and kind in ("square","circle")))
            field.setEnabled(enabled)
            if kind!="free":
                blocked=field.blockSignals(True)
                field.setValue(tool.sizes[kind][key])
                field.blockSignals(blocked)

    def _mode_tool_active(self,key):
        active=self.app.viewport.active_tool
        ctrl=self.controllers[key]
        tool=ctrl.draw_tool if key=="wall" else ctrl.tool
        return active is tool

    def _trigger_mode(self,key,action,index):
        if not self._mode_tool_active(key):
            return
        self._set_mode_button(key,index)
        action.trigger()
        self.sync_mode_buttons()

    def _set_mode_button(self,key,index):
        for i,b in enumerate(self._mode_buttons.get(key,())):
            blocked=b.blockSignals(True);b.setChecked(i==index);b.blockSignals(blocked)

    def user_show_page(self,key):
        self.show_page(key)
        self.schedule_sync_context()

    def open_arrange(self):
        """Open XYZ organization IN the same anchorable OpenTrace sidebar.

        Previously this created a second, disconnected Qt dock. The
        inspector navigation now returns naturally to the prior modelling
        page without moving focus to another floating window.
        """
        try:
            if self._arrange_panel is None:
                from .arrange_ui import ArrangePanel
                self._arrange_panel=ArrangePanel(self.app)
                self._add_page("arrange",self._arrange_panel)
            self._arrange_panel.refresh()
            self.show_page("arrange")
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.panel,"OpenTrace BIM",
                f"Não foi possível abrir alinhamento: {type(exc).__name__}: {exc}")

    def open_help(self,context=None):
        """Show chaptered documentation, without modifying modelling tool."""
        if self._help_dialog is None:
            from .help_dialog import HelpDialog
            self._help_dialog=HelpDialog(self.app.window)
        # A regular header click starts at "O que há de novo".
        self._help_dialog.show_for_context(
            context if isinstance(context,str) else None)

    def _auto_update_toggled(self, enabled):
        if enabled and self.update_manager is not None:
            # The checkbox itself is the user's consent to perform automatic
            # catalog checks. Still, no package is downloaded without another
            # explicit confirmation.
            QTimer.singleShot(0, lambda: self.update_manager.check(manual=False))

    def _auto_check_updates_on_startup(self):
        if (
            self.update_manager is not None
            and self.auto_update_check.isChecked()
        ):
            self.update_manager.check(manual=False)

    def _wire(self):
        for key,ctrl in self.controllers.items():
            if ctrl is None:continue
            for action in self._actions_for(key,ctrl):
                try:action.triggered.connect(lambda _=False,k=key:self.show_page(k))
                except Exception:pass
        self.app.viewport.sceneVersionChanged.connect(self.schedule_sync_context)
        self.app.viewport.measurementChanged.connect(self.schedule_tool_sync_context)
        wall = self.controllers.get("wall")
        if wall is not None:
            # Toolbar, menu and keyboard all invoke the SAME host actions.
            # Update the Info Box after their tool switch, without polling
            # cursor moves or creating any parallel command registration.
            for action in (wall.action,*wall.openings.tool_actions):
                action.triggered.connect(self.schedule_sync_context)

    def schedule_sync_context(self,*_):
        if self._sync_queued:return
        self._sync_queued=True;self._context_timer.start(0)

    def schedule_tool_sync_context(self,*_):
        active_id=id(getattr(self.app.viewport,"active_tool",None))
        if active_id==self._last_active_tool_id:return
        self._last_active_tool_id=active_id;self.schedule_sync_context()

    def _run_sync_context(self):
        self._sync_queued=False;self._last_active_tool_id=id(getattr(self.app.viewport,"active_tool",None));self.sync_context();self.sync_mode_buttons()
        bar = getattr(self,"context_bar",None)
        if bar is not None:
            bar.refresh()
        self._sync_editor_sections()
        self._sync_opening_section()

    def show_page(self,key,show_dock=True):
        if key not in self.pages:key="home"
        self.stack.setCurrentWidget(self.pages[key]);b=self.buttons.get(key)
        if b is not None:
            b.setChecked(True)
        elif key in ("project","arrange"):
            # A context page without a dedicated category tab must not
            # leave the BIM or a modelling tab misleadingly selected.
            self.group.setExclusive(False)
            for button in self.buttons.values():
                button.setChecked(False)
            self.group.setExclusive(True)
        if show_dock:
            try:self.app.show_panel(self.master_dock)
            except Exception:self.master_dock.show()
        if key=="home":self.refresh_home()
        self._sync_editor_sections()
        self._sync_opening_section()
        self.sync_mode_buttons()

    def sync_mode_buttons(self):
        for key,buttons in self._mode_buttons.items():
            enabled=self._mode_tool_active(key)
            for button in buttons:
                button.setEnabled(enabled)
                button.setToolTip("" if enabled
                                  else t("Ative a ferramenta na fileira do topo."))
        wall=self.controllers.get("wall")
        if wall is not None and self._mode_buttons.get("wall"):
            kind=(getattr(getattr(wall,"structure",None),"currentData",lambda:None)() or getattr(wall,"defaults",{}).get("structure","simple"))
            self._set_mode_button("wall",1 if kind=="composite" else 0)
        slab=self.controllers.get("slab")
        if slab is not None and self._mode_buttons.get("slab"):
            kind=(getattr(getattr(slab,"structure",None),"currentData",lambda:None)() or getattr(slab,"defaults",{}).get("structure","simple"))
            self._set_mode_button("slab",1 if kind=="composite" else 0)
        for key in ("column","beam"):
            if self._mode_buttons.get(key):self._set_mode_button(key,0)

    def _show_context_settings(self,key):
        """Open the full form for a new active tool or selected object."""
        self.show_page(key)
        toggle=self._property_sections.get(key)
        if toggle is not None:
            toggle.setChecked(True)

    def sync_context(self):
        """Follow a NEW tool or selection; never undo the user's page choice.

        This runs on every document change. Re-applying the page each time
        threw the user back to the wall page whenever a wall was selected,
        so Home, Profiles and the other tabs looked dead.
        """
        active=getattr(self.app.viewport,"active_tool",None)
        signature=(id(active),)+tuple(
            id(getattr(self.controllers.get(k),"target",None))
            for k in ("wall","slab","column","beam"))
        if signature==getattr(self,"_context_signature",None):
            return
        self._context_signature=signature
        # BIM is an inspector/export workspace. Keep it open while selection or
        # metadata changes; otherwise selecting a wall would immediately throw
        # the user back to the modelling page.
        if any(self.pages.get(key) is not None and
               self.stack.currentWidget() is self.pages[key]
               for key in ("bim", "project", "arrange")):
            return
        opening_tool,opening_kind=self._opening_tool_and_kind()
        if opening_tool is not None:
            self._show_context_settings("wall")
            return
        for key in ("wall","slab","column","beam"):
            ctrl=self.controllers.get(key)
            if ctrl is None:continue
            tool=getattr(ctrl,"draw_tool",None) or getattr(ctrl,"tool",None)
            if tool is not None and active is tool:
                self._show_context_settings(key)
                return
        for key in ("beam","column","slab","wall"):
            ctrl=self.controllers.get(key)
            if ctrl is not None and getattr(ctrl,"target",None) is not None:
                self._show_context_settings(key);return

    def refresh_home(self):
        cat=builtins();counts={k:len(v) for k,v in cat.items()};profiles=load_profiles()
        built=sum(1 for p in profiles if p.get("builtin"));personal=sum(1 for p in profiles if not p.get("builtin"))
        self.summary.setText(
            f"Built-in library: {counts.get('wall',0)} walls · {counts.get('slab',0)} slabs · "
            f"{counts.get('beam',0)} beams · {counts.get('column',0)} columns · {built} catalogue profiles. "
            f"Personal profiles: {personal}."
        )
        service=getattr(self.app.window,"_layer_combinations_service",None)
        if service is None:
            self.intersections.setText("Layer Combinations: integration is available when the companion service is loaded.")
        else:
            name=service.applied_combination_name() or "current state"
            self.intersections.setText(f"Layer Combinations connected · {name}. Intersection groups control automatic wall junctions.")
