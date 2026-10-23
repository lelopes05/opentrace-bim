# SPDX-License-Identifier: GPL-3.0-or-later
"""Integrated OpenTrace BIM sidebar: compact task navigation and live editors."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QStackedWidget, QToolButton, QVBoxLayout,
    QWidget,
)

from . import __version__, __build_label__
from .icons import icon
from .preset_catalog import builtins
from .profile_library import load_profiles
from .i18n import t, englishize_widget, english
from .style import SIZES, qss, theme_font

# Home is onboarding + the actual project-information form, not a second
# tool launcher.  Tool choice stays in the top row and category tabs.


class ArchitectureSuitePanel:
    PAGE_INFO=(
        ("home","Home","home"),("wall","Wall","wall"),
        ("door","Door","door"),
        ("slab","Slab","slab"),("column","Column","column"),
        ("beam","Beam","beam"),("membrane","Membrane","slab"),
        ("profiles","Profiles","profile"),("bim","BIM","bim"),
    )
    def __init__(self,app,wall=None,slab=None,column=None,beam=None,profiles=None,bim=None,membrane=None,master_dock=None):
        self.app=app;self.controllers={"wall":wall,"slab":slab,"column":column,"beam":beam,"membrane":membrane,"profiles":profiles,"bim":bim}
        self._sync_queued=False;self._last_active_tool_id=id(getattr(self.app.viewport,"active_tool",None))
        self._mode_buttons={}
        self._home_sections={}
        self._opening_size_fields={}
        self._opening_section=None
        self._door_size_fields={}
        self._door_full_button=None
        self._door_void_button=None
        self._door_family_combo=None  # retired: replaced with two direct buttons
        self._door_system_swing=None
        self._door_system_slide=None
        self._door_sliding_type_combo=None
        self._door_sliding_options=None
        self._last_sliding_family='sliding_surface'
        self._door_slide_combo=None
        self._door_swing_options=None
        self._door_hinge_combo=None
        self._door_swing_combo=None
        self._door_style_combo=None
        self._door_variant_combo=None
        self._door_selected_variant='grid'
        self._door_style_preview=None
        self._door_style_caption=None
        self._door_preview_key=None
        self._door_draft_original=None
        self._door_instance_caption=None
        self._door_apply_button=None
        self._door_cancel_button=None
        self._property_sections={}
        self._property_slots={}
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
        self.arrange_button.setToolTip("Align and distribute objects along X, Y and Z")
        self.arrange_button.setAccessibleName("Align and distribute objects")
        self.arrange_button.setFixedSize(QSize(32,32))
        self.arrange_button.clicked.connect(self.open_arrange)
        h.addWidget(self.arrange_button)
        self.project_info_button=QToolButton(header)
        self.project_info_button.setText("ⓘ")
        self.project_info_button.setToolTip("Project information")
        self.project_info_button.setAccessibleName("Project information")
        self.project_info_button.setFixedSize(QSize(32,32))
        self.project_info_button.clicked.connect(lambda: self.show_page("project"))
        h.addWidget(self.project_info_button)
        self.help_button=QToolButton(header)
        self.help_button.setText("?")
        self.help_button.setFixedSize(QSize(32,32))
        self.help_button.setToolTip("Contextual help and About")
        self.help_button.setAccessibleName("OpenTrace BIM Help")
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
        # Own navigation page for the existing hosted-door tool. No new host
        # tool, history path or duplicated model is registered here.
        self._add_page("door",self._make_door_page())
        self.controllers['wall'].openings.door_settings_changed.connect(
            self._on_door_settings_changed)
        self._route_hosted_editor("door")
        bim_ctrl=self.controllers.get("bim")
        if bim_ctrl is not None and getattr(bim_ctrl, "project_panel", None) is not None:
            # Reparent the SINGLE authoritative project form into Home.
            # Its line edits remain wired to bim_ctrl.save(); no clones.
            self.home_project_layout.addWidget(bim_ctrl.project_panel)
            self.export_template_button = QPushButton("Save my settings as template…", self.panel)
            self.export_template_button.setObjectName("opentrace_export_project_template")
            self.export_template_button.setToolTip("Saves settings and libraries without copying .igz geometry")
            self.export_template_button.clicked.connect(self.export_project_template)
            self.home_project_layout.addWidget(self.export_template_button)
        else:
            self.project_info_button.setEnabled(False)
            self.home_project_section.hide()
        from .object_properties import ObjectProperties
        self.object_properties = ObjectProperties(self)
        self._property_fallback = QWidget(self.panel)
        self._property_fallback_layout = QVBoxLayout(self._property_fallback)
        self._property_fallback_layout.setContentsMargins(0,0,0,0)
        self._property_fallback_layout.addWidget(self.object_properties)
        root.insertWidget(root.indexOf(self.stack), self._property_fallback)
        self.show_page("home",show_dock=False);self._wire();self.refresh_home();self.sync_mode_buttons()
        from .workspace_menu import install_workspace_menu
        self.workspace_menus = install_workspace_menu(self)
        # The viewport overlay creates the contextual bar with an explicit
        # overlay reference after the sidebar is ready.
        self.context_bar = None
        englishize_widget(self.panel)
        # Check automatically only when the user has explicitly opted in.
        if self.auto_update_check.isChecked():
            self._auto_check_timer.start(3000)

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
            "QLabel[visualRole='hint'] { color: {text-muted}; font-size: 11px; }",
            palette))
        for key, button in self.buttons.items():
            name = next(ico for page, _label, ico in self.PAGE_INFO if page == key)
            button.setIcon(icon(name, SIZES["icon-24"],
                                state="marked" if button.isChecked() else "normal",
                                palette=palette))
        self.library_manager_button.setIcon(
            icon("library", SIZES["icon-24"], palette=palette))
        from .palette import RadialPalette
        for radial in self.app.window.findChildren(RadialPalette):
            radial.apply_theme()

    def _add_page(self,key,widget):
        self.pages[key]=widget;self.stack.addWidget(widget)

    def _make_membrane_notice(self):
        w=QWidget();lay=QVBoxLayout(w);lay.setContentsMargins(12,12,12,12);lay.setSpacing(8)
        title=QLabel("<b style='font-size:14pt'>Membrane — Under review</b>")
        title.setWordWrap(True);lay.addWidget(title)
        body=QLabel("Tool temporarily disabled while its modeling workflow is being revised.")
        body.setWordWrap(True);body.setProperty("visualRole", "hint");lay.addWidget(body)
        note=QLabel("The experimental tool is not loaded in this version.")
        note.setWordWrap(True);lay.addWidget(note);lay.addStretch(1)
        return w

    def _make_home(self):
        """One scrollable Home: start guide, project data, libraries, updates.

        The real BIM controller's project form is attached after its page
        exists; this is not a second copy of fields or document properties.
        """
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(w)
        scroll.setObjectName("opentrace_home_scroll")
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setMinimumSize(0, 0)
        content = QWidget(scroll)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)
        greeting = QLabel("<b style='font-size:14pt'>Welcome!</b>", content)
        lay.addWidget(greeting)
        guidance = QLabel(
            "To start modeling, choose a tool and click anywhere "
            "in the viewport.\n\n"
            "OpenTrace will display short tips in the lower status bar.", content)
        guidance.setWordWrap(True)
        lay.addWidget(guidance)


        # Explicit project initialization; never auto-prompts an opened .igz.
        self.project_setup_button = QPushButton("Configure new project · template + catalog", content)
        self.project_setup_button.setObjectName("opentrace_experimental_project_setup")
        self.project_setup_button.setToolTip("Always available: choose settings and create a NEW independent project")
        self.project_setup_button.clicked.connect(self.open_project_setup)
        lay.addWidget(self.project_setup_button)
        self.project_setup_status = QLabel(content)
        self.project_setup_status.setWordWrap(True)
        self.project_setup_status.setProperty("visualRole", "hint")
        lay.addWidget(self.project_setup_status)

        self.home_project_section = QWidget(content)
        self.home_project_section.setObjectName("opentrace_home_project")
        self.home_project_layout = QVBoxLayout(self.home_project_section)
        self.home_project_layout.setContentsMargins(0, 0, 0, 0)
        self.home_project_layout.setSpacing(0)
        lay.addWidget(self.home_project_section)

        self.library_manager_button = QToolButton(content)
        self.library_manager_button.setObjectName("opentrace_home_manage_libraries")
        self.library_manager_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.library_manager_button.setIconSize(QSize(SIZES["icon-24"], SIZES["icon-24"]))
        self.library_manager_button.setIcon(icon("library", SIZES["icon-24"],
                                                 palette=QApplication.palette()))
        self.library_manager_button.setText("Manage libraries")
        self.library_manager_button.setToolTip("Browse full library and manage project collections")
        self.library_manager_button.setAccessibleName("Manage libraries and sublibraries")
        self.library_manager_button.clicked.connect(self.manage_libraries)
        self.library_manager_button.setEnabled(True)
        lay.addWidget(self.library_manager_button)

        self.summary = QLabel(content)
        self.summary.setWordWrap(True)
        self.summary.setProperty("visualRole", "hint")
        lay.addWidget(self.summary)
        self.intersections = QLabel(content)
        self.intersections.setWordWrap(True)
        self.intersections.setProperty("visualRole", "hint")
        lay.addWidget(self.intersections)

        update_box = QFrame(content)
        update_box.setFrameShape(QFrame.StyledPanel)
        update_lay = QVBoxLayout(update_box)
        update_lay.setContentsMargins(8, 8, 8, 8)
        update_lay.setSpacing(6)
        update_lay.addWidget(QLabel(f"<b>OpenTrace BIM {__build_label__}</b>"))
        self.update_status = QLabel(
            "Checks OpenTrace BIM GitHub Releases; installation requires confirmation.")
        self.update_status.setWordWrap(True)
        self.update_status.setProperty("visualRole", "hint")
        update_lay.addWidget(self.update_status)
        self.auto_update_check = QCheckBox("Automatically check for updates")
        self.update_button = QPushButton("Check for updates")
        update_lay.addWidget(self.auto_update_check)
        update_lay.addWidget(self.update_button)
        lay.addWidget(update_box)

        # Single, real updater instance owned by the Home panel.
        # Do not contact the network until a manual click or opt-in startup check.
        from .updater import UpdateManager, auto_check_enabled
        self.update_manager = UpdateManager(content)
        self.update_manager.status_changed.connect(self.update_status.setText)
        self.auto_update_check.setChecked(auto_check_enabled())
        self.auto_update_check.toggled.connect(self._auto_update_toggled)
        self.update_button.clicked.connect(
            lambda _checked=False: self.update_manager.check(manual=True)
        )

        lay.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self.home_scroll = scroll
        return w

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
            ("form_widget","Geometry and properties"),
            ("layer_editor","Composition and layers"),
            ("opening_widget","Openings and doors/windows"),
        ):
            widget=getattr(ctrl,attr,None)
            if widget is None: continue
            index=layout.indexOf(widget)
            if index<0: continue
            initial_hidden=widget.isHidden()
            layout.removeWidget(widget)
            section=EditorSection(title,widget,parent=page)
            section.setObjectName("opentrace_wall_section_"+attr)
            if attr == "opening_widget":
                ctrl._suite_opening_widget_section = section.body
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
            section.setVisible(widget.parentWidget() is section.body and not widget.isHidden())

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
        container=QWidget(wrapper)
        inner=QVBoxLayout(container)
        inner.setContentsMargins(0,0,0,0)
        inner.setSpacing(5)
        property_slot=QWidget(container)
        property_slot.setObjectName("opentrace_properties_slot_" + key)
        property_slot_layout=QVBoxLayout(property_slot)
        property_slot_layout.setContentsMargins(0,0,0,0)
        inner.addWidget(property_slot)
        inner.addWidget(page)
        self._property_slots[key] = property_slot_layout
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame);scroll.setMinimumSize(0,0);scroll.setWidget(container)
        # Do not detach/rebuild the existing editor: the section only
        # collapses its VIEW, preserving widgets, values and Undo handlers.
        toggle=QToolButton(wrapper)
        toggle.setObjectName("opentrace_properties_"+key)
        toggle.setCheckable(True)
        toggle.setChecked(True)
        toggle.setToolButtonStyle(Qt.ToolButtonTextOnly)
        toggle.setText("▾ Detailed properties")
        toggle.setToolTip("Collapse or expand detailed editing")
        toggle.setAccessibleName("Detailed properties")
        def switch_properties(expanded, sc=scroll, bt=toggle):
            sc.setVisible(expanded)
            bt.setText(("▾" if expanded else "▸")+" Detailed properties")
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

    def _make_door_page(self):
        """Route the existing form to a dedicated Porta tab, never clone it."""
        page=QWidget(self.panel)
        outer=QVBoxLayout(page);outer.setContentsMargins(2,2,2,2)
        scroll=QScrollArea(page);scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content=QWidget(scroll);form=QVBoxLayout(content)
        form.setContentsMargins(8,8,8,8);form.setSpacing(8)
        note=QLabel('Ferramenta Porta · Inserção e edição da porta selecionada',content)
        note.setWordWrap(True);form.addWidget(note)
        modes=QHBoxLayout()
        self._door_full_button=QPushButton('Porta completa',content)
        self._door_void_button=QPushButton('Vão sem folha',content)
        for button,as_void in ((self._door_full_button,False),
                               (self._door_void_button,True)):
            button.setCheckable(True)
            button.clicked.connect(lambda _=False,v=as_void:self._choose_door_mode(v))
            modes.addWidget(button)
        form.addLayout(modes)
        # The compositor is ALWAYS visible, even before there is a selected
        # instance or a collapsed property inspector.
        self._door_editor_button=QPushButton('✎  Abrir compositor visual de folhas…',content)
        self._door_editor_button.setObjectName('opentrace_door_editor_primary')
        self._door_editor_button.setToolTip('Edite uma folha-modelo antes de inserir ou a porta selecionada.')
        self._door_editor_button.clicked.connect(self._open_door_editor)
        form.addWidget(self._door_editor_button)
        from .door_style_catalog import DOOR_STYLES, DOOR_INSTALLATIONS
        from .door_leaf_editor import _preset_icon
        from .door_leaf_presets import LEAF_PRESETS
        form.addWidget(QLabel('Sistema de portas',content))
        systems=QHBoxLayout()
        self._door_system_swing=QPushButton('Porta de Giro',content)
        self._door_system_slide=QPushButton('Porta de Correr',content)
        for button in (self._door_system_swing,self._door_system_slide):
            button.setCheckable(True)
            systems.addWidget(button)
        self._door_system_swing.setObjectName('opentrace_door_system_swing')
        self._door_system_slide.setObjectName('opentrace_door_system_slide')
        self._door_system_swing.clicked.connect(
            lambda _=False:self._set_door_family('swing_single',activate=True))
        self._door_system_slide.clicked.connect(
            lambda _=False:self._set_door_family(self._last_sliding_family,activate=True))
        form.addLayout(systems)
        # One model/conversion block immediately below the system selector.
        # A preset choice is a draft for converting a selected door, or the
        # insertion default when no instance is selected.
        form.addWidget(QLabel('Tipo de folha · edição e conversão',content))
        self._door_variant_combo=QComboBox(content)
        self._door_variant_combo.setObjectName('opentrace_door_conversion_variant')
        for title,key in (('Folha do compositor / modelo visual','grid'),
                          ('Folha lisa tradicional','plain'),
                          ('Folha frisada tradicional','grooved'),
                          ('Folha almofadada tradicional','panelled')):
            self._door_variant_combo.addItem(title,key)
        self._door_variant_combo.activated.connect(
            lambda _i:self._set_door_variant(self._door_variant_combo.currentData()))
        form.addWidget(self._door_variant_combo)
        self._edit_grooves_button=QPushButton('Edit grooves…',content)
        self._edit_grooves_button.setToolTip('Edit groove count, width, margins and horizontal offset in the visual compositor.')
        self._edit_grooves_button.clicked.connect(self._open_door_editor)
        form.addWidget(self._edit_grooves_button)
        form.addWidget(QLabel('Modelo da folha',content))
        self._door_style_combo=QComboBox(content)
        self._door_style_combo.setObjectName('opentrace_door_preset_picker')
        self._door_style_combo.setIconSize(QSize(32,40))
        patterns={item[0]:item for item in LEAF_PRESETS}
        for key,title in DOOR_STYLES:
            self._door_style_combo.addItem(_preset_icon(patterns[key]),title,key)
        self._door_style_combo.activated.connect(
            lambda _index:self._choose_door_style(self._door_style_combo.currentData()))
        # A single read-only thumbnail above the selector avoids model buttons
        # activating tools or changing host geometry while choosing a style.
        self._door_style_preview=QLabel(content)
        self._door_style_preview.setObjectName('opentrace_door_style_preview')
        self._door_style_preview.setAlignment(Qt.AlignCenter)
        self._door_style_preview.setFixedSize(112,150)
        self._door_style_preview.setStyleSheet(
            'background:#f4f7fa; border:1px solid #9eafc0; border-radius:5px;')
        self._door_style_caption=QLabel(content)
        self._door_style_caption.setAlignment(Qt.AlignCenter)
        preview_host=QWidget(content)
        preview_col=QVBoxLayout(preview_host)
        preview_col.setContentsMargins(0,4,0,6)
        preview_col.addWidget(self._door_style_preview,alignment=Qt.AlignHCenter)
        preview_col.addWidget(self._door_style_caption)
        form.addWidget(preview_host)
        form.addWidget(QLabel('Modelos pré-configurados',content))
        form.addWidget(self._door_style_combo)
        actions=QHBoxLayout()
        self._door_apply_button=QPushButton('Aplicar / Converter porta selecionada',content)
        self._door_apply_button.setObjectName('opentrace_door_apply_conversion')
        self._door_apply_button.setToolTip(
            'Converte sistema e folha em um único Undo; mantém posição, dimensões e IDs.')
        self._door_apply_button.clicked.connect(self._apply_door_conversion)
        actions.addWidget(self._door_apply_button,2)
        self._door_cancel_button=QPushButton('Descartar escolha',content)
        self._door_cancel_button.setObjectName('opentrace_door_cancel_conversion')
        self._door_cancel_button.clicked.connect(self._discard_door_choice)
        actions.addWidget(self._door_cancel_button,1)
        form.addLayout(actions)
        # Rebuild only the applicable controls; use the same placement engine.
        self._door_sliding_options=QWidget(content)
        sliding_options=QVBoxLayout(self._door_sliding_options)
        sliding_options.setContentsMargins(0,0,0,0)
        sliding_options.addWidget(QLabel('Instalação da porta de correr',content))
        self._door_sliding_type_combo=QComboBox(self._door_sliding_options)
        self._door_sliding_type_combo.setObjectName('opentrace_door_sliding_type')
        self._door_sliding_type_combo.addItem('Correr aparente (externa)','sliding_surface')
        self._door_sliding_type_combo.addItem('Correr embutida (experimental)','sliding_pocket')
        self._door_sliding_type_combo.activated.connect(
            lambda _i:self._set_door_family(self._door_sliding_type_combo.currentData()))
        sliding_options.addWidget(self._door_sliding_type_combo)
        sliding_options.addWidget(QLabel('Sentido de deslizamento',content))
        self._door_slide_combo=QComboBox(content)
        self._door_slide_combo.setObjectName('opentrace_door_slide_direction')
        self._door_slide_combo.addItem('Para a esquerda','left')
        self._door_slide_combo.addItem('Para a direita','right')
        self._door_slide_combo.activated.connect(
            lambda _index:self._set_door_slide_side(self._door_slide_combo.currentData()))
        sliding_options.addWidget(self._door_slide_combo)
        form.addWidget(self._door_sliding_options)
        self._door_swing_options=QWidget(content)
        swing_options=QVBoxLayout(self._door_swing_options)
        swing_options.setContentsMargins(0,0,0,0)
        swing_options.addWidget(QLabel('Lado das dobradiças',content))
        self._door_hinge_combo=QComboBox(self._door_swing_options)
        self._door_hinge_combo.setObjectName('opentrace_door_hinge')
        self._door_hinge_combo.addItem('Dobradiças à esquerda','left')
        self._door_hinge_combo.addItem('Dobradiças à direita','right')
        self._door_hinge_combo.activated.connect(
            lambda _i:self._set_door_hinge(self._door_hinge_combo.currentData()))
        swing_options.addWidget(self._door_hinge_combo)
        swing_options.addWidget(QLabel('Sentido do giro',content))
        self._door_swing_combo=QComboBox(self._door_swing_options)
        self._door_swing_combo.setObjectName('opentrace_door_swing')
        self._door_swing_combo.addItem('Giro positivo',1)
        self._door_swing_combo.addItem('Giro negativo',-1)
        self._door_swing_combo.activated.connect(
            lambda _i:self._set_door_swing(self._door_swing_combo.currentData()))
        swing_options.addWidget(self._door_swing_combo)
        form.addWidget(self._door_swing_options)
        # Keep the real, history-backed instance inspector above insertion
        # dimensions. No clone of the model or second tool controller.
        self._door_instance_caption=QLabel(
            'Porta selecionada · alterações de propriedades são imediatas',content)
        self._door_instance_caption.setWordWrap(True)
        form.addWidget(self._door_instance_caption)
        self._door_properties_host=QWidget(content)
        self._door_properties_layout=QVBoxLayout(self._door_properties_host)
        self._door_properties_layout.setContentsMargins(0,0,0,0)
        form.addWidget(self._door_properties_host)
        self._property_slots['door']=self._door_properties_layout
        insertion_heading=QLabel('Dimensões padrão para inserir novas portas',content)
        insertion_heading.setWordWrap(True)
        form.addWidget(insertion_heading)
        dimensions=QFrame(content)
        size_layout=QGridLayout(dimensions)
        for row,(key,title) in enumerate((('width','Largura'),('height','Altura'),
                                          ('sill','Peitoril'))):
            value=QDoubleSpinBox(dimensions)
            value.setDecimals(3);value.setRange(0 if key=='sill' else .05,100)
            value.setSingleStep(.01);value.setSuffix(' m')
            value.setKeyboardTracking(False)
            value.setObjectName('opentrace_door_insert_'+key)
            value.valueChanged.connect(lambda number,k=key:self._set_door_size(k,number))
            size_layout.addWidget(QLabel(title,dimensions),row,0)
            size_layout.addWidget(value,row,1)
            self._door_size_fields[key]=value
        form.addWidget(dimensions)
        # Repair ONLY orphaned historic V5 door cuts, explicitly on request;
        # never silently mutate saved scenes or compromise native Undo.
        self._repair_door_cuts_button=QPushButton(
            'Reparar aberturas órfãs de portas antigas…',content)
        self._repair_door_cuts_button.setObjectName('opentrace_repair_orphaned_doors')
        self._repair_door_cuts_button.setToolTip(
            'Remove, com Undo/Redo, apenas aberturas de portas cujas folhas já não existem.')
        self._repair_door_cuts_button.clicked.connect(self._repair_orphaned_door_cuts)
        form.addWidget(self._repair_door_cuts_button)
        form.addStretch(1)
        scroll.setWidget(content);outer.addWidget(scroll)
        self._sync_door_controls()
        return page

    def _choose_door_mode(self,as_void):
        opening=self.controllers['wall'].openings
        opening.door_tool.door_as_opening=as_void
        from .wall_opening_ui import DOOR_TOOL_KEY
        # Existing registered command, identical to top-bar split button.
        opening._start(DOOR_TOOL_KEY)
        opening.notify_door_settings()
        self._sync_door_controls()
        self.schedule_sync_context()

    def _on_door_settings_changed(self):
        self._sync_door_controls()
        bar=getattr(self,'context_bar',None)
        if bar is not None:bar.refresh()
        self.app.viewport.update()

    def _save_door_draft(self):
        if self._door_draft_original is not None:return
        import copy
        tool=self.controllers['wall'].openings.door_tool
        self._door_draft_original={name:copy.deepcopy(getattr(tool,name))
             for name in ('door_family_key','door_style_key','door_leaf_grid',
                          'door_slide_side','door_hinge','door_swing','door_variant','door_grooves')}
        self._door_draft_original['visual_variant']=self._door_selected_variant

    def _set_door_variant(self,value):
        if value not in ('grid','plain','grooved','panelled'):return
        self._save_door_draft()
        self._door_selected_variant=value
        self.controllers['wall'].openings.door_tool.door_variant=value
        self._sync_door_controls()
        self.schedule_sync_context()

    def _set_door_family(self,key,activate=False):
        from .door_style_catalog import DOOR_INSTALLATIONS
        if key not in dict(DOOR_INSTALLATIONS):return
        self._save_door_draft()
        if key.startswith('sliding_'):
            self._last_sliding_family=key
        # Never discard the actual selection when staging a conversion.
        active_selection=self._selected_door_instance() is not None
        self.controllers['wall'].openings.choose_door_family(
            key,activate=activate and not active_selection)

    def _set_door_slide_side(self, side):
        if side not in ('left','right'):return
        tool=self.controllers['wall'].openings.door_tool
        self._save_door_draft()
        tool.door_slide_side=side
        self.controllers['wall'].openings.notify_door_settings()

    def _set_door_hinge(self,hinge):
        if hinge not in ('left','right'):return
        openings=self.controllers['wall'].openings
        self._save_door_draft()
        openings.door_tool.door_hinge=hinge
        openings.notify_door_settings()

    def _set_door_swing(self,positive):
        if positive not in (-1,1):return
        openings=self.controllers['wall'].openings
        self._save_door_draft()
        openings.door_tool.door_swing=positive
        openings.notify_door_settings()

    def _choose_door_style(self,key):
        from .door_style_catalog import prepare_door_style
        tool=self.controllers['wall'].openings.door_tool
        self._save_door_draft()
        # Choosing a visual preset always means the visual/grid variant.
        self._door_selected_variant='grid'
        tool.door_variant='grid'
        try:prepare_door_style(tool,key)
        except ValueError:return
        self.controllers['wall'].openings.notify_door_settings()

    def _selected_door_instance(self):
        """Current selected *real* door, not a stale insertion preview."""
        from .door_window_commands import _fill_record
        from .model import read_wall, wall_record
        scene=self.app.viewport.scene
        # First honour a selected fill group in the host viewport.
        for group in scene.selection:
            parent=getattr(group,'owner',None) or group
            if parent not in scene.groups:continue
            record=_fill_record(parent)
            if record and record.get('kind')=='door':
                host=next((w for w in scene.groups
                           if getattr(w,'uid',None)==record.get('host_id')),None)
                if host is not None:return host,parent,record['params']
        wall=self.controllers['wall']
        host=wall.target
        # A non-door selection must never apply a conversion to a stale
        # previously edited door in the wall's opening selector.
        if scene.selection and host not in scene.selection:
            return None
        if (host is None or host not in scene.groups
                or wall_record(host) is None or not wall._active_opening_id):
            return None
        opening=next((o for o in read_wall(host).get('openings',[])
                      if o.get('id')==wall._active_opening_id),None)
        if opening is None:return None
        group=wall._find_linked_fill(opening)
        record=_fill_record(group) if group is not None else None
        if record and record.get('kind')=='door':
            return host,group,record['params']
        return None

    def _apply_door_conversion(self):
        """One history command for *type/style*, never for insertion defaults."""
        from PySide6.QtWidgets import QMessageBox
        from .door_leaf_presets import make_leaf_preset
        from .door_window_commands import EditHostedFill
        from .door_window_core import normalize_fill
        from .door_style_catalog import DOOR_STYLES
        choice=self._selected_door_instance()
        if choice is None:
            QMessageBox.information(self.panel,'Converter porta',
                'Selecione primeiro uma porta paramétrica existente na viewport.')
            return
        host,group,raw=choice
        try:
            import copy
            current=normalize_fill(raw)
            if current.get('f01_layout')!='physical':
                raise ValueError('Portas antigas precisam de migração explícita antes da conversão.')
            tool=self.controllers['wall'].openings.door_tool
            grid=copy.deepcopy(tool.door_leaf_grid)
            if grid is None or (current['width']!=tool.sizes['door']['width']
                                 or current['height']!=tool.sizes['door']['height']):
                # Presets are regenerated for the dimensions of THIS instance.
                grid=make_leaf_preset(tool.door_style_key,current['width'],
                                      current['height'],current['leaf_thickness'])
            from .door_leaf_grid import normalize_leaf_grid
            grid=normalize_leaf_grid(grid,current['width'],current['height'],
                                      current['leaf_thickness'])
            changes={'family_key':tool.door_family_key,
                     'leaf_variant':self._door_selected_variant,
                     'hinge':tool.door_hinge,'swing':tool.door_swing}
            if self._door_selected_variant=='grid':
                changes['leaf_grid']=grid
            if self._door_selected_variant=='grooved':
                from .door_grooves import normalize_grooves
                changes.update(normalize_grooves(tool.door_grooves,current['width'],current['height']))
            if tool.door_family_key.startswith('sliding_'):
                changes.update(slide_side=tool.door_slide_side,
                               slide_open_fraction=0.0)
                if tool.door_family_key=='sliding_pocket':
                    changes['pocket_layout']='sleeve'
            # The existing host, opening and fill keep their identities.
            command=EditHostedFill(self.app.scene,host,group,changes)
            self.app.viewport.history.execute(command)
            if self.app.viewport.history.last_error:
                raise ValueError(self.app.viewport.history.last_error)
            self._door_draft_original=None
            self.app.viewport.notify_scene_changed()
            self.controllers['wall'].schedule_refresh()
            self._sync_door_controls()
        except Exception as exc:
            QMessageBox.warning(self.panel,'Conversão não aplicada',str(exc))

    def _discard_door_choice(self):
        if self._door_draft_original is None:return
        import copy
        tool=self.controllers['wall'].openings.door_tool
        for name,value in self._door_draft_original.items():
            if name=='visual_variant':
                self._door_selected_variant=value
            else:
                setattr(tool,name,copy.deepcopy(value))
        self._door_draft_original=None
        self.controllers['wall'].openings.notify_door_settings()

    def _open_door_editor(self):
        """Open a modal visual draft with one authoritative button.

        The old implementation silently delegated to a potentially stale
        inspector, producing a no-op when a previous door was selected.
        Validate the LIVE scene selection, and report *every* dialog failure.
        """
        from PySide6.QtWidgets import QMessageBox
        try:
            from .door_leaf_editor import DoorLeafGridDialog
            from .door_leaf_presets import make_leaf_preset
            from .door_leaf_grid import normalize_leaf_grid
            from .materials import material_catalog
            from .door_window_commands import _fill_record
            wall=self.controllers['wall']
            scene=self.app.viewport.scene
            selected=None
            selected_group=None
            for group in scene.selection:
                parent=getattr(group,'owner',None) or group
                if parent not in scene.groups:
                    continue
                record=_fill_record(parent)
                if record and record.get('kind')=='door':
                    selected=record.get('params')
                    selected_group=parent
                    break
            tool=wall.openings.door_tool
            size=tool.sizes['door']
            if selected and selected.get('f01_layout')=='physical':
                spec=selected
                is_instance=True
            else:
                grid=tool.door_leaf_grid
                try:
                    if grid is None:raise ValueError('Nenhum modelo')
                    grid=normalize_leaf_grid(grid,size['width'],size['height'],.035)
                except (ValueError,TypeError):
                    grid=make_leaf_preset(tool.door_style_key,
                                          size['width'],size['height'],.035)
                spec={'kind':'door','width':size['width'],
                      'height':size['height'],'leaf_thickness':.035,
                      'leaf_grid':grid,
                      'leaf_variant':self._door_selected_variant}
                if self._door_selected_variant=='grooved':
                    spec.update(tool.door_grooves)
                is_instance=False
            dialog=DoorLeafGridDialog(spec,self.panel,
                                catalog=material_catalog(scene))
            if not dialog.exec():
                return
            changes=({'groove_settings': dialog.result_grooves()}
                     if spec.get('leaf_variant')=='grooved'
                     else {'leaf_grid': dialog.result_grid()})
            if is_instance:
                # Explicitly address the selected live Group. The historical
                # inspector target can still point to an older selection.
                from .door_window_commands import EditHostedFill
                host=next((w for w in scene.groups
                          if getattr(w,'uid',None)==selected.get('host_id')),None)
                if host is None:
                    raise ValueError('A parede hospedadora da porta não existe.')
                updates=(changes['groove_settings'] if 'groove_settings' in changes
                         else {'leaf_variant':'grid','leaf_grid':changes['leaf_grid']})
                command=EditHostedFill(scene,host,selected_group,updates)
                self.app.viewport.history.execute(command)
                if self.app.viewport.history.last_error:
                    raise ValueError(self.app.viewport.history.last_error)
                self.app.viewport.notify_scene_changed()
                wall.schedule_refresh()
            else:
                if 'groove_settings' in changes:
                    tool.door_grooves=changes['groove_settings']
                    tool.door_variant='grooved'
                else:
                    tool.door_leaf_grid=changes['leaf_grid']
                    tool.door_variant='grid'
                    self._door_selected_variant='grid'
                wall.openings.notify_door_settings()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception('Falha ao abrir ou aplicar compositor visual')
            QMessageBox.warning(self.panel,'Visual compositor',
                                'Unable to open or apply the compositor:\n'+str(exc))

    def _repair_orphaned_door_cuts(self):
        """Undoable, user-confirmed repair of stale source_id links.

        No automatic scene mutation: existing files may have external objects
        and ordinary open voids that must never be deleted by a heuristic.
        """
        from PySide6.QtWidgets import QMessageBox
        from .model import read_wall, wall_record
        from .door_window_commands import _fill_record
        from .commands import EditWall
        from core.history import CompoundCommand
        scene=self.app.viewport.scene
        active_ids={rec.get('source_id') for group in scene.groups
                    if (rec:=_fill_record(group)) is not None}
        updates=[];removed=0
        for wall in scene.groups:
            if wall_record(wall) is None:continue
            values=read_wall(wall)
            retained=[]
            for opening in values.get('openings',()):
                metadata=opening.get('fill') or {}
                if (opening.get('source_id') and
                        opening['source_id'] not in active_ids and
                        metadata.get('class')=='IfcDoor'):
                    removed+=1
                    continue
                retained.append(opening)
            if len(retained)!=len(values.get('openings',())):
                values['openings']=retained
                updates.append((wall,values))
        if not updates:
            QMessageBox.information(self.panel,'Reparar aberturas',
              'Nenhuma abertura órfã de porta foi encontrada.')
            return
        decision=QMessageBox.question(self.panel,'Reparar aberturas',
            f'Foram encontradas {removed} abertura(s) de portas sem folha '+
            'vinculada. Remover essas aberturas com Undo/Redo?')
        if decision!=QMessageBox.Yes:return
        try:
            commands=[EditWall(scene,wall,values) for wall,values in updates]
            cmd=commands[0] if len(commands)==1 else CompoundCommand(commands)
            self.app.viewport.history.execute(cmd)
            if self.app.viewport.history.last_error:
                raise ValueError(self.app.viewport.history.last_error)
            self.app.viewport.notify_scene_changed()
            self.controllers['wall'].schedule_refresh()
        except Exception as exc:
            QMessageBox.warning(self.panel,'Reparo não concluído',str(exc))

    def _set_door_size(self,key,value):
        tool=self.controllers['wall'].openings.door_tool
        if abs(tool.sizes['door'][key]-value)<1e-9:return
        tool.sizes['door'][key]=value
        # Notifier updates sidebar, floating bar and preview exactly once.
        self.controllers['wall'].openings.notify_door_settings()

    def _sync_door_controls(self):
        if not self._door_size_fields:return
        tool=self.controllers['wall'].openings.door_tool
        selected=self._selected_door_instance()
        # When selection changes (and no conversion is staged), display the
        # real selected variant instead of the insertion tool's last variant.
        if selected is not None and self._door_draft_original is None:
            self._door_selected_variant=selected[2].get('leaf_variant','grid')
        for key,field in self._door_size_fields.items():
            old=field.blockSignals(True)
            field.setValue(tool.sizes['door'][key])
            field.blockSignals(old)
        if self._door_full_button is not None:
            self._door_full_button.setChecked(not tool.door_as_opening)
            self._door_void_button.setChecked(tool.door_as_opening)
        from .door_style_catalog import selected_style,selected_installation
        for combo,value in ((self._door_style_combo,selected_style(tool)),):
            if combo is not None:
                old=combo.blockSignals(True)
                idx=combo.findData(value)
                combo.setCurrentIndex(idx if idx>=0 else 0)
                combo.blockSignals(old)
        family=selected_installation(tool)
        is_sliding=isinstance(family,str) and family.startswith('sliding_')
        if is_sliding:self._last_sliding_family=family
        for button,chosen in ((self._door_system_swing,not is_sliding),
                              (self._door_system_slide,is_sliding)):
            if button is not None:
                was_blocked=button.blockSignals(True)
                button.setChecked(chosen)
                button.blockSignals(was_blocked)
        if self._door_sliding_options is not None and self._door_sliding_options.isHidden() == is_sliding:
            self._door_sliding_options.setVisible(is_sliding)
        if self._door_swing_options is not None and self._door_swing_options.isHidden() == (not is_sliding):
            self._door_swing_options.setVisible(not is_sliding)
        for combo,value in ((self._door_hinge_combo,tool.door_hinge),
                            (self._door_swing_combo,tool.door_swing)):
            if combo is not None:
                old=combo.blockSignals(True)
                idx=combo.findData(value)
                combo.setCurrentIndex(idx if idx>=0 else 0)
                combo.blockSignals(old)
        if self._door_sliding_type_combo is not None:
            old=self._door_sliding_type_combo.blockSignals(True)
            idx=self._door_sliding_type_combo.findData(self._last_sliding_family)
            self._door_sliding_type_combo.setCurrentIndex(idx if idx>=0 else 0)
            self._door_sliding_type_combo.blockSignals(old)
        if self._door_slide_combo is not None:
            old=self._door_slide_combo.blockSignals(True)
            side=self._door_slide_combo.findData(tool.door_slide_side)
            self._door_slide_combo.setCurrentIndex(side if side>=0 else 0)
            self._door_slide_combo.blockSignals(old)
        if getattr(self,'_edit_grooves_button',None) is not None:
            self._edit_grooves_button.setVisible(self._door_selected_variant=='grooved')
        if self._door_variant_combo is not None:
            blocked=self._door_variant_combo.blockSignals(True)
            idx=self._door_variant_combo.findData(self._door_selected_variant)
            if self._door_variant_combo.currentIndex()!=idx:
                self._door_variant_combo.setCurrentIndex(idx)
            self._door_variant_combo.blockSignals(blocked)
        if self._door_apply_button is not None:
            instance=self._selected_door_instance()
            available=instance is not None
            self._door_apply_button.setEnabled(available)
            self._door_apply_button.setToolTip(english(
                'Converte a porta selecionada, mantendo medidas e ancoragem.'
                if available else 'Selecione uma porta existente para habilitar a conversão.'))
            self._door_cancel_button.setEnabled(self._door_draft_original is not None)
            caption=('Porta selecionada · propriedades abaixo aplicam imediatamente'
                     if available else 'Nenhuma porta selecionada · configure a nova inserção')
            if self._door_instance_caption.text()!=caption:
                self._door_instance_caption.setText(english(caption))
        if self._door_style_preview is not None:
            from .door_leaf_editor import _preset_icon
            from .door_leaf_presets import LEAF_PRESETS
            preset=next((v for v in LEAF_PRESETS
                         if v[0]==selected_style(tool)),LEAF_PRESETS[0])
            if self._door_preview_key != preset[0]:
                self._door_style_preview.setPixmap(_preset_icon(preset).pixmap(QSize(92,128)))
                self._door_style_caption.setText(english(preset[1]))
                self._door_preview_key = preset[0]

    def _route_hosted_editor(self,key):
        """Move the ONE real WallController editor to Porta only for doors.

        Walls and windows retain the original panel, host actions, and editor.
        Widget ownership changes; signal connections do not.
        """
        wall=self.controllers.get('wall')
        if wall is None:return
        widget=getattr(wall,'opening_widget',None)
        if widget is None:return
        if key=='door':
            target=self._door_properties_layout
            parent=self._door_properties_host
        elif key=='wall':
            parent=getattr(wall,'_suite_opening_widget_section',None) or wall.panel
            target=parent.layout()
        else:return
        if widget.parentWidget() is parent:return
        was_hidden=widget.isHidden()
        current=widget.parentWidget()
        if current is not None and current.layout() is not None:
            current.layout().removeWidget(widget)
        # Also remove the original layout item, if owned by the wall page.
        if wall.panel.layout() is not None:wall.panel.layout().removeWidget(widget)
        self._door_properties_layout.removeWidget(widget)
        widget.setParent(parent)
        target.addWidget(widget)
        widget.setVisible(not was_hidden)

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
        showing=tool is not None and kind!="door"
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
        # Explicit category clicks select the real host tool. Automatic page
        # changes (selection/refresh) never activate creation.
        from .object_properties import TOOL_KEYS
        from .host import activate_tool, host_tool
        tool_key = TOOL_KEYS.get(key)
        if key=='door':
            from .wall_opening_ui import DOOR_TOOL_KEY
            tool_key=DOOR_TOOL_KEY
        if tool_key and self.app.viewport.active_tool is not host_tool(self.app, tool_key):
            activate_tool(self.app, tool_key)
        self.show_page(key)
        self.schedule_sync_context()

    def export_project_template(self):
        from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
        from .project_setup import export_template
        bim = self.controllers.get("bim")
        if bim is None:
            return
        name, ok = QInputDialog.getText(self.panel, "My template", "Template name:")
        if not ok or not str(name).strip():
            return
        path, _ = QFileDialog.getSaveFileName(
            self.panel, "Save settings template", "My_OpenTrace_Template.json",
            "Template OpenTrace (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            raw = self.app.document_data(default=None)
            from .bim import normalize_document_data
            export_template(normalize_document_data(raw), path, name)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.warning(self.panel, "Template", str(exc))
            return
        QMessageBox.information(self.panel, "Template", 
            "Settings template saved. Project geometry and objects were not exported.")

    def open_project_setup(self):
        from .project_setup_dialog import NewProjectSetupDialog
        bim = self.controllers.get("bim")
        if bim is None:
            return
        dialog = NewProjectSetupDialog(
            self.app, bim, self.panel,
            layer_controller=getattr(self.app.window, '_layer_combinations_controller', None))
        if dialog.exec():
            self.refresh_project_setup()

    def manage_libraries(self):
        """Choose small active packs without rebuilding an existing project."""
        from .resource_collections_ui import LibraryManagerDialog
        from .resource_collections import validate_collection
        from .bim import normalize_document_data
        import copy
        try:
            raw = self.app.document_data(default=None)
        except Exception:
            raw = None
        setup = raw.get('project_setup') if isinstance(raw, dict) else None
        selected = (setup.get('resource_libraries', []) if isinstance(setup, dict)
                    else ['ot:arq:basica'])
        dlg = LibraryManagerDialog(self.app, self.panel, selected=selected)
        if not dlg.exec():
            return
        # Works even for an untitled project that was not configured in the
        # new-project window. No assistant is required to browse or load packs.
        changed = normalize_document_data(copy.deepcopy(raw or {}))
        if not isinstance(changed.get('project_setup'), dict):
            changed['project_setup'] = {}
        changed['project_setup']['resource_libraries'] = dlg.selected_collections()
        changed['project_setup']['library_selection_mode'] = 'curated'
        self.app.set_document_data(changed)
        from .preset_catalog import set_active_collections
        set_active_collections(changed)
        for ctrl in self.controllers.values():
            preset_panel = getattr(ctrl, '_catalog_preset_panel', None)
            if preset_panel is not None:
                preset_panel.refresh()
        bim = self.controllers.get('bim')
        if bim is not None:
            bim.data = normalize_document_data(changed)
            bim.refresh()

    def refresh_project_setup(self):
        """Always allow the user to start an independent new project.

        Never depend on stale Home-tab tool state after Ctrl+N. The actual
        creation keeps the host's normal unsaved-changes confirmation.
        """
        self.project_setup_button.setEnabled(True)
        try:
            raw = self.app.document_data(default=None)
            setup = (raw or {}).get('project_setup') if isinstance(raw, dict) else None
        except Exception:
            setup = None
        if isinstance(setup, dict):
            self.project_setup_status.setText(
                'Current project: ' + str(setup.get('template_name') or '—') +
                ' · catalog: ' + str(setup.get('catalogue_name') or '—') +
                '. This button creates a new project; the current file is preserved until confirmation.')
        else:
            self.project_setup_status.setText(
                'Create a new project using a template, layers, catalog, and libraries. '
                'Available even if another project is already open.')

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
                f"Could not open alignment panel: {type(exc).__name__}: {exc}")

    def open_help(self,context=None):
        """Show chaptered documentation, without modifying modelling tool."""
        if self._help_dialog is None:
            from .help_dialog import HelpDialog
            self._help_dialog=HelpDialog(self.app.window)
        # A regular header click starts at "O que há de novo".
        self._help_dialog.show_for_context(
            context if isinstance(context,str) else None)

    def _auto_update_toggled(self, enabled):
        from .updater import set_auto_check_enabled
        set_auto_check_enabled(bool(enabled))
        if enabled:
            self._auto_check_timer.start(1500)
        else:
            self._auto_check_timer.stop()

    def _auto_check_updates_on_startup(self):
        from .updater import auto_check_enabled
        if auto_check_enabled() and self.update_manager is not None:
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
        self.object_properties.refresh()
        self._sync_queued=False;self._last_active_tool_id=id(getattr(self.app.viewport,"active_tool",None));self.sync_context();self.sync_mode_buttons()
        bar = getattr(self,"context_bar",None)
        if bar is not None:
            bar.refresh()
        self._sync_editor_sections()
        self._sync_opening_section()
        self._sync_door_controls()

    def show_page(self,key,show_dock=True):
        show_project = key == "project"
        if show_project:
            key = "home"  # Project information now lives within Home.
        if key not in self.pages:key="home"
        slot = self._property_slots.get(key)
        if slot is not None:
            slot.addWidget(self.object_properties)
            self._property_fallback.hide()
            self.object_properties.show()
        else:
            self._property_fallback_layout.addWidget(self.object_properties)
            self._property_fallback.setVisible(key not in ("home", "membrane"))
        if key=='door':
            self._route_hosted_editor('door')
        elif key=='wall':
            selected=getattr(self.controllers['wall'].fill_properties,'_spec',None)
            if (not isinstance(selected,dict) or selected.get('kind')!='door') and \
                    self._opening_tool_and_kind()[1]!='door':
                self._route_hosted_editor('wall')
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
        if key=="home":
            self.refresh_home()
            if show_project and self.home_project_section.isVisible():
                self.home_scroll.ensureWidgetVisible(self.home_project_section, 0, 12)
        self._sync_editor_sections()
        self._sync_opening_section()
        self._sync_door_controls()
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
               for key in ("bim", "project", "arrange", "profiles")):
            return
        slab_ctrl=self.controllers.get("slab")
        if slab_ctrl is not None and active is slab_ctrl.opening_tool:
            self._show_context_settings("slab")
            return
        opening_tool,opening_kind=self._opening_tool_and_kind()
        if opening_tool is not None:
            self._show_context_settings("door" if opening_kind=="door" else "wall")
            return
        current_fill=getattr(self.controllers['wall'].fill_properties,'_spec',None)
        if (isinstance(current_fill,dict) and current_fill.get('kind')=='door'):
            self._show_context_settings('door')
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
        self.refresh_project_setup()
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
