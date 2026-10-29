# SPDX-License-Identifier: GPL-3.0-or-later
"""Editable orthographic/isometric preview of actual parametric XZ profiles.

All polygons originate in ``door_leaf_grid.leaf_shapes``. Inset glass and
curved arches are therefore drawn from exactly the same footprint as the mesh.
"""
from __future__ import annotations

import math
import hashlib
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF, QFont, QBrush, QPixmap, QPainterPath
from PySide6.QtWidgets import QWidget
from .length_field import format_length
from .door_grooves import groove_spans, normalize_grooves
from .door_leaf_grid import (leaf_shapes, part_group, member_widths, arc_height,
                             grid_material, cell_rectangles, resolved_member)

INK=QColor('#273948')
COLORS={
    'leaf_stile':QColor('#ae9875'), 'leaf_rail':QColor('#ae9875'),
    'leaf_mullion':QColor('#ae9875'),'leaf_transom':QColor('#ae9875'),
    'leaf_solid':QColor('#e2d5bd'),'leaf_glass':QColor('#89c9d9'),
    'leaf_louver':QColor('#bdab8a'),
}


def _shade(color, factor):
    return QColor(*(max(0,min(255,round(v*factor)))
                    for v in (color.red(),color.green(),color.blue())))


def _inside_polygon(point,poly):
    coords=[(p.x(),p.y()) for p in poly]
    hit=False
    for i in range(len(coords)):
        ax,ay=coords[i-1]; bx,by=coords[i]
        if (ay>point.y())!=(by>point.y()):
            cross=ax+(point.y()-ay)*(bx-ax)/(by-ay)
            if point.x()<cross:hit=not hit
    return hit


