# SPDX-License-Identifier: GPL-3.0-or-later
"""Integrated OpenTrace BIM sidebar: compact task navigation and live editors."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QStackedWidget, QToolButton, QVBoxLayout,
    QWidget,
)

from . import __version__
from .icons import icon
from .preset_catalog import builtins
from .profile_library import load_profiles
from .i18n import t, ui_locale
from .style import SIZES, qss, theme_font

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
        self._context_signature = None
        self._navigation_explicit = False
        self._mode_buttons={}
        self._home_sections={}
        self._opening_size_fields={}
        self._opening_section=None
        self._door_create_fields={}
        self._door_anchor_buttons={}
        self._door_edit_fields={}
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
        self.sidebar_brand = brand
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
        self.project_info_button.clicked.connect(lambda: self.user_show_page("project"))
        h.addWidget(self.project_info_button)
        self.navigation_pin=QToolButton(header)
        self.navigation_pin.setObjectName("opentrace_navigation_pin")
        self.navigation_pin.setText(t("Fixar"))
        self.navigation_pin.setCheckable(True)
        self.navigation_pin.setFocusPolicy(Qt.NoFocus)
        self.navigation_pin.setToolTip(t("Fixar página da paleta até desmarcar"))
        self.navigation_pin.toggled.connect(self._pin_changed)
        h.addWidget(self.navigation_pin)
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
            b.setProperty("visualRole", "navigation")
            b.setIcon(icon(ico, SIZES["icon-24"], palette=QApplication.palette()))
            b.setIconSize(QSize(SIZES["icon-24"], SIZES["icon-24"]))
            b.setMinimumSize(QSize(43,48))
            b.setText(label)
            b.setToolTip(label)
            b.setAccessibleName(label)
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
        # Door-specific views reuse the existing hosted door tool and fill
        # records. No wall-form reparenting, copied model or F01 controls.
        if wall is not None:
            self._add_page("door", self._make_door_create_page())
            self._add_page("door_edit", self._make_door_edit_page())
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

    def apply_theme(self):
        """ThemeWatcher dispatches the sidebar through this single style path."""
        palette = QApplication.palette()
        self.sidebar_brand.setFont(theme_font(QApplication.font(), "brand"))
        self.panel.setStyleSheet(qss(
            "QFrame#opentrace_sidebar_header { background: {panel};"
            " border-bottom: 1px solid {divider}; }"
            "QFrame#opentrace_section_open { border-left: 3px solid {orange}; }"
            "QToolButton[visualRole='navigation'] { color: {text}; background: transparent;"
            " border: 0px; border-bottom: 2px solid transparent; font-size: 11px; }"
            "QToolButton[visualRole='navigation']:hover { background: {hover-wash}; }"
            "QToolButton[visualRole='navigation']:checked { border-bottom: 2px solid {orange};"
            " background: {panel-raised}; }"
            "QToolButton[visualRole='home-button'] { color: {text}; border: 1px solid {border};"
            " border-radius: 4px; padding: 5px; text-align: left; }"
            "QToolButton[visualRole='home-button']:hover { background: {hover-wash}; }"
            "QToolButton[visualRole='section-toggle'] { color: {text};"
            " font-size: 12px; font-weight: 600; text-align: left;"
            " border: 0px; border-bottom: 1px solid {divider}; padding: 7px; }"
            "QLabel[visualRole='hint'] { color: {text-muted}; font-size: 11px; }"
            "QToolButton[visualRole='door-anchor'] { border: 0; background: {panel-raised};"
            " border-radius: 4px; color: {text}; padding: 4px; }"
            "QToolButton[visualRole='door-anchor']:checked { background: {panel};"
            " border: 2px solid {orange}; }"
            "QDoubleSpinBox[visualRole='door-readonly'] { background: {panel-raised};"
            " color: {text}; border: 0; }",
            palette))
        for key, button in self.buttons.items():
            name = next(ico for page, _label, ico in self.PAGE_INFO if page == key)
            button.setIcon(icon(name, SIZES["icon-24"],
                                state="marked" if button.isChecked() else "normal",
                                palette=palette))
        for definition in HOME_SECTIONS:
            if definition["title"] not in self._home_sections:
                continue
            _frame, toggle, body = self._home_sections[definition["title"]]
            toggle.setIcon(icon(definition["icon"], SIZES["icon-20"], palette=palette))
            for button in body.findChildren(QToolButton):
                button.setIcon(icon(button.property("designIcon"), SIZES["icon-24"],
                                    palette=palette))
        from .palette import RadialPalette
        for radial in self.app.window.findChildren(RadialPalette):
            radial.apply_theme()

    def _make_door_create_page(self):
        """Existing F01 hosted placement values, never the wall properties form."""
        from .door_window_core import DOOR_FAMILIES

        page = QWidget()
        page.setObjectName("opentrace_door_create_page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(SIZES["space-4"])
        family = QLabel(t("Família") + ": " + t(DOOR_FAMILIES["swing_single"]["name"]))
        family.setObjectName("opentrace_door_family")
        lay.addWidget(family)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for key, label in (("width", "Largura da folha"),
                           ("height", "Altura"), ("sill", "Peitoril")):
            spin = QDoubleSpinBox(page)
            spin.setObjectName("opentrace_door_create_" + key)
            spin.setDecimals(2)
            spin.setLocale(ui_locale())
            spin.setRange(0.0 if key == "sill" else 0.05, 100.0)
            spin.setSingleStep(0.05)
            spin.setSuffix(" m")
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda value, k=key: self._set_door_size(k, value))
            form.addRow(t(label), spin)
            self._door_create_fields[key] = spin
        rough = QDoubleSpinBox(page)
        rough.setObjectName("opentrace_door_rough_width")
        rough.setDecimals(2)
        rough.setLocale(ui_locale())
        rough.setRange(0.0, 200.0)
        rough.setSuffix(" m")
        rough.setReadOnly(True)
        rough.setButtonSymbols(QDoubleSpinBox.NoButtons)
        rough.setFocusPolicy(Qt.NoFocus)
        rough.setProperty("visualRole", "door-readonly")
        rough.setToolTip(t("Calculado pela família F01 e suas folgas"))
        form.addRow(t("Largura do vão de corte"), rough)
        self._door_rough_width = rough
        lay.addLayout(form)
        anchors = QHBoxLayout()
        anchors.addWidget(QLabel(t("Âncora"), page))
        for anchor, label in (("left", "Esquerda"), ("center", "Centro"),
                              ("right", "Direita")):
            button = QToolButton(page)
            button.setObjectName("opentrace_door_create_anchor_" + anchor)
            button.setProperty("visualRole", "door-anchor")
            button.setText(t(label))
            button.setCheckable(True)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda _=False, a=anchor: self._set_door_anchor(a))
            anchors.addWidget(button)
            self._door_anchor_buttons[anchor] = button
        lay.addLayout(anchors)
        method = QHBoxLayout()
        method.addWidget(QLabel(t("Método"), page))
        on_wall = QToolButton(page)
        on_wall.setObjectName("opentrace_door_hosted")
        on_wall.setText(t("Na parede"))
        on_wall.setCheckable(True)
        on_wall.setChecked(True)
        on_wall.setFocusPolicy(Qt.NoFocus)
        on_wall.setEnabled(False)  # Informational: hosted is the only F01 mode.
        method.addWidget(on_wall)
        free = QToolButton(page)
        free.setObjectName("opentrace_door_free_disabled")
        free.setText(t("Livre"))
        free.setEnabled(False)
        free.setToolTip(t("Porta livre: em desenvolvimento"))
        method.addWidget(free)
        method.addStretch(1)
        lay.addLayout(method)
        pending = QLabel(t("Giro e dobradiça: integração F01 em desenvolvimento."), page)
        pending.setProperty("visualRole", "hint")
        pending.setWordWrap(True)
        lay.addWidget(pending)
        lay.addStretch(1)
        self._sync_door_editor()
        return page

    def _make_door_edit_page(self):
        """A selected hosted door gets its own explicit, non-editing page."""
        page = QWidget()
        page.setObjectName("opentrace_door_edit_page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(SIZES["space-4"])
        title = QLabel(t("Porta selecionada"), page)
        title.setObjectName("opentrace_door_edit_title")
        lay.addWidget(title)
        for field, label in (("family", "Família"), ("width", "Largura da folha"),
                             ("height", "Altura"), ("rough", "Largura do vão de corte"),
                             ("anchor", "Âncora")):
            display = QLabel(page)
            display.setObjectName("opentrace_door_edit_" + field)
            display.setProperty("visualRole", "hint")
            self._door_edit_fields[field] = (t(label), display)
            lay.addWidget(display)
        pending = QLabel(t("Edição paramétrica F01: em desenvolvimento."), page)
        pending.setObjectName("opentrace_door_edit_pending")
        pending.setProperty("visualRole", "hint")
        pending.setWordWrap(True)
        lay.addWidget(pending)
        lay.addStretch(1)
        return page

    def _set_door_size(self, key, value):
        tool = self.controllers["wall"].openings.door_tool
        if self.app.viewport.active_tool is not tool:
            return
        tool.sizes["door"][key] = value
        self._sync_door_editor()
        if self.context_bar is not None:
            self.context_bar.refresh()
        self.app.viewport.update()

    def _set_door_anchor(self, anchor):
        tool = self.controllers["wall"].openings.door_tool
        if self.app.viewport.active_tool is not tool:
            return
        tool.anchor = anchor
        self._sync_door_editor()
        if self.context_bar is not None:
            self.context_bar.refresh()
        self.app.viewport.update()

    def _sync_door_editor(self):
        if not self._door_create_fields:
            return
        from .door_window_core import DOOR_FAMILIES
        tool = self.controllers["wall"].openings.door_tool
        sizes = tool.sizes["door"]
        for key, field in self._door_create_fields.items():
            blocked = field.blockSignals(True)
            field.setValue(sizes[key])
            field.blockSignals(blocked)
        offsets = DOOR_FAMILIES["swing_single"]["clearances"]
        blocked = self._door_rough_width.blockSignals(True)
        self._door_rough_width.setValue(sizes["width"] + offsets["left"] + offsets["right"])
        self._door_rough_width.blockSignals(blocked)
        for anchor, button in self._door_anchor_buttons.items():
            button.setChecked(tool.anchor == anchor)

    def _add_page(self,key,widget):
        self.pages[key]=widget;self.stack.addWidget(widget)

    def _make_membrane_notice(self):
        w=QWidget();lay=QVBoxLayout(w);lay.setContentsMargins(12,12,12,12);lay.setSpacing(8)
        title=QLabel("<b style='font-size:14pt'>Membrana — Em avaliação</b>")
        title.setWordWrap(True);lay.addWidget(title)
        body=QLabel("Ferramenta temporariamente desativada enquanto o fluxo de modelagem é revisado.")
        body.setWordWrap(True);body.setProperty("visualRole", "hint");lay.addWidget(body)
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
        subtitle.setProperty("visualRole", "hint")
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
            toggle.setProperty("visualRole", "section-toggle")
            toggle.setIcon(icon(definition["icon"], SIZES["icon-20"],
                                palette=QApplication.palette()))
            toggle.setIconSize(QSize(SIZES["icon-20"], SIZES["icon-20"]))
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
                button.setProperty("visualRole", "home-button")
                button.setProperty("designIcon", glyph)
                button.setIcon(icon(glyph, SIZES["icon-24"], palette=QApplication.palette()))
                button.setIconSize(QSize(SIZES["icon-24"], SIZES["icon-24"]))
                button.setText(t(title))
                button.setToolTip(t(title))
                button.setMinimumHeight(40)
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
        self.summary.setProperty("visualRole", "hint")
        project_grid=self._home_sections["Projeto e organização"][2].layout()
        project_grid.addWidget(self.summary,2,0,1,2)
        self.intersections=QLabel()
        self.intersections.setWordWrap(True)
        self.intersections.setProperty("visualRole", "hint")
        project_grid.addWidget(self.intersections,3,0,1,2)

        update_box=QFrame();update_box.setFrameShape(QFrame.StyledPanel)
        update_lay=QVBoxLayout(update_box);update_lay.setContentsMargins(8,8,8,8);update_lay.setSpacing(6)
        update_lay.addWidget(QLabel(f"<b>OpenTrace BIM {__version__}</b>"))
        self.update_status=QLabel(
            "Consulta apenas o catálogo oficial. Nenhum pacote é instalado sem confirmação."
        )
        self.update_status.setWordWrap(True);self.update_status.setProperty("visualRole", "hint")
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
                frame.style().unpolish(frame)
                frame.style().polish(frame)
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
        toggle.setProperty("visualRole", "section-toggle")
        def mark_properties(opened, frame=wrapper):
            frame.setObjectName("opentrace_section_open" if opened
                                else "opentrace_properties_page")
            frame.style().unpolish(frame)
            frame.style().polish(frame)
        toggle.toggled.connect(mark_properties)
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
            section.style().unpolish(section)
            section.style().polish(section)
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
        self._navigation_explicit = True
        self.show_page(key)
        self.schedule_sync_context()

    def _pin_changed(self, pinned):
        # An explicit pin is the only exception to context-following.
        self._context_signature = None
        if not pinned:
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
            self.user_show_page("arrange")
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
            if ctrl is None:
                continue
            # The active host tool, not the last QAction callback, owns the
            # context. Never force the sidebar onto a creation form here.
            for action in self._actions_for(key,ctrl):
                action.triggered.connect(self.schedule_sync_context)
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
        self._sync_door_editor()

    def show_page(self,key,show_dock=True):
        if key not in self.pages:key="home"
        self.stack.setCurrentWidget(self.pages[key]);b=self.buttons.get(key)
        if b is not None:
            b.setChecked(True)
        elif key in ("project","arrange","door","door_edit"):
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
        self._sync_door_editor()
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
        self._navigation_explicit = False
        self.show_page(key)
        toggle=self._property_sections.get(key)
        if toggle is not None:
            toggle.setChecked(True)

    def _selected_door_record(self):
        """Return only an unambiguous, real selected hosted door fill."""
        from .door_window_commands import _fill_record
        selection = tuple(self.app.scene.selection)
        if len(selection) != 1:
            return None
        group = getattr(selection[0], "owner", None) or selection[0]
        record = _fill_record(group)
        params = record.get("params") if record is not None else None
        return params if params is not None and params.get("kind") == "door" else None

    def _refresh_door_edit(self):
        from .door_window_core import DOOR_FAMILIES, wallhole_size
        from .i18n import ui_locale
        rec = self._selected_door_record()
        if rec is None:
            return
        values = {
            "family": t(DOOR_FAMILIES[rec.get("family_key", "swing_single")]["name"]),
            "width": ui_locale().toString(float(rec["width"]), "f", 2) + " m",
            "height": ui_locale().toString(float(rec["height"]), "f", 2) + " m",
            "rough": ui_locale().toString(float(wallhole_size(rec)[0]), "f", 2) + " m",
            "anchor": t({"left": "Esquerda", "center": "Centro",
                         "right": "Direita"}[rec["anchor"]]),
        }
        for key, (label, display) in self._door_edit_fields.items():
            display.setText(label + ": " + values[key])

    def _context_identity(self):
        active = getattr(self.app.viewport, "active_tool", None)
        owners = tuple(sorted(
            id(getattr(item, "owner", None) or item)
            for item in self.app.scene.selection))
        targets = tuple(id(getattr(self.controllers.get(key), "target", None))
                        for key in ("wall", "slab", "column", "beam"))
        return id(active), targets, owners

    def sync_context(self):
        """Follow tool activation and selection, except for a deliberate pin.

        Manual navigation persists during document refreshes of the SAME
        context; a new tool or selection follows its actual editor. Merely
        selecting a group never calls any tool activation.
        """
        signature = self._context_identity()
        if signature == self._context_signature:
            return
        self._context_signature = signature
        if self.navigation_pin.isChecked():
            return

        active = getattr(self.app.viewport, "active_tool", None)
        opening_tool, opening_kind = self._opening_tool_and_kind()
        if opening_tool is not None:
            self._show_context_settings("door" if opening_kind == "door" else "wall")
            return
        for key in ("wall", "slab", "column", "beam"):
            ctrl = self.controllers.get(key)
            if ctrl is None:
                continue
            tool = getattr(ctrl, "draw_tool", None) or getattr(ctrl, "tool", None)
            if tool is not None and active is tool:
                self._show_context_settings(key)
                return
        if self._selected_door_record() is not None:
            self._refresh_door_edit()
            self._show_context_settings("door_edit")
            return
        for key in ("beam", "column", "slab", "wall"):
            ctrl = self.controllers.get(key)
            if ctrl is not None and getattr(ctrl, "target", None) is not None:
                self._show_context_settings(key)
                return
        if not self._navigation_explicit:
            self.show_page("home", show_dock=False)

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
