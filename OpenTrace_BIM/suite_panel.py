# SPDX-License-Identifier: GPL-3.0-or-later
"""Integrated OpenTrace BIM sidebar: compact task navigation and live editors."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QStackedWidget, QToolButton, QVBoxLayout,
    QWidget,
)

from . import __version__
from .icons import icon
from .preset_catalog import builtins
from .profile_library import load_profiles


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
        self.master_dock = master_dock or getattr(
            self.app.window, "_arquitetura_parametrica_master_dock", None)
        if self.master_dock is None:
            self.master_dock=self.app.add_panel(
                "OpenTrace BIM",self.panel,name="parametric_architecture")
        else:
            # The host already registered this dock before restoreState.  Only
            # swap its contents; do not remove/re-add/re-tabify docks after the
            # main window is shown.
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
        # Stage B3b: the EXISTING architecture toolbar now contains one
        # context-sensitive Info Box instead of an always-visible tool pile.
        from .contextual_bar import ContextualBar
        self.context_bar = ContextualBar(self)
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
        """Compact launchpad grouped by actual modeling tasks, not dead cards."""
        w=QWidget()
        lay=QVBoxLayout(w)
        lay.setContentsMargins(10,8,10,8)
        lay.setSpacing(7)
        subtitle=QLabel("Modelagem arquitetônica paramétrica")
        subtitle.setStyleSheet("color:palette(mid);font-size:10pt;")
        lay.addWidget(subtitle)

        def header(title,detail):
            line=QHBoxLayout()
            heading=QLabel(title)
            heading.setStyleSheet("font-weight:700;font-size:10pt;")
            line.addWidget(heading)
            line.addStretch()
            note=QLabel(detail)
            note.setStyleSheet("color:palette(mid);font-size:9pt;")
            line.addWidget(note)
            lay.addLayout(line)

        def options(entries):
            grid=QGridLayout()
            grid.setSpacing(5)
            for i,(label,ico,callback) in enumerate(entries):
                button=QToolButton(w)
                button.setObjectName("opentrace_home_"+str(i)+"_"+label.lower().replace(" ","_"))
                button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                button.setIcon(icon(ico))
                button.setIconSize(QSize(25,25))
                button.setText(label)
                button.setToolTip(label)
                button.setMinimumHeight(40)
                button.setStyleSheet(
                    "QToolButton{border:1px solid palette(mid);"
                    "border-radius:5px;padding:5px;text-align:left;}"
                    "QToolButton:hover{background:palette(midlight);}")
                button.clicked.connect(lambda _=False,cb=callback:cb())
                grid.addWidget(button,i//2,i%2)
            lay.addLayout(grid)

        header("Criar elementos","Modelagem")
        options((("Parede","wall",lambda:self.user_show_page("wall")),
                 ("Laje","slab",lambda:self.user_show_page("slab")),
                 ("Pilar","column",lambda:self.user_show_page("column")),
                 ("Viga","beam",lambda:self.user_show_page("beam"))))
        header("Vãos e esquadrias","Parede hospedeira")
        wall=self.controllers.get("wall")
        options((("Abertura","opening",
                  lambda:wall.begin_hosted_fill("opening") if wall else None),
                 ("Porta","opening",
                  lambda:wall.begin_hosted_fill("door") if wall else None),
                 ("Janela","opening",
                  lambda:wall.begin_hosted_fill("window") if wall else None),
                 ("Vão poligonal","polygon",
                  lambda:wall.begin_wall_polygon_from_toolbar() if wall else None)))
        header("Projeto e organização","Gerenciamento")
        options((("Informações","bim",lambda:self.show_page("project")),
                 ("Alinhar / distribuir","move",self.open_arrange),
                 ("Perfis complexos","profile",lambda:self.user_show_page("profiles")),
                 ("BIM / IFC","bim",lambda:self.user_show_page("bim"))))
        self.summary=QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:palette(mid);font-size:9pt;")
        lay.addWidget(self.summary)
        self.intersections=QLabel()
        self.intersections.setWordWrap(True)
        self.intersections.setStyleSheet("color:palette(mid);font-size:9pt;")
        lay.addWidget(self.intersections)

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
        lay.addWidget(update_box)

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
            "wall":("simple_wall_action","composite_wall_action","curve_action"),
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
        lay.addWidget(toggle)
        lay.addWidget(scroll,1)
        self._property_sections[key]=toggle
        return wrapper

    def _trigger_mode(self,key,action,index):
        self._set_mode_button(key,index)
        action.trigger()
        QTimer.singleShot(0,self.sync_mode_buttons)

    def _set_mode_button(self,key,index):
        for i,b in enumerate(self._mode_buttons.get(key,())):
            blocked=b.blockSignals(True);b.setChecked(i==index);b.blockSignals(blocked)

    def _activate_default(self,key):
        ctrl=self.controllers.get(key)
        if ctrl is None:return
        if key=="wall":
            self._set_mode_button(key,0);ctrl.start_structure("simple")
        elif key=="slab":
            self._set_mode_button(key,0);ctrl.start_structure("simple")
        elif key in ("column","beam"):
            self._set_mode_button(key,0);ctrl.start_drawing()

    def user_show_page(self,key):
        self.show_page(key)
        # Choosing a modelling category is itself a tool choice. Start with the
        # obvious default instead of making the user click a second control.
        if key in ("wall","slab","column","beam"):
            self._activate_default(key)
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
            for action in (getattr(wall,"action",None),
                           getattr(wall,"curve_action",None),
                           getattr(wall,"opening_toolbar_action",None)):
                if action is not None:
                    action.triggered.connect(self.schedule_sync_context)
            for action in getattr(getattr(wall,"opening_toolbar_menu",None),"actions",lambda:[])():
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
        self.sync_mode_buttons()

    def sync_mode_buttons(self):
        active=getattr(self.app.viewport,"active_tool",None)
        wall=self.controllers.get("wall")
        if wall is not None and self._mode_buttons.get("wall"):
            if active is getattr(wall,"curve_create_tool",None):idx=2
            else:
                kind=(getattr(getattr(wall,"structure",None),"currentData",lambda:None)() or getattr(wall,"defaults",{}).get("structure","simple"))
                idx=1 if kind=="composite" else 0
            self._set_mode_button("wall",idx)
        slab=self.controllers.get("slab")
        if slab is not None and self._mode_buttons.get("slab"):
            kind=(getattr(getattr(slab,"structure",None),"currentData",lambda:None)() or getattr(slab,"defaults",{}).get("structure","simple"))
            self._set_mode_button("slab",1 if kind=="composite" else 0)
        for key in ("column","beam"):
            if self._mode_buttons.get(key):self._set_mode_button(key,0)

    def sync_context(self):
        # BIM is an inspector/export workspace. Keep it open while selection or
        # metadata changes; otherwise selecting a wall would immediately throw
        # the user back to the modelling page.
        if any(self.pages.get(key) is not None and
               self.stack.currentWidget() is self.pages[key]
               for key in ("bim", "project", "arrange")):
            return
        active=getattr(self.app.viewport,"active_tool",None)
        for key in ("wall","slab","column","beam"):
            ctrl=self.controllers.get(key)
            if ctrl is None:continue
            tool=getattr(ctrl,"tool",None);curve_tool=getattr(ctrl,"curve_create_tool",None)
            if (tool is not None and active is tool) or (curve_tool is not None and active is curve_tool):
                self.show_page(key);return
        for key in ("beam","column","slab","wall"):
            ctrl=self.controllers.get(key)
            if ctrl is not None and getattr(ctrl,"target",None) is not None:
                self.show_page(key);return

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
