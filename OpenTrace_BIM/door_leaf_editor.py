# SPDX-License-Identifier: GPL-3.0-or-later
"""High-contrast graphical leaf and sash compositor, local transaction only.

A confirmed edit returns one JSON-safe composition. No scene writes, library
changes or external network use take place in this dialog.
"""
from __future__ import annotations

from pathlib import Path

import copy
import re
from PySide6.QtCore import Qt, QSize, QRectF, QPointF, QSettings
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter,
    QToolButton, QVBoxLayout, QWidget,
)
from .length_field import LengthField, has_document_units
from .door_leaf_grid import (DEFAULT_GRID, MATERIAL_GROUPS, PANEL_KINDS,
                             normalize_leaf_grid, part_group, leaf_shapes,
                             member_family, member_linked, resolved_member)
from .door_leaf_presets import LEAF_PRESETS, make_leaf_preset
from .door_leaf_preview import LeafPreview
from .door_grooves import DEFAULT_GROOVES, normalize_grooves
from .i18n import t, ui_locale, englishize_widget

TYPES=(("Vidro","glass","#8bc9dc"),
       ("Painel sólido","solid","#dac9ab"),
       ("Veneziana","louver","#b3a58a"),
       ("Vão livre","open","#d6e0ea"))
LABELS={"structure":"Structure", "glass":"Glass",
        "solid":"Solid panels", "louver":"Louvers"}
SHAPES=(("Retangular / quadrado","rect"),
        ("Circular","circle"), ("Perfil complexo da biblioteca","complex"))



def _english_part_name(name):
    """Translate legacy mesh labels only in UI, never change persistent names."""
    fixed={
        'Corpo liso da folha':'Plain leaf body',
        'Montante lateral':'Side stile',
        'Travessa inferior':'Bottom rail',
        'Travessa superior':'Top rail',
        'Travessa superior em arco':'Arched top rail',
        'Painel deslocável':'Movable infill',
    }
    if name in fixed:return fixed[name]
    for prefix,english in (('Montante ','Mullion '),('Travessa ','Transom '),
                           ('Painel ','Panel '),('Perfil visor ','Vision frame ')):
        if name.startswith(prefix):return english+name[len(prefix):]
    return t(name)


def _preset_icon(pattern):
    key,_title,cols,rows,kinds=pattern
    image=QPixmap(56,70)
    image.fill(Qt.transparent)
    painter=QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing,True)
    painter.setPen(QPen(QColor('#627989'),2))
    painter.setBrush(QColor('#e0d3bd'))
    painter.drawRect(QRectF(4,3,47,63))
    colors={item[1]:QColor(item[2]) for item in TYPES}
    if key=='movable_vision':
        painter.setBrush(colors['glass'])
        painter.drawRect(QRectF(15,17,25,22))
    else:
        ww,hh=43/cols,59/rows
        for row in range(rows):
            for col in range(cols):
                kind=kinds[row*cols+col]
                x=6+col*ww;y=5+(rows-1-row)*hh
                rect=QRectF(x+1,y+1,max(1,ww-2),max(1,hh-2))
                painter.setBrush(colors[kind]);painter.drawRect(rect)
                if kind=='louver':
                    for fraction in (.3,.5,.7):
                        yy=rect.top()+rect.height()*fraction
                        painter.drawLine(QPointF(rect.left()+2,yy),
                                         QPointF(rect.right()-2,yy))
        if key=='plain_solid' or key=='arch_solid':
            painter.setBrush(colors['solid']);painter.drawRect(QRectF(4,3,47,63))
    if key.startswith('arch_'):
        painter.setPen(QPen(QColor('#e48b27'),2))
        painter.drawArc(QRectF(4,-2,47,24),0,180*16)
    painter.end()
    return QIcon(image)