class LeafPreview(QWidget):
    selected=Signal(int,int)
    elementSelected=Signal(str,str)
    insetMoved=Signal(float,float)

    def __init__(self,parent=None):
        super().__init__(parent)
        self._grid=None
        self._grooves=None
        self._width=.9;self._height=2.1;self._thickness=.035
        self._isometric=False;self._angle=45
        self._selected=(0,0)
        self._part_selected=None
        self._hits=[]
        self._dragging=False
        self._layout=None
        self._texture_cache={}
        self.setMinimumSize(340,330)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setToolTip('Click glazing, panels or profiles; drag the inset in 2D')

    def set_composition(self,grid,width,height,thickness,selected=None,part=None):
        self._grooves=None
        self._grid=grid;self._width=width;self._height=height;self._thickness=thickness
        if selected is not None:self._selected=selected
        self._part_selected=part
        self.update()

    def set_grooved(self,grooves,width,height,thickness):
        self._grid=None
        self._grooves=normalize_grooves(grooves,width,height)
        self._width=width;self._height=height;self._thickness=thickness
        self.update()

    def _depth(self,pts):
        """Camera depth; larger distances are painted first (back to front)."""
        a=math.radians(self._angle)
        return sum(-math.sin(a)*(x-self._width/2)+math.cos(a)*y
                   for x,y,z in pts)/len(pts)

    def _draw_grooved(self,painter,transform):
        """Parametric grooved traditional door preview, in 2D and 3D."""
        w,h,d=self._width,self._height,self._thickness
        front=-d/2;back=d/2
        def rectangle(x0,x1,y,z0,z1):
            return ((x0,y,z0),(x1,y,z0),(x1,y,z1),(x0,y,z1))
        if not self._isometric:
            painter.setBrush(QColor('#e2d5bd'))
            painter.setPen(QPen(INK,1))
            painter.drawPolygon(self._polygon(rectangle(0,w,0,0,h),transform))
            for _,xa,xb,za,zb in groove_spans(self._grooves,w,h):
                painter.setBrush(QColor('#9f8c6f'))
                painter.drawPolygon(self._polygon(rectangle(xa,xb,0,za,zb),transform))
            return
        faces=[]
        def face(pts,color,pen=INK):
            faces.append((self._depth(pts),pts,color,pen))
        for y,color in ((front,QColor('#e2d5bd')),(back,QColor('#c2b294'))):
            face(rectangle(0,w,y,0,h),color)
        for pts,color in (
            (((0,front,0),(w,front,0),(w,back,0),(0,back,0)),QColor('#96876e')),
            (((0,front,h),(w,front,h),(w,back,h),(0,back,h)),QColor('#c4b69e')),
            (((0,front,0),(0,back,0),(0,back,h),(0,front,h)),QColor('#b4a48c')),
            (((w,front,0),(w,back,0),(w,back,h),(w,front,h)),QColor('#b4a48c')),
        ):face(pts,color)
        # Front/rear groove marks follow the actual 3D face on either side.
        for _,xa,xb,za,zb in groove_spans(self._grooves,w,h):
            for y,color in ((front-.0007,QColor('#9e8b6b')),
                            (back+.0007,QColor('#9e8b6b'))):
                face(rectangle(xa,xb,y,za,zb),color,QColor('#86745c'))
        for _,pts,color,pen in sorted(faces,key=lambda item:item[0],reverse=True):
            painter.setPen(QPen(pen,.7))
            painter.setBrush(QBrush(color))
            painter.drawPolygon(self._polygon(pts,transform))

    def set_isometric(self,enabled):
        self._isometric=bool(enabled);self.update()

    def rotate(self,step):
        self._angle=(self._angle+step)%360
        self.update()
        return self._angle

    @property
    def angle(self):return self._angle

    def _project(self,x,y,z,scale,cx,cy):
        if not self._isometric:
            return QPointF(cx+(x-self._width/2)*scale,
                           cy-(z-self._height/2)*scale)
        a=math.radians(self._angle)
        elevation=math.radians(30)
        px=x-self._width/2;pz=z-self._height/2
        u=math.cos(a)*px+math.sin(a)*y
        depth=-math.sin(a)*px+math.cos(a)*y
        return QPointF(cx+scale*u,cy+scale*(math.sin(elevation)*depth
                                             -math.cos(elevation)*pz))

    def _cell_boxes(self):
        """Bounds are calculated by the same layout code as the actual 3D mesh."""
        yield from cell_rectangles(self._grid,self._width,self._height)

    def _polygon(self,points,transform):
        return QPolygonF([transform(*point) for point in points])

    def _box_faces(self,xa,xb,za,zb,depth,transform):
        # Retained compatibility and quick primitive layout tests.
        yf,yb=-depth/2,depth/2
        return (
            ([(xa,yf,za),(xb,yf,za),(xb,yf,zb),(xa,yf,zb)],.99,yf),
            ([(xb,yf,za),(xb,yb,za),(xb,yb,zb),(xb,yf,zb)],.76,xb),
            ([(xa,yb,za),(xa,yf,za),(xa,yf,zb),(xa,yb,zb)],.68,xa),
            ([(xa,yf,zb),(xb,yf,zb),(xb,yb,zb),(xa,yb,zb)],1.19,zb),
            ([(xa,yb,za),(xb,yb,za),(xb,yb,zb),(xa,yb,zb)],.83,yb),
        )

    def _material_recipe(self,part_id,kind):
        return grid_material(self._grid,part_id,kind) if self._grid else None

    def _color(self,part_id,kind):
        color=COLORS.get(kind,QColor('#aab6be'))
        recipe=self._material_recipe(part_id,kind)
        if not isinstance(recipe,dict):return color
        rgb=recipe.get('color')
        if isinstance(rgb,(tuple,list)) and len(rgb)>=3:
            try:
                color=QColor(*(int(max(0,min(255,v))) for v in rgb[:3]))
            except (ValueError,TypeError):pass
        elif recipe.get('mat'):
            # A named material with no RGB still needs an identifiable preview
            # when its texture file is temporarily unavailable.
            digest=hashlib.sha256(str(recipe['mat']).encode('utf-8')).digest()
            color=QColor(85+digest[0]//3,88+digest[1]//3,87+digest[2]//3)
        return color

    def _brush(self,part_id,kind,color=None):
        """Tile the actual native material texture locally; do not access network."""
        color=color or self._color(part_id,kind)
        recipe=self._material_recipe(part_id,kind)
        if isinstance(recipe,dict):
            tex=recipe.get('texture')
            path=tex.get('path') if isinstance(tex,dict) else None
            if isinstance(path,str) and path:
                if path not in self._texture_cache:
                    pix=QPixmap(path)
                    self._texture_cache[path]=(None if pix.isNull() else
                                               QBrush(pix.scaled(96,96)))
                brush=self._texture_cache[path]
                if brush is not None:return brush
        return QBrush(color)

    def _body_path(self,transform,y=0):
        """One hole-bearing QPainterPath: never draw the four virtual slabs."""
        g=self._grid;w=self._width;h=self._height
        if g.get('top_arc_enabled'):
            outer=[(0,0),(w,0)]+[(w*i/40,arc_height(g,w,h,w*i/40))
                                    for i in range(40,-1,-1)]
        else:
            outer=[(0,0),(w,0),(w,h),(0,h)]
        inset=g['insert'];xa=w*inset['x']-inset['width']/2
        za=h*inset['z']-inset['height']/2
        hole=[(xa,za),(xa+inset['width'],za),
              (xa+inset['width'],za+inset['height']),(xa,za+inset['height'])]
        path=QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        for shape in (outer,hole):
            path.addPolygon(self._polygon([(x,y,z) for x,z in shape],transform))
            path.closeSubpath()
        return path,outer,hole

    def _draw_body(self,painter,transform):
        """Render same connected body as host's _continuous_structure mesh."""
        color=self._color('body','leaf_solid')
        if self._isometric:
            front,outer,hole=self._body_path(transform,-self._thickness/2)
            back,*_=self._body_path(transform,self._thickness/2)
            painter.setPen(QPen(_shade(color,.75),.75))
            painter.setBrush(QBrush(_shade(color,.8)))
            if math.cos(math.radians(self._angle))>=0:
                painter.drawPath(back)
            else:
                painter.drawPath(front)
            for perimeter in (outer,hole):
                for i,(x,z) in enumerate(perimeter):
                    nx,nz=perimeter[(i+1)%len(perimeter)]
                    painter.setBrush(QBrush(_shade(color,.84)))
                    painter.drawPolygon(self._polygon(((x,-self._thickness/2,z),
                         (nx,-self._thickness/2,nz),(nx,self._thickness/2,nz),
                         (x,self._thickness/2,z)),transform))
            painter.setPen(QPen(_shade(color,.7),.8))
            painter.setBrush(self._brush('body','leaf_solid',color))
            if math.cos(math.radians(self._angle))>=0:
                painter.drawPath(front)
            else:
                painter.drawPath(back)
        else:
            path,*_=self._body_path(transform)
            painter.setPen(QPen(_shade(color,.7),1.))
            painter.setBrush(self._brush('body','leaf_solid',color))
            painter.drawPath(path)

    def _draw_round_section(self,painter,part_id,profile,kind,color,transform):
        """Show the genuinely round cross-section in isometric preview."""
        member='rail' if kind in ('leaf_rail','leaf_stile') else 'transom'
        resolved=resolved_member(self._grid,part_id)
        cfg=resolved['profile'] if resolved else self._grid.get('member_profiles',{}).get(member,{})
        if cfg.get('shape')!='circle' or not self._isometric:return False
        xs=[x for x,z in profile];zs=[z for x,z in profile]
        xa,xb=min(xs),max(xs);za,zb=min(zs),max(zs)
        resolved=resolved_member(self._grid,part_id)
        radius=(resolved['width'] if resolved else member_widths(self._grid)[member])/2
        if part_id=='rail_top' and self._grid.get('top_arc_enabled'):
            path=[(xa+(xb-xa)*i/32,
                   arc_height(self._grid,self._width,self._height,
                              xa+(xb-xa)*i/32)-radius) for i in range(33)]
        elif kind in ('leaf_stile','leaf_mullion'):
            path=[((xa+xb)/2,za),((xa+xb)/2,zb)]
        else:path=[(xa,(za+zb)/2),(xb,(za+zb)/2)]
        rings=[];n=16
        for i,(x,z) in enumerate(path):
            pre=path[max(0,i-1)];post=path[min(i+1,len(path)-1)]
            dx,dz=post[0]-pre[0],post[1]-pre[1]
            length=max(1e-9,math.hypot(dx,dz));nx,nz=-dz/length,dx/length
            rings.append([transform(x+nx*radius*math.sin(2*math.pi*j/n),
                                    radius*math.cos(2*math.pi*j/n),
                                    z+nz*radius*math.sin(2*math.pi*j/n)) for j in range(n)])
        for i in range(len(rings)-1):
            for j in range(n):
                k=(j+1)%n
                painter.setPen(QPen(color,.12))
                painter.setBrush(_shade(color,.75+.23*math.cos(2*math.pi*j/n)))
                painter.drawPolygon(QPolygonF((rings[i][j],rings[i][k],
                                               rings[i+1][k],rings[i+1][j])))
        return True

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing,True)
        painter.fillRect(self.rect(),QColor('#eaf0f4'))
        painter.setPen(QColor('#34495e'))
        painter.setFont(QFont('Sans Serif',10))
        painter.drawText(16,24,'ISOMETRIC VIEW' if self._isometric else '2D ELEVATION')
        if not self._grid and self._grooves is None:
            painter.end();return
        w,h=self.width(),self.height()
        cx,cy=w/2,h/2+8
        if self._isometric:
            scale=min((w-85)/(self._width*1.3+self._thickness),
                      (h-90)/(self._height*.99+self._thickness))
        else:
            scale=min((w-75)/self._width,(h-85)/self._height)
        scale=max(1.,scale)
        self._layout=(scale,cx,cy)
        transform=lambda x,y,z:self._project(x,y,z,scale,cx,cy)
        self._hits=[]
        if self._grooves is not None:
            self._draw_grooved(painter,transform)
            painter.setFont(QFont('Sans Serif',9))
            painter.setPen(QColor('#34495e'))
            painter.drawText(16,h-16,f'{format_length(self._width)} × {format_length(self._height)} · '
                + (f'{self._angle}° · 45° steps' if self._isometric else 'Groove layout'))
            painter.end()
            return
        shapes=list(leaf_shapes(self._grid,self._width,self._height))
        if self._isometric:
            a=math.radians(self._angle)
            shapes.sort(key=lambda p: -math.sin(a)*sum(x for x,z in p[3])/len(p[3]),reverse=True)
        uniform=(self._grid.get('uniform_external_rails',False) and
                 self._grid.get('uniform_internal_transoms',False))
        material_uniform=self._grid.get('uniform_materials',{}).get('structure',True)
        if self._grid.get('mode')=='inset':
            self._draw_body(painter,transform)
        for part_id,name,kind,profile in shapes:
            if part_id=='body':
                # Keep four disjoint regions only for hit-testing. They are not
                # seams or separate panels in either geometry or preview.
                self._hits.append((part_id,kind,
                         self._polygon([(x,0,z) for x,z in profile],transform)))
                continue
            color=self._color(part_id,kind)
            is_round=(kind in ('leaf_rail','leaf_transom','leaf_stile','leaf_mullion') and
                      self._draw_round_section(painter,part_id,profile,kind,color,transform))
            if self._isometric and not is_round:
                member=resolved_member(self._grid,part_id)
                depth=(self._grid['glass_thickness'] if kind=='leaf_glass' else
                       self._grid['panel_thickness'] if kind in ('leaf_solid','leaf_louver') else
                       member['profile'].get('depth',self._thickness) if member else
                       self._thickness)
                a=-depth/2;b=depth/2
                top=[(x,a,z) for x,z in profile]
                back=[(x,b,z) for x,z in profile]
                # Do not always paint the negative-Y face last: after 180°
                # rotation it is the REAR face and used to hide the front.
                # Depth sorting fixes both reversed facings and overlapping
                # 3D polygon sidewalls while retaining real XZ profiles.
                facets=[(self._depth(top),top,self._brush(part_id,kind,color),color),
                        (self._depth(back),back,QBrush(_shade(color,.78)),INK)]
                for i in range(len(profile)):
                    j=(i+1)%len(profile)
                    pts=(top[i],top[j],back[j],back[i])
                    facets.append((self._depth(pts),pts,
                        QBrush(_shade(color,.76 if i%2 else 1.08)),INK))
                for _dist,pts,brush,edge in sorted(facets,key=lambda q:q[0],reverse=True):
                    painter.setBrush(brush)
                    painter.setPen(QPen(edge,.3 if edge==color else .7))
                    painter.drawPolygon(self._polygon(pts,transform))
            elif not is_round:
                painter.setBrush(self._brush(part_id,kind,color))
                painter.setPen(QPen(color,.1) if (part_id=='body' or (uniform and material_uniform and
                               part_group(kind)=='structure')) else QPen(INK,.85))
                poly=self._polygon([(x,0,z) for x,z in profile],transform)
                painter.drawPolygon(poly)
            if kind=='leaf_louver':
                xs=[x for x,z in profile];zs=[z for x,z in profile]
                self._draw_louvers(painter,min(xs),max(xs),min(zs),max(zs),transform)
            # Selecting the actual members allows independent material overrides.
            poly=self._polygon([(x,0,z) for x,z in profile],transform)
            self._hits.append((part_id,kind,poly))
        # Empty visors have no infill mesh, but must stay clickable.
        if self._grid.get('mode')=='inset' and self._grid['insert']['kind']=='open':
            inset=self._grid['insert'];xa=self._width*inset['x']-inset['width']/2
            za=self._height*inset['z']-inset['height']/2
            f=inset['frame_width'] if inset['frame_enabled'] else 0.
            poly=self._polygon(((xa+f,0,za+f),(xa+inset['width']-f,0,za+f),
                                (xa+inset['width']-f,0,za+inset['height']-f),
                                (xa+f,0,za+inset['height']-f)),transform)
            self._hits.append(('insert','leaf_open',poly))
        # Draw selection and optional empty cell hit regions (grid mode).
        if self._grid.get('mode','grid')=='grid':
            for row,col,xa,xb,za,zb in self._cell_boxes():
                poly=self._polygon(((xa,0,za),(xb,0,za),
                                    (xb,0,zb),(xa,0,zb)),transform)
                if self._grid['cell_types'][row*self._grid['columns']+col]=='open':
                    self._hits.append((f'cell_{row}_{col}','leaf_open',poly))
                if (row,col)==self._selected and self._part_selected is None:
                    painter.setPen(QPen(QColor('#ffad3e'),3))
                    painter.setBrush(QColor(255,173,62,26))
                    painter.drawPolygon(poly)
        if self._part_selected=='body' and self._grid.get('mode')=='inset':
            path,*_=self._body_path(transform)
            painter.setPen(QPen(QColor('#ffad3e'),3))
            painter.setBrush(QBrush(QColor(255,173,62,26)))
            painter.drawPath(path)
        elif self._part_selected:
            for part_id,kind,poly in self._hits:
                if part_id==self._part_selected:
                    painter.setPen(QPen(QColor('#ffad3e'),3))
                    painter.setBrush(QColor(255,173,62,26))
                    painter.drawPolygon(poly)
        painter.setFont(QFont('Sans Serif',9))
        painter.setPen(QColor('#34495e'))
        painter.drawText(16,h-16,f'{format_length(self._width)} × {format_length(self._height)} · '
                         +(f'{self._angle}° · 45° steps' if self._isometric
                           else 'drag the inset to reposition'))
        painter.end()

    def _draw_louvers(self,painter,xa,xb,za,zb,transform):
        n=max(1,int((zb-za)/.065))
        painter.setPen(QPen(QColor('#566b75'),1.8))
        for index in range(n):
            z=za+(index+.5)*(zb-za)/n
            painter.drawLine(transform(xa,.001,z),transform(xb,.001,z))

    def _pick(self,point):
        for part_id,kind,poly in reversed(self._hits):
            if _inside_polygon(point,poly):return part_id,kind
        return None,None

    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton:
            return super().mousePressEvent(event)
        part_id,kind=self._pick(event.position())
        if part_id:
            self._part_selected=part_id
            if part_id.startswith('cell_'):
                try:
                    _,r,c=part_id.split('_');self._selected=(int(r),int(c))
                    self.selected.emit(int(r),int(c))
                except ValueError:pass
            self.elementSelected.emit(part_id,kind)
            self._dragging=(not self._isometric and
                            self._grid.get('mode')=='inset' and part_id=='insert')
            self.update();return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self._dragging and self._layout and not self._isometric:
            scale,cx,cy=self._layout
            x=.5+(event.position().x()-cx)/(scale*self._width)
            z=.5-(event.position().y()-cy)/(scale*self._height)
            self.insetMoved.emit(max(0.,min(1.,x)),max(0.,min(1.,z)))
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        self._dragging=False
        super().mouseReleaseEvent(event)