class DoorLeafGridDialog(QDialog):
    def __init__(self,spec,parent=None,catalog=None):
        super().__init__(parent)
        self._window=spec['kind']=='window'
        self._grooved=(not self._window and spec.get('leaf_variant')=='grooved')
        self._grooves=(normalize_grooves(spec, spec['width'], spec['height'])
                       if self._grooved else dict(DEFAULT_GROOVES))
        self._width=(spec['width']-2*spec['frame_thickness']
                     if self._window else spec['width'])
        self._height=(spec['height']-2*spec['frame_thickness']
                      if self._window else spec['height'])
        self._thickness=(spec['frame_thickness'] if self._window
                         else spec['leaf_thickness'])
        raw=spec.get('window_grid') if self._window else spec.get('leaf_grid')
        try:
            self._grid=normalize_leaf_grid(raw,self._width,self._height,self._thickness)
        except ValueError:
            self._grid=make_leaf_preset('full_glass',self._width,
                                        self._height,self._thickness)
        # Migrate the previous global width switch in the *draft only*.  Keep
        # the apparent dimensions rather than allowing an old uniform value to
        # leak into unrelated circular profiles/montantes.
        if self._grid.get('uniform_structure'):
            common=self._grid['structure_width']
            for field in ('stile_width','rail_width','mullion_width','transom_width'):
                self._grid[field]=common
            for cfg in self._grid.get('member_profiles',{}).values():
                if cfg.get('shape')=='circle':cfg['diameter']=common
            self._grid['uniform_structure']=False
            self._grid=normalize_leaf_grid(self._grid,self._width,self._height,self._thickness)
        self._selected=(0,0)
        self._part_selected=None
        self._part_kind='leaf_glass'
        self._saved={}
        self._remember_cells()
        self._fields={}
        self._update_lock=False
        self._catalog=dict(catalog or {})
        self._profiles={}
        try:
            from .profile_library import load_profiles
            self._profiles={p['id']:p for p in load_profiles()}
        except Exception:
            # Local profiles are optional; previously saved embedded snapshots
            # remain available even if QSettings/library cannot be read.
            pass
        self.setWindowTitle(t('Compositor visual de esquadrias — OpenTrace BIM'))
        self.setObjectName('opentrace_visual_leaf_editor_v2')
        self.resize(1200,790)
        self.setMinimumSize(860,600)
        checkbox_mark=(Path(__file__).resolve().parent/'assets'/'ui'/'checkbox_checked.png').as_posix()
        self.setStyleSheet('''
            QDialog#opentrace_visual_leaf_editor_v2,
            QWidget#opentrace_editor_settings { background:#f0f4f8; color:#203347; }
            QGroupBox {background:#ffffff;color:#203347;
                border:1px solid #cbd6e2;border-radius:7px;
                margin-top:13px;padding:12px 8px 8px; font-weight:600;}
            QCheckBox::indicator {width:18px;height:18px;border:1px solid #718b9e;
                border-radius:3px;background:#ffffff;}
            QCheckBox::indicator:checked {background:#217ba5;
                border:1px solid #155975;image:url("__OPENTRACE_CHECKMARK__");}
            QCheckBox::indicator:disabled {background:#d8dce1;border-color:#bec7cf;}
            QCheckBox::indicator:checked:disabled {image:none;background:#afc0ca;
                border:3px solid #d8dce1;}
            QGroupBox::title {subcontrol-origin:margin;left:12px;
                padding:0 5px;color:#173249;}
            QLabel,QCheckBox {color:#203347;background:transparent;}
            QLabel#opentrace_subtitle {color:#425b70;}
            QLabel#opentrace_feedback {color:#126044;}
            QSpinBox,QDoubleSpinBox,QComboBox {background:#ffffff;
                color:#14283b;selection-background-color:#cae8f8;
                selection-color:#12283b;border:1px solid #9eb2c5;
                border-radius:4px;min-height:26px;padding:2px 6px;}
            QComboBox QAbstractItemView {background:#ffffff;color:#172c40;
                selection-background-color:#d9ecf7;selection-color:#172c40;}
            QPushButton,QToolButton {background:#e6edf5;color:#173249;
                border:1px solid #a7b9ca;border-radius:5px;
                min-height:25px;padding:4px 9px;}
            QPushButton:hover,QToolButton:hover {background:#d5e8f5;}
            QToolButton:checked {background:#bedced;border:2px solid #377ca7;}
            QToolButton#opentrace_preset_tile {text-align:left;
                background:#fff;color:#173249;min-height:60px;padding:3px;}
            QToolButton#opentrace_preset_tile:hover {background:#e9f4fa;}
            QScrollArea {background:#f0f4f8;border:0;}
            QSplitter::handle {background:#c4d2de;}
        '''.replace('__OPENTRACE_CHECKMARK__', checkbox_mark))
        root=QVBoxLayout(self)
        root.setContentsMargins(15,12,15,11)
        root.setSpacing(8)
        heading=QLabel(t('Compositor visual do caixilho' if self._window
                         else 'Compositor visual da folha'),self)
        heading.setStyleSheet('font-size:19px;font-weight:700;color:#173249;')
        root.addWidget(heading)
        subtitle=QLabel(t('Edite as peças no desenho; clique nos perfis para atribuir materiais. '
                          'Tudo é aplicado somente ao confirmar.'),self)
        subtitle.setObjectName('opentrace_subtitle')
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)
        splitter=QSplitter(Qt.Horizontal,self)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter,1)

        visual=QWidget(splitter)
        left=QVBoxLayout(visual)
        left.setContentsMargins(0,0,5,0)
        camera=QHBoxLayout()
        self._front=QToolButton(self);self._front.setText(t('Elevação 2D'))
        self._front.setCheckable(True)
        self._front.clicked.connect(lambda: self._camera(False))
        self._iso=QToolButton(self);self._iso.setText(t('Isométrica 3D'))
        self._iso.setCheckable(True)
        self._iso.clicked.connect(lambda: self._camera(True))
        camera.addWidget(self._front);camera.addWidget(self._iso)
        camera.addStretch(1)
        self._rot_left=QPushButton('↶ 45°',self)
        self._rot_right=QPushButton('45° ↷',self)
        self._rot_left.clicked.connect(lambda:self._preview.rotate(-45))
        self._rot_right.clicked.connect(lambda:self._preview.rotate(45))
        camera.addWidget(self._rot_left);camera.addWidget(self._rot_right)
        left.addLayout(camera)
        self._preview=LeafPreview(self)
        self._preview.selected.connect(self._select_cell)
        self._preview.elementSelected.connect(self._select_part)
        self._preview.insetMoved.connect(self._drag_inset)
        left.addWidget(self._preview,1)
        self._selection_label=QLabel(self)
        self._selection_label.setWordWrap(True)
        left.addWidget(self._selection_label)
        infill=QHBoxLayout()
        self._kind_buttons={}
        for label,kind,color in TYPES:
            button=QToolButton(self)
            button.setText(t(label));button.setCheckable(True)
            button.clicked.connect(lambda _checked=False,k=kind:self._set_infill(k))
            self._kind_buttons[kind]=button
            infill.addWidget(button,1)
        left.addLayout(infill)
        hint=QLabel(t('No modo visor, arraste o vidro na elevação 2D ou use X/Z. '
                      'Clique em qualquer travessa/montante para editar seu material.'),self)
        hint.setObjectName('opentrace_subtitle');hint.setWordWrap(True)
        left.addWidget(hint)
        splitter.addWidget(visual)

        scroll=QScrollArea(splitter)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        settings=QWidget(scroll)
        settings.setObjectName('opentrace_editor_settings')
        right=QVBoxLayout(settings)
        right.setContentsMargins(5,1,8,4)
        right.setSpacing(8)
        groove_group=QGroupBox('Groove layout — traditional grooved leaf',settings)
        groove_form=QFormLayout(groove_group)
        self._groove_fields={}
        for name,label,minimum,maximum,step in (
            ('groove_count','Grooves (number)',1,12,1),
            ('groove_width','Groove width',.001,.03,.001),
            ('groove_end_margin','Top/bottom margin',.01,1.0,.005),
            ('groove_offset','Horizontal offset',-.30,.30,.005),
        ):
            control=QSpinBox(groove_group) if name=='groove_count' else LengthField(groove_group)
            control.setRange(minimum,maximum)
            if name!='groove_count':
                control.setDecimals(4);control.setSuffix(' m')
                control.setLocale(ui_locale());control.setKeyboardTracking(False)
            control.setSingleStep(step)
            control.valueChanged.connect(self._recalculate)
            groove_form.addRow(label,control)
            self._groove_fields[name]=control
        right.addWidget(groove_group)
        groove_group.setVisible(self._grooved)
        gallery=QGroupBox(t('Estilos editáveis'),settings)
        tile_layout=QGridLayout(gallery)
        tile_layout.setHorizontalSpacing(6)
        for index,preset in enumerate(LEAF_PRESETS):
            key,name,*_=preset
            tile=QToolButton(gallery)
            tile.setObjectName('opentrace_preset_tile')
            tile.setText(t(name));tile.setIcon(_preset_icon(preset))
            tile.setIconSize(QSize(38,49))
            tile.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            tile.setMinimumSize(145,63)
            tile.clicked.connect(lambda _checked=False,k=key:self._apply_preset(k))
            tile_layout.addWidget(tile,index//2,index%2)
        right.addWidget(gallery)
        gallery.setVisible(not self._grooved)

        layout=QGroupBox(t('Tipo de composição e divisões'),settings)
        form=QFormLayout(layout)
        self._mode=QComboBox(layout)
        self._mode.addItem(t('Malha de montantes e travessas'),'grid')
        self._mode.addItem(t('Folha lisa com visor deslocável'),'inset')
        self._mode.currentIndexChanged.connect(self._recalculate)
        form.addRow(t('Composição'),self._mode)
        for key,title in (('columns','Colunas'),('rows','Linhas')):
            field=QSpinBox(layout)
            field.setRange(1,8)
            field.valueChanged.connect(self._recalculate)
            self._fields[key]=field
            form.addRow(t(title),field)
        right.addWidget(layout)
        layout.setVisible(not self._grooved)
        self._grid_group=layout

        structure=QGroupBox(t('Ativar estrutura e editar larguras'),settings)
        form=QFormLayout(structure)
        self._checks={}
        for key,title in (('stiles_enabled','Include side stiles'),
                          ('rails_enabled','Include top/bottom rails')):
            toggle=QCheckBox(t(title),structure)
            # Defaults for glass/panel presets are ON, but this is an actual
            # user-editable option, not a read-only safety indicator. Changing
            # it updates leaf_shapes, the preview and the mesh on confirmation.
            toggle.setToolTip('Toggle this external member in the leaf. '
                              'Glazed and multi-panel presets start with a full frame.')
            toggle.setObjectName('opentrace_'+key)
            toggle.toggled.connect(self._recalculate)
            self._checks[key]=toggle
            form.addRow(toggle)
        sizes=(('stile_width','Montantes laterais'),
               ('rail_width','Largura travessas externas · ret./complexo'),
               ('mullion_width','Montantes internos'),
               ('transom_width','Largura travessas internas · ret./complexo'),
               ('glass_thickness','Espessura dos vidros'),
               ('panel_thickness','Espessura dos painéis'))
        for key,title in sizes:
            self._add_measure(form,key,title,maximum=0.5)
        right.addWidget(structure)
        structure.setVisible(not self._grooved)

        curved=QGroupBox(t('Topo em arco circular'),settings)
        form=QFormLayout(curved)
        arc=QCheckBox(t('Ativar arco superior'),curved)
        arc.toggled.connect(self._recalculate)
        self._checks['top_arc_enabled']=arc
        form.addRow(arc)
        self._add_measure(form,'top_arc_rise','Flecha do arco (altura)',maximum=2.0)
        right.addWidget(curved)
        curved.setVisible(not self._grooved)

        inset=QGroupBox(t('Visor / painel deslocável'),settings)
        form=QFormLayout(inset)
        self._insert_fields={}
        for key,title in (('width','Largura do visor'),('height','Altura do visor'),
                          ('frame_width','Largura da moldura')):
            field=LengthField(inset)
            field.setLocale(ui_locale())
            field.setDecimals(4)
            field.setRange(.001,1 if key in ('x','z') else 4)
            field.setSingleStep(.02 if key in ('x','z') else .005)
            field.setSuffix(' m')
            field.setKeyboardTracking(False)
            field.valueChanged.connect(self._recalculate)
            self._insert_fields[key]=field
            form.addRow(t(title),field)
        # Human-friendly distances from actual sash edges. Canonical JSON
        # stores centres in metres-independent ratios for backward compatibility.
        self._unit_factors={'m':1.,'cm':.01,'mm':.001}
        self._display_unit=str(QSettings().value('OpenTrace_BIM/length_unit','cm'))
        if self._display_unit not in self._unit_factors:self._display_unit='cm'
        if has_document_units():self._display_unit='m'
        self._unit_selector=QComboBox(inset)
        for unit in ('m','cm','mm'):self._unit_selector.addItem(unit,unit)
        self._unit_selector.setCurrentIndex(self._unit_selector.findData(self._display_unit))
        self._unit_selector.currentIndexChanged.connect(self._change_length_unit)
        form.addRow(t('Unidades de deslocamento'),self._unit_selector)
        if has_document_units():
            # The document's units decide; this selector predates them.
            self._unit_selector.hide()
            selector_label=form.labelForField(self._unit_selector)
            if selector_label is not None:selector_label.hide()
        self._edge_fields={}
        for key,title in (('left','Afastamento esquerdo · folha → visor'),
                          ('right','Afastamento direito · visor → folha'),
                          ('bottom','Afastamento inferior · folha → visor'),
                          ('top','Afastamento superior · visor → folha')):
            edge=LengthField(inset)
            edge.setLocale(ui_locale());edge.setDecimals(3)
            edge.setRange(0,10000);edge.setSingleStep(1)
            edge.setKeyboardTracking(False)
            edge.setSuffix(' '+self._display_unit)
            edge.valueChanged.connect(lambda _, k=key:self._edge_changed(k))
            self._edge_fields[key]=edge
            form.addRow(t(title),edge)
        frame=QCheckBox(t('Adicionar moldura própria ao visor'),inset)
        frame.toggled.connect(self._recalculate)
        self._checks['insert_frame_enabled']=frame
        form.addRow(frame)
        self._insert_group=inset
        right.addWidget(inset)
        inset.setVisible(False)

        profile_group=QGroupBox(t('Seção das travessas (geometria real)'),settings)
        form=QFormLayout(profile_group)
        self._profile_widgets={}
        for member,description in (('rail','Travessas externas'),
                                   ('transom','Travessas internas')):
            mode=QComboBox(profile_group)
            for text,value in SHAPES: mode.addItem(t(text),value)
            mode.currentIndexChanged.connect(self._recalculate)
            form.addRow(t(description),mode)
            diameter=LengthField(profile_group)
            diameter.setRange(.002,.5);diameter.setDecimals(4)
            diameter.setSingleStep(.005);diameter.setSuffix(' m')
            diameter.setLocale(ui_locale());diameter.setKeyboardTracking(False)
            diameter.valueChanged.connect(self._recalculate)
            form.addRow(t('Diâmetro · '+description),diameter)
            depth=LengthField(profile_group)
            depth.setRange(.002,.5);depth.setDecimals(4)
            depth.setSingleStep(.005);depth.setSuffix(' m')
            depth.setLocale(ui_locale());depth.setKeyboardTracking(False)
            depth.valueChanged.connect(self._recalculate)
            form.addRow(t('Profundidade · '+description),depth)
            library=QComboBox(profile_group)
            library.addItem(t('Escolha um perfil salvo'),None)
            for pid,profile in sorted(self._profiles.items(),key=lambda p:p[1]['name']):
                library.addItem(profile['name'],pid)
            library.currentIndexChanged.connect(self._recalculate)
            form.addRow(t('Perfil da biblioteca'),library)
            self._profile_widgets[member]=(mode,diameter,depth,library)
        right.addWidget(profile_group)
        profile_group.setVisible(not self._grooved)

        names=set(self._catalog)
        names.update(v.get('mat') for v in self._grid.get('kind_materials',{}).values()
                     if isinstance(v,dict) and v.get('mat'))
        names.update(v.get('mat') for v in self._grid.get('part_materials',{}).values()
                     if isinstance(v,dict) and v.get('mat'))
        names.update(v.get('mat') for v in self._grid.get('member_materials',{}).values()
                     if isinstance(v,dict) and v.get('mat'))
        names.update(d.get('material',{}).get('mat') for d in self._grid.get('member_overrides',{}).values()
                     if isinstance(d.get('material'),dict) and d['material'].get('mat'))
        self._names=sorted(names,key=str.casefold)
        rail_links=QGroupBox(t('Uniformidade independente da estrutura'),settings)
        form=QFormLayout(rail_links)
        self._rail_material_combos={}
        for family,flag,text in (
                ('rail','uniform_external_rails','Perfis externos uniformes · travessas e montantes'),
                ('transom','uniform_internal_transoms','Perfis internos uniformes · travessas e montantes')):
            toggle=QCheckBox(t(text),rail_links)
            toggle.setToolTip(t('Liga largura, seção e material das travessas e montantes deste grupo. '
                                'Desligue e clique em uma peça para editar individualmente.'))
            toggle.toggled.connect(lambda _checked=False,f=family:self._toggle_member_link(f))
            self._checks[flag]=toggle
            form.addRow(toggle)
            combo=self._material_combo(rail_links)
            combo.currentIndexChanged.connect(self._recalculate)
            self._rail_material_combos[family]=combo
            form.addRow(t('Material · '+('externas' if family=='rail' else 'internas')),combo)
            choose=QPushButton(t('Selecionar perfil '+('externo' if family=='rail' else 'interno')+
                                 ' para edição individual'),rail_links)
            choose.clicked.connect(lambda _=False,f=family:self._select_member_group(f))
            form.addRow(choose)
        right.addWidget(rail_links)
        rail_links.setVisible(not self._grooved)

        individual=QGroupBox(t('Perfil selecionado · opções individuais'),settings)
        form=QFormLayout(individual)
        self._individual_help=QLabel(t('Desligue a uniformidade correspondente e clique '
                          'em um montante ou travessa na elevação 2D.'),individual)
        self._individual_help.setWordWrap(True)
        form.addRow(self._individual_help)
        self._individual_width=LengthField(individual)
        self._individual_width.setRange(.001,.5);self._individual_width.setDecimals(4)
        self._individual_width.setSingleStep(.005)
        self._individual_width.setSuffix(' m')
        self._individual_width.setLocale(ui_locale());self._individual_width.setKeyboardTracking(False)
        self._individual_width.valueChanged.connect(self._recalculate)
        form.addRow(t('Largura individual'),self._individual_width)
        self._individual_shape=QComboBox(individual)
        for title,value in SHAPES:self._individual_shape.addItem(t(title),value)
        self._individual_shape.currentIndexChanged.connect(self._recalculate)
        form.addRow(t('Seção individual'),self._individual_shape)
        self._individual_diameter=LengthField(individual)
        self._individual_diameter.setRange(.002,.5);self._individual_diameter.setDecimals(4)
        self._individual_diameter.setSingleStep(.005);self._individual_diameter.setSuffix(' m')
        self._individual_diameter.setLocale(ui_locale());self._individual_diameter.setKeyboardTracking(False)
        self._individual_diameter.valueChanged.connect(self._recalculate)
        form.addRow(t('Diâmetro individual'),self._individual_diameter)
        self._individual_depth=LengthField(individual)
        self._individual_depth.setRange(.002,.5);self._individual_depth.setDecimals(4)
        self._individual_depth.setSingleStep(.005);self._individual_depth.setSuffix(' m')
        self._individual_depth.setLocale(ui_locale());self._individual_depth.setKeyboardTracking(False)
        self._individual_depth.valueChanged.connect(self._recalculate)
        form.addRow(t('Profundidade individual'),self._individual_depth)
        self._individual_library=QComboBox(individual)
        self._individual_library.addItem(t('Escolha um perfil salvo'),None)
        for pid,profile in sorted(self._profiles.items(),key=lambda p:p[1]['name']):
            self._individual_library.addItem(profile['name'],pid)
        self._individual_library.currentIndexChanged.connect(self._recalculate)
        form.addRow(t('Perfil complexo individual'),self._individual_library)
        right.addWidget(individual)
        individual.setVisible(not self._grooved)
        self._individual_group=individual

        material_group=QGroupBox('MATERIALS — structure, glass and panels',settings)
        form=QFormLayout(material_group)
        self._uniform_materials={}
        self._kind_material_combos={}
        for group in MATERIAL_GROUPS:
            uniform=QCheckBox(t(f'Material uniforme · {LABELS[group].lower()}'),material_group)
            uniform.toggled.connect(self._recalculate)
            self._uniform_materials[group]=uniform
            form.addRow(uniform)
            combo=self._material_combo(material_group)
            combo.currentIndexChanged.connect(self._recalculate)
            form.addRow(t(f'Material · {LABELS[group].lower()}'),combo)
            self._kind_material_combos[group]=combo
        self._piece_label=QLabel(t('Material da peça selecionada'),material_group)
        self._piece_label.setWordWrap(True)
        form.addRow(self._piece_label)
        self._piece_material=self._material_combo(material_group)
        self._piece_material.currentIndexChanged.connect(self._edit_piece_material)
        form.addRow(t('Somente esta peça'),self._piece_material)
        right.addWidget(material_group)
        material_group.setVisible(not self._grooved)
        right.addStretch(1)
        scroll.setWidget(settings)
        splitter.addWidget(scroll)
        splitter.setSizes([640,510])

        self._message=QLabel('',self)
        self._message.setObjectName('opentrace_feedback')
        self._message.setWordWrap(True)
        root.addWidget(self._message)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel,
                                 Qt.Horizontal,self)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        self._buttons=buttons
        root.addWidget(buttons)
        if self._grooved:
            for button in self._kind_buttons.values():button.setEnabled(False)
            hint.setText('Change the groove parameters on the right. Preview updates live; OK commits the changes.')
            self._selection_label.setText('Grooved leaf — front and 3D preview')
        self._camera(False)
        self._refresh()
        englishize_widget(self)

    def _add_measure(self,form,key,title,maximum=1.0):
        field=LengthField(self)
        field.setLocale(ui_locale())
        field.setDecimals(4)
        field.setRange(.001,maximum)
        field.setSingleStep(.005)
        field.setSuffix(' m')
        field.setKeyboardTracking(False)
        field.valueChanged.connect(self._recalculate)
        form.addRow(t(title),field)
        self._fields[key]=field

    def _material_combo(self,parent):
        combo=QComboBox(parent)
        combo.setMaxVisibleItems(18)
        combo.addItem(t('Padrão / sem material específico'),None)
        for name in self._names:combo.addItem(name,name)
        return combo

    def _recipe(self,name):
        if name is None:return None
        data=self._catalog.get(name)
        recipe={'mat':name}
        if isinstance(data,dict):
            recipe.update({k:copy.deepcopy(v) for k,v in data.items()
                           if k in ('color','texture','opacity') and v is not None})
        return recipe

    def _remember_cells(self):
        g=self._grid
        self._saved={(r,c):g['cell_types'][r*g['columns']+c]
                     for r in range(g['rows']) for c in range(g['columns'])}

    def _camera(self,isometric):
        self._preview.set_isometric(isometric)
        self._front.setChecked(not isometric);self._iso.setChecked(isometric)
        self._rot_left.setEnabled(isometric);self._rot_right.setEnabled(isometric)

    def _select_cell(self,row,col):
        self._selected=(row,col)
        self._refresh_selection()

    def _select_part(self,part_id,kind):
        self._part_selected=part_id
        self._part_kind=kind
        self._sync_individual_fields()
        self._refresh_selection()

    def _drag_inset(self,x,z):
        if self._mode.currentData()!='inset':return
        self._grid['insert']['x']=x
        self._grid['insert']['z']=z
        self._recalculate()

    def _change_length_unit(self,*_):
        if self._update_lock:return
        unit=self._unit_selector.currentData()
        if unit not in self._unit_factors:return
        self._display_unit=unit
        QSettings().setValue('OpenTrace_BIM/length_unit',unit)
        self._sync_edge_fields()

    def _sync_edge_fields(self):
        insert=self._grid['insert'];factor=self._unit_factors[self._display_unit]
        left=self._width*insert['x']-insert['width']/2
        bottom=self._height*insert['z']-insert['height']/2
        sides={'left':left,'right':self._width-left-insert['width'],
               'bottom':bottom,'top':self._height-bottom-insert['height']}
        previous=self._update_lock;self._update_lock=True
        try:
            for key,field in self._edge_fields.items():
                field.setSuffix(' '+self._display_unit)
                value=max(0.,sides[key])/factor
                field.setValue(value if has_document_units() else round(value,3))
        finally:self._update_lock=previous

    def _edge_changed(self,key):
        if self._update_lock or self._mode.currentData()!='inset':return
        insert=self._grid['insert']
        distance=self._edge_fields[key].value()*self._unit_factors[self._display_unit]
        if key=='left':insert['x']=(distance+insert['width']/2)/self._width
        elif key=='right':insert['x']=(self._width-distance-insert['width']/2)/self._width
        elif key=='bottom':insert['z']=(distance+insert['height']/2)/self._height
        else:insert['z']=(self._height-distance-insert['height']/2)/self._height
        self._recalculate()

    def _set_infill(self,kind):
        if kind not in PANEL_KINDS:return
        if self._mode.currentData()=='inset':
            self._grid['insert']['kind']=kind
            self._part_selected='insert'
        else:
            self._saved[self._selected]=kind
            r,c=self._selected
            self._part_selected=f'cell_{r}_{c}'
        self._part_kind='leaf_'+kind
        self._recalculate()

    def _edit_piece_material(self,*_):
        if self._update_lock or not self._part_selected:return
        recipe=self._recipe(self._piece_material.currentData())
        family=member_family(self._part_selected)
        group=part_group(self._part_kind)
        if family and member_linked(self._grid,family):
            # The uniform group remains uniform; the selection edits ALL of it.
            combo=self._rail_material_combos[family]
            blocked=combo.blockSignals(True)
            combo.setCurrentIndex(max(0,combo.findData(self._piece_material.currentData())))
            combo.blockSignals(blocked)
            self._grid.setdefault('member_materials',{})[family]=recipe
        elif family:
            self._grid.setdefault('member_overrides',{}).setdefault(
                self._part_selected,{})['material']=recipe
        elif (group in MATERIAL_GROUPS and
              self._uniform_materials.get(group) is not None and
              self._uniform_materials[group].isChecked()):
            # Selecting any component edits its material family, not an
            # invisible overridden member disabled by the checkbox.
            combo=self._kind_material_combos[group]
            blocked=combo.blockSignals(True)
            combo.setCurrentIndex(max(0,combo.findData(self._piece_material.currentData())))
            combo.blockSignals(blocked)
            self._grid.setdefault('kind_materials',{})[group]=recipe
        elif group in MATERIAL_GROUPS:
            self._grid.setdefault('part_materials',{})[self._part_selected]=recipe
        else:
            return  # Nothing selected / unknown category during Qt signal setup.
        self._recalculate()

    def _candidate(self):
        data=copy.deepcopy(self._grid)
        for key,field in self._fields.items():data[key]=field.value()
        for key,field in self._checks.items():
            if not key.startswith('insert_'):data[key]=field.isChecked()
        data['uniform_structure']=False  # legacy global switch is read-only
        data['mode']=self._mode.currentData()
        cols,rows=data['columns'],data['rows']
        data['cell_types']=[self._saved.get((r,c),'glass')
                            for r in range(rows) for c in range(cols)]
        insert=copy.deepcopy(data.get('insert',DEFAULT_GRID['insert']))
        for key,field in self._insert_fields.items():insert[key]=field.value()
        insert['frame_enabled']=self._checks['insert_frame_enabled'].isChecked()
        data['insert']=insert
        materials=data.setdefault('kind_materials',{})
        uniform=data.setdefault('uniform_materials',{})
        for group in MATERIAL_GROUPS:
            uniform[group]=self._uniform_materials[group].isChecked()
            materials[group]=self._recipe(self._kind_material_combos[group].currentData())
        profiles={}
        for group,(shape,diameter,depth,library) in self._profile_widgets.items():
            old=data.get('member_profiles',{}).get(group,{})
            profile=copy.deepcopy(old)
            profile['shape']=shape.currentData()
            profile['diameter']=diameter.value()
            profile['depth']=depth.value()
            if profile['shape']=='complex':
                pid=library.currentData()
                if pid in self._profiles:
                    profile['profile_ref']=pid
                    profile['profile_data']=copy.deepcopy(self._profiles[pid])
            profiles[group]=profile
        data['member_profiles']=profiles
        data['member_materials']={family:self._recipe(combo.currentData())
                                  for family,combo in self._rail_material_combos.items()}
        family=member_family(self._part_selected or '')
        if family and not member_linked(data,family):
            override=copy.deepcopy(data.setdefault('member_overrides',{}).get(self._part_selected,{}))
            override['width']=self._individual_width.value()
            cfg=copy.deepcopy(override.get('profile',profiles[family]))
            cfg['shape']=self._individual_shape.currentData()
            cfg['diameter']=self._individual_diameter.value()
            cfg['depth']=self._individual_depth.value()
            if cfg['shape']=='complex':
                pid=self._individual_library.currentData()
                if pid in self._profiles:
                    cfg['profile_ref']=pid
                    cfg['profile_data']=copy.deepcopy(self._profiles[pid])
            override['profile']=cfg
            data['member_overrides'][self._part_selected]=override
        return normalize_leaf_grid(data,self._width,self._height,self._thickness)

    def _select_member_group(self,family):
        if family=='rail':
            part,kind='rail_top','leaf_rail'
        elif self._fields['rows'].value()>1:
            part,kind='transom_1','leaf_transom'
        elif self._fields['columns'].value()>1:
            part,kind='mullion_1','leaf_mullion'
        else:
            self._individual_help.setText(t('Não existem montantes/travessas internos. '
                                             'Aumente linhas ou colunas.'))
            return
        self._part_selected=part;self._part_kind=kind
        self._sync_individual_fields()
        self._refresh_selection()

    def _toggle_member_link(self,family):
        if self._update_lock:return
        # First switch the local resolver to the new state. This is essential:
        # otherwise unlinking overwrites saved personal widths with the old
        # linked width on the next recalculate.
        key='uniform_external_rails' if family=='rail' else 'uniform_internal_transoms'
        self._grid[key]=self._checks[key].isChecked()
        if member_family(self._part_selected or '')!=family:
            self._select_member_group(family)
        else:
            self._sync_individual_fields()
        self._recalculate()

    def _sync_individual_fields(self):
        """Only a selection event changes the inspector's target/values."""
        member=resolved_member(self._grid,self._part_selected or '')
        self._update_lock=True
        try:
            if member:
                profile=member['profile']
                self._individual_width.setValue(member['width'])
                self._individual_shape.setCurrentIndex(max(0,self._individual_shape.findData(
                    profile.get('shape','rect'))))
                self._individual_diameter.setValue(profile.get('diameter',member['width']))
                self._individual_depth.setValue(profile.get('depth',self._thickness))
                pid=profile.get('profile_ref')
                if pid and self._individual_library.findData(pid)<0 and profile.get('profile_data'):
                    self._individual_library.addItem(profile['profile_data'].get('name',pid),pid)
                self._individual_library.setCurrentIndex(max(0,self._individual_library.findData(pid)))
        finally:
            self._update_lock=False

    def _refresh_selection(self):
        mode=self._grid['mode']
        if mode=='inset':
            kind=self._grid['insert']['kind']
            text=t('Visor deslocável · selecione o vidro ou a moldura')
        else:
            r,c=self._selected
            kind=self._saved.get((r,c),'glass')
            text=t('Coluna {0}, linha {1} · clique na estrutura para editar a peça').format(c+1,r+1)
        if self._part_selected and not self._part_selected.startswith('cell_'):
            selected=next((name for pid,name,_type,poly in leaf_shapes(
                self._grid,self._width,self._height) if pid==self._part_selected),
                self._part_selected)
            text=t('Selecionado: ')+_english_part_name(selected)
            if self._part_selected=='insert':kind=self._grid['insert']['kind']
        self._selection_label.setText(text)
        for k,b in self._kind_buttons.items():b.setChecked(k==kind)
        part_id=self._part_selected
        group=part_group(self._part_kind)
        self._piece_label.setText(t('Material da peça: ')+(part_id or '—'))
        family=member_family(part_id or '')
        can_edit_family=bool(family and not member_linked(self._grid,family))
        self._individual_group.setEnabled(can_edit_family)
        self._individual_help.setText(t(('Peça: '+str(part_id)) if can_edit_family else
                       'Desligue a uniformidade correspondente e selecione um montante ou travessa.'))
        self._individual_width.setEnabled(can_edit_family and
                                           self._individual_shape.currentData()!='circle')
        self._individual_diameter.setEnabled(can_edit_family and
                                              self._individual_shape.currentData()=='circle')
        self._individual_depth.setEnabled(can_edit_family and
                                           self._individual_shape.currentData()!='circle')
        self._individual_library.setEnabled(can_edit_family and
                                             self._individual_shape.currentData()=='complex')
        self._piece_material.setEnabled(bool(part_id) and group in MATERIAL_GROUPS)
        self._update_lock=True
        try:
            from .door_leaf_grid import grid_material
            material=grid_material(self._grid,part_id,self._part_kind)
            mat=material.get('mat') if isinstance(material,dict) else None
            index=self._piece_material.findData(mat)
            self._piece_material.setCurrentIndex(max(0,index))
        finally:
            self._update_lock=False
        self._preview.set_composition(self._grid,self._width,self._height,
                                       self._thickness,self._selected,
                                       part=self._part_selected)

    def _recalculate(self,*_):
        if self._update_lock:return
        if self._grooved:
            try:
                self._grooves=normalize_grooves(
                    {key:field.value() for key,field in self._groove_fields.items()},
                    self._width,self._height)
            except ValueError as exc:
                self._message.setText(str(exc))
                self._message.setStyleSheet('color:#ad2929;font-weight:600;')
                self._buttons.button(QDialogButtonBox.Ok).setEnabled(False)
                return
            self._buttons.button(QDialogButtonBox.Ok).setEnabled(True)
            self._message.setText('Valid groove dimensions — changes are local until OK')
            self._message.setStyleSheet('color:#176348;font-weight:600;')
            self._preview.set_grooved(self._grooves,self._width,self._height,self._thickness)
            return
        row,col=self._selected
        self._selected=(min(row,self._fields['rows'].value()-1),
                        min(col,self._fields['columns'].value()-1))
        # Do not lock or force-check these controls for multi-panel/glazed
        # compositions. Presets initialise a closed frame, but the operator
        # must be able to enable/disable each member. _candidate() reads the
        # actual checkbox state and the renderer/host use the same geometry.
        try:
            self._grid=self._candidate()
        except ValueError as exc:
            self._message.setText(t('Corrija as medidas: ')+t(str(exc)))
            self._message.setStyleSheet('color:#ad2929;font-weight:600;')
            self._buttons.button(QDialogButtonBox.Ok).setEnabled(False)
            return
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(True)
        self._message.setText(t('Composição válida · alterações locais até confirmar'))
        self._message.setStyleSheet('color:#176348;font-weight:600;')
        inset=self._grid['mode']=='inset'
        self._insert_group.setVisible(inset and not self._grooved)
        for name in ('columns','rows'):
            self._fields[name].setEnabled(not inset)
        if inset and self._part_selected and self._part_selected.startswith('cell_'):
            self._part_selected='insert'
        self._fields['stile_width'].setEnabled(self._checks['stiles_enabled'].isChecked())
        self._fields['rail_width'].setEnabled(
            self._checks['rails_enabled'].isChecked() and
            self._profile_widgets['rail'][0].currentData()!='circle')
        self._fields['mullion_width'].setEnabled(True)
        self._fields['transom_width'].setEnabled(
            self._profile_widgets['transom'][0].currentData()!='circle')
        self._fields['top_arc_rise'].setEnabled(self._checks['top_arc_enabled'].isChecked())
        self._insert_fields['frame_width'].setEnabled(self._checks['insert_frame_enabled'].isChecked())
        for family,combo in self._rail_material_combos.items():
            combo.setEnabled(member_linked(self._grid,family))
        for group,(shape,diameter,depth,library) in self._profile_widgets.items():
            mode=shape.currentData()
            diameter.setEnabled(mode=='circle')
            depth.setEnabled(mode in ('rect','complex'))
            library.setEnabled(mode=='complex')
        self._sync_edge_fields()
        self._refresh_selection()

    def _refresh(self):
        if self._grooved:
            self._update_lock=True
            try:
                for key,field in self._groove_fields.items():field.setValue(self._grooves[key])
            finally:self._update_lock=False
            self._recalculate()
            return
        self._update_lock=True
        try:
            for key,field in self._fields.items():field.setValue(self._grid[key])
            for key,field in self._checks.items():
                if key=='insert_frame_enabled':
                    field.setChecked(self._grid['insert']['frame_enabled'])
                else:field.setChecked(self._grid[key])
            self._mode.setCurrentIndex(max(0,self._mode.findData(self._grid['mode'])))
            for key,field in self._insert_fields.items():
                field.setValue(self._grid['insert'][key])
            for group in MATERIAL_GROUPS:
                self._uniform_materials[group].setChecked(
                    self._grid['uniform_materials'][group])
                recipe=self._grid.get('kind_materials',{}).get(group)
                name=recipe.get('mat') if isinstance(recipe,dict) else None
                combo=self._kind_material_combos[group]
                combo.setCurrentIndex(max(0,combo.findData(name)))
            for family,combo in self._rail_material_combos.items():
                recipe=self._grid.get('member_materials',{}).get(family)
                mat=recipe.get('mat') if isinstance(recipe,dict) else None
                combo.setCurrentIndex(max(0,combo.findData(mat)))
            for group,(shape,diameter,depth,library) in self._profile_widgets.items():
                cfg=self._grid.get('member_profiles',{}).get(group,{})
                shape.setCurrentIndex(max(0,shape.findData(cfg.get('shape','rect'))))
                diameter.setValue(cfg.get('diameter',.042))
                depth.setValue(cfg.get('depth',self._thickness))
                pid=cfg.get('profile_ref')
                if pid and library.findData(pid)<0 and cfg.get('profile_data'):
                    library.addItem(cfg['profile_data'].get('name',pid),pid)
                library.setCurrentIndex(max(0,library.findData(pid)))
        finally:
            self._update_lock=False
        self._sync_individual_fields()
        self._sync_edge_fields()
        self._recalculate()

    def _apply_preset(self,key):
        try:
            result=make_leaf_preset(key,self._width,self._height,
                                    self._thickness,self._grid)
        except ValueError as exc:
            self._message.setText(t(str(exc)));return
        self._grid=result
        self._remember_cells()
        self._selected=(0,0);self._part_selected=None
        self._refresh()

    def result_grid(self):
        return self._candidate()

    def result_grooves(self):
        """Return only the edited groove parameters; do not alter leaf variant."""
        if not self._grooved:
            raise ValueError('This is not a grooved leaf.')
        return normalize_grooves(self._grooves,self._width,self._height)

    def _validate(self):
        try:self.result_grooves() if self._grooved else self.result_grid()
        except ValueError as exc:
            QMessageBox.warning(self,t('Composição da folha'),t(str(exc)))
            return
        self.accept()
