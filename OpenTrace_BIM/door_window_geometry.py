# SPDX-License-Identifier: GPL-3.0-or-later
"""Real but unregistered IngeTrazo meshes for basic parametric door/window.

The wall owns the cut. This module builds a *separate* leaf/frame/glass Group
and stores a link to the wall's opening; it does not mutate the host, register
UI, or invoke IFC export. Geometry is local to opening-left, wall midplane,
opening-bottom. A future placement command anchors the parent to the wall.
"""
from __future__ import annotations

import copy
import math

from PySide6.QtGui import QVector3D
from core.group import Group
from core.mesh import Mesh

from .door_window_core import normalize_fill, FillError, f01_unit_size, f01_minimum_unit
from .door_grooves import groove_spans
from . import rust_bridge as _rust_geometry


def _prism(x0, x1, y0, y1, z0, z1, *, pivot=None, angle=0.0):
    """Closed prism, using native Rust vertex construction."""
    if not (x1 > x0 and y1 > y0 and z1 > z0):
        raise FillError("Sólido de esquadria com medidas inválidas.")
    corners = [QVector3D(*pt) for pt in _rust_geometry.prism_vertices(
        x0,x1,y0,y1,z0,z1,pivot=pivot,angle=angle)]
    mesh = Mesh()
    for loop in ((3,2,1,0),(4,5,6,7),(0,1,5,4),
                 (1,2,6,5),(2,3,7,6),(3,0,4,7)):
        mesh.add_face([corners[i] for i in loop])
    return mesh

def _profile_prism(profile, y0, y1, *, pivot=None, angle=0.0):
    """Closed extrusion of an arbitrary simple XZ outline (including arcs).

    Front/back faces use original ear-clipped triangles: no foreign mesh code.
    Curved segments are physically present, not painted over rectangular slabs.
    """
    pts = list(profile)
    # Remove repeated vertices and collinear vertices left by clipping.
    clean=[]
    for point in pts:
        if not clean or abs(point[0]-clean[-1][0])+abs(point[1]-clean[-1][1])>1e-9:
            clean.append(point)
    if len(clean)>2 and clean[0]==clean[-1]: clean.pop()
    pts=clean
    if len(pts)<3 or y1<=y0:
        raise FillError("Perfil extrudado degenerado.")
    area=sum(pts[i][0]*pts[(i+1)%len(pts)][1]
             -pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))/2
    if abs(area)<1e-10: raise FillError("Perfil sem área útil.")
    if area<0: pts.reverse()
    c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    def vertex(x,y,z):
        if pivot is not None:
            xx,yy=x-pivot[0],y-pivot[1]
            x,y=pivot[0]+c*xx-s*yy,pivot[1]+s*xx+c*yy
        return QVector3D(x,y,z)
    def cross(a,b,d):
        return ((b[0]-a[0])*(d[1]-a[1])
                -(b[1]-a[1])*(d[0]-a[0]))
    # Ear clipping is bounded by the 40-point circular header resolution.
    remaining=list(range(len(pts)))
    triangles=[]
    for _ in range(len(pts)*len(pts)):
        if len(remaining)==3:
            triangles.append(tuple(remaining));break
        if len(remaining)<3:break
        found=False
        for idx in range(len(remaining)):
            a,b,d=(remaining[(idx-1)%len(remaining)], remaining[idx],
                    remaining[(idx+1)%len(remaining)])
            if cross(pts[a],pts[b],pts[d])<=1e-10:continue
            def inside(q):
                c1,c2,c3=(cross(pts[a],pts[b],q),cross(pts[b],pts[d],q),
                          cross(pts[d],pts[a],q))
                return min(c1,c2,c3)>=-1e-10
            if any(inside(pts[v]) for v in remaining if v not in (a,b,d)):
                continue
            triangles.append((a,b,d));remaining.pop(idx);found=True;break
        if not found:
            # Degenerate collinear sample from a nearly-flat cap.
            removed=False
            for idx in range(len(remaining)):
                a,b,d=(remaining[(idx-1)%len(remaining)], remaining[idx],
                        remaining[(idx+1)%len(remaining)])
                if abs(cross(pts[a],pts[b],pts[d]))<1e-9:
                    remaining.pop(idx);removed=True;break
            if not removed:
                raise FillError("Não foi possível triangular o perfil da folha.")
    mesh=Mesh()
    # Native faces retain one boundary per side.  Individual ear triangles
    # exposed their diagonals as selectable edges in the host (especially
    # conspicuous on curved headers). The same winding is preserved.
    try:
        mesh.add_face([vertex(*_xz_to_xyz(p,y0)) for p in reversed(pts)])
        mesh.add_face([vertex(*_xz_to_xyz(p,y1)) for p in pts])
    except (ValueError, RuntimeError, TypeError):
        # Older host mesh adapters without concave n-gon support retain the
        # safe triangulation fallback rather than corrupting the solid.
        mesh=Mesh()
        for a,b,d in triangles:
            mesh.add_face([vertex(*_xz_to_xyz(pts[i],y0)) for i in (d,b,a)])
            mesh.add_face([vertex(*_xz_to_xyz(pts[i],y1)) for i in (a,b,d)])
    for i in range(len(pts)):
        a,b=pts[i],pts[(i+1)%len(pts)]
        mesh.add_face([vertex(a[0],y0,a[1]),vertex(b[0],y0,b[1]),
                       vertex(b[0],y1,b[1]),vertex(a[0],y1,a[1])])
    return mesh


def _xz_to_xyz(point,y):
    return point[0],y,point[1]


def _profile_part(name, polygon, y0, y1, **kwargs):
    xs={x for x,z in polygon}; zs={z for x,z in polygon}
    if len(polygon)==4 and len(xs)==2 and len(zs)==2:
        mesh=_prism(min(xs),max(xs),y0,y1,min(zs),max(zs),**kwargs)
    else:
        mesh=_profile_prism(polygon,y0,y1,**kwargs)
    result=Group(mesh,name=name)
    result.component=False
    return result

def _can_join_uniform_frame(grid, shapes, depth):
    """Join only when one continuous finish and physical depth are possible.

    Scoped external/internal links may have different materials or profiles;
    joining those silently discards their face treatments. In that case
    retain separate parametric members rather than fabricate a single solid.
    """
    from .door_leaf_grid import part_group, grid_material, resolved_member
    if (grid.get('mode')!='grid' or not grid.get('stiles_enabled',True)
            or not grid.get('rails_enabled',True)
            or not grid.get('uniform_materials',{}).get('structure',True)):
        return False
    # Historical global switch used a single physical depth regardless of
    # embedded section depths. Preserve legacy .igz geometry without change.
    if grid.get('uniform_structure'):
        return all(grid.get('member_profiles',{}).get(f,{}).get('shape','rect')=='rect'
                   for f in ('rail','transom'))
    if not (grid.get('uniform_external_rails',False) and
            grid.get('uniform_internal_transoms',False)):
        return False
    # Do not silently merge old preset templates that happened to start
    # with linked dimensions but no chosen unified finish.
    materials=grid.get('member_materials',{})
    if (materials.get('rail') is None and materials.get('transom') is None
            and grid.get('kind_materials',{}).get('structure') is None):
        return False
    items=[(pid,kind) for pid,_,kind,_ in shapes if part_group(kind)=='structure']
    if not items:return False
    finish=grid_material(grid,*items[0])
    for part_id,kind in items:
        profile=resolved_member(grid,part_id)
        if (profile is None or profile['profile'].get('shape','rect')!='rect'
                or abs(profile['profile'].get('depth',depth)-depth)>1.e-6):
            return False
        if grid_material(grid,part_id,kind)!=finish:return False
    return True


def _continuous_framed_grid(grid, width, height, depth, *, x_offset=0.,
                            z_offset=0.,center_y=0.,pivot=None,angle=0.):
    """Produce a single curved/straight manifold frame with real panel holes.

    A closed perimeter and rectangular-section members are prerequisites.
    The front/back are two continuous faces with holes, avoiding rail seams.
    """
    if (grid.get("mode")!="grid" or not grid.get("stiles_enabled",True)
            or not grid.get("rails_enabled",True)):
        return None
    from .door_leaf_grid import arc_height, leaf_shapes
    if grid.get("top_arc_enabled"):
        outer=[(0.,0.),(width,0.)]
        outer.extend((width*i/40,arc_height(grid,width,height,width*i/40))
                     for i in range(40,-1,-1))
    else:
        outer=[(0.,0.),(width,0.),(width,height),(0.,height)]
    draft=dict(grid,cell_types=['glass']*(grid['columns']*grid['rows']))
    openings=[list(reversed(poly)) for pid,name,kind,poly in
              leaf_shapes(draft,width,height) if pid.startswith('cell_')]
    if len(openings)!=grid['columns']*grid['rows']:
        return None
    c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    def v(point,y):
        x,z=point[0]+x_offset,point[1]+z_offset
        if pivot is not None:
            dx=x-pivot[0];dy=y-pivot[1]
            x,y=pivot[0]+c*dx-s*dy,pivot[1]+s*dx+c*dy
        return QVector3D(x,y,z)
    y0=center_y-depth/2;y1=center_y+depth/2
    mesh=Mesh()
    mesh.add_face([v(p,y0) for p in reversed(outer)],
                  [[v(p,y0) for p in reversed(h)] for h in openings])
    mesh.add_face([v(p,y1) for p in outer],
                  [[v(p,y1) for p in h] for h in openings])
    for perimeter in [outer]+openings:
        for i,p in enumerate(perimeter):
            q=perimeter[(i+1)%len(perimeter)]
            mesh.add_face([v(p,y0),v(q,y0),v(q,y1),v(p,y1)])
    group=Group(mesh,name="Estrutura uniforme contínua, incluindo arco")
    group.component=False
    return group



def _continuous_inset_body(grid,width,height,depth,*,x_offset=0.,z_offset=0.,
                           center_y=0.,pivot=None,angle=0.):
    """One physical solid surrounding a visor, including an optional top arc.

    Unlike the four virtual preview rectangles, this has a *single* front and
    back face (with one hole), and boundary faces only around the real contours.
    The curved outer edge is polygonally approximated just like all other arcs.
    """
    from .door_leaf_grid import arc_height
    insert=grid['insert'];xa=width*insert['x']-insert['width']/2
    xb=xa+insert['width'];za=height*insert['z']-insert['height']/2
    zb=za+insert['height']
    if grid.get('top_arc_enabled'):
        outer=[(0.,0.),(width,0.)]
        outer.extend((width*i/40,arc_height(grid,width,height,width*i/40))
                     for i in range(40,-1,-1))
    else:
        outer=[(0.,0.),(width,0.),(width,height),(0.,height)]
    hole=[(xa,za),(xa,zb),(xb,zb),(xb,za)]
    c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    def vertex(p,y):
        x,z=p[0]+x_offset,p[1]+z_offset
        if pivot is not None:
            dx=x-pivot[0];dy=y-pivot[1]
            x,y=pivot[0]+c*dx-s*dy,pivot[1]+s*dx+c*dy
        return QVector3D(x,y,z)
    y0=center_y-depth/2;y1=center_y+depth/2
    mesh=Mesh()
    mesh.add_face([vertex(p,y0) for p in reversed(outer)],
                  [[vertex(p,y0) for p in reversed(hole)]])
    mesh.add_face([vertex(p,y1) for p in outer],
                  [[vertex(p,y1) for p in hole]])
    for boundary in (outer,hole):
        for i,p in enumerate(boundary):
            q=boundary[(i+1)%len(boundary)]
            mesh.add_face([vertex(p,y0),vertex(q,y0),vertex(q,y1),vertex(p,y1)])
    obj=Group(mesh,name='Corpo único com visor e contorno em arco')
    obj.component=False
    return obj


def _continuous_structure(profile_parts, depth, *, x_offset=0.,z_offset=0.,
                         center_y=0.,pivot=None,angle=0.,
                         name="Estrutura contínua · sem emendas"):
    """One manifold rectangular network without coplanar butt-joint seams.

    The union outline and any panel holes are extracted from occupied lattice
    cells. Only exterior and opening boundaries become faces. No overlapping
    stiles, no separate touching rail end-caps and no inner seam geometry.
    """
    rects=[]
    for _pid,_name,_kind,polygon in profile_parts:
        xs={x for x,z in polygon};zs={z for x,z in polygon}
        if len(polygon)!=4 or len(xs)!=2 or len(zs)!=2:
            return None
        rects.append((min(xs),max(xs),min(zs),max(zs)))
    if not rects:return None
    xx=sorted({v for a,b,c,d in rects for v in (a,b)})
    zz=sorted({v for a,b,c,d in rects for v in (c,d)})
    occupied=set()
    for i in range(len(xx)-1):
        for j in range(len(zz)-1):
            cx=(xx[i]+xx[i+1])/2;cz=(zz[j]+zz[j+1])/2
            if any(a<cx<b and c<cz<d for a,b,c,d in rects):
                occupied.add((i,j))
    # Directed segments with material (occupied cells) always on the left.
    edges=[]
    for i,j in occupied:
        x0,x1=xx[i:i+2];z0,z1=zz[j:j+2]
        if (i,j-1) not in occupied:edges.append(((x0,z0),(x1,z0)))
        if (i+1,j) not in occupied:edges.append(((x1,z0),(x1,z1)))
        if (i,j+1) not in occupied:edges.append(((x1,z1),(x0,z1)))
        if (i-1,j) not in occupied:edges.append(((x0,z1),(x0,z0)))
    outgoing={}
    for a,b in edges:outgoing.setdefault(a,[]).append(b)
    loops=[]
    while outgoing:
        start=next(iter(outgoing));p=start
        loop=[]
        for _ in range(len(edges)+2):
            loop.append(p)
            options=outgoing.get(p)
            if not options:raise FillError("Contorno unificado descontínuo.")
            dest=options.pop()
            if not options:outgoing.pop(p)
            p=dest
            if p==start:break
        else:raise FillError("Malha unificada não fechou.")
        # Merge collinear boundary steps to avoid visible edge subdivisions.
        trimmed=[]
        for idx,pt in enumerate(loop):
            pre=loop[idx-1];post=loop[(idx+1)%len(loop)]
            if abs((pt[0]-pre[0])*(post[1]-pt[1])-
                   (pt[1]-pre[1])*(post[0]-pt[0]))>1e-10:
                trimmed.append(pt)
        if len(trimmed)>=3:loops.append(trimmed)
    def area(poly):
        return sum(poly[i][0]*poly[(i+1)%len(poly)][1]-
                   poly[(i+1)%len(poly)][0]*poly[i][1]
                   for i in range(len(poly)))/2
    outer=[loop for loop in loops if area(loop)>0]
    holes=[loop for loop in loops if area(loop)<0]
    from .complex_profile import point_in_polygon
    mesh=Mesh()
    c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    def vertex(pt,y):
        x,z=pt
        x+=x_offset;z+=z_offset
        if pivot is not None:
            dx=x-pivot[0];dy=y-pivot[1]
            x,y=pivot[0]+c*dx-s*dy,pivot[1]+s*dx+c*dy
        return QVector3D(x,y,z)
    y0=center_y-depth/2;y1=center_y+depth/2
    for ext in outer:
        inners=[loop for loop in holes if point_in_polygon(loop[0],ext)]
        front=[vertex(pt,y0) for pt in reversed(ext)]
        back=[vertex(pt,y1) for pt in ext]
        if inners:
            mesh.add_face(front,[[vertex(p,y0) for p in reversed(loop)] for loop in inners])
            mesh.add_face(back,[[vertex(p,y1) for p in loop] for loop in inners])
        else:
            mesh.add_face(front);mesh.add_face(back)
    for outline in loops:
        for i,p in enumerate(outline):
            q=outline[(i+1)%len(outline)]
            mesh.add_face([vertex(p,y0),vertex(q,y0),vertex(q,y1),vertex(p,y1)])
    group=Group(mesh,name=name)
    group.component=False
    return group


def _section_mesh(path, loops, width, depth):
    """Sweep editable circular or embedded complex sections along a member.

    Path is a 3D polyline of (x,y,z), with horizontal/curved members in XZ.
    Front/back caps, hole loops and side faces share the saved profile outline.
    """
    if len(path)<2 or not loops:
        raise FillError("Perfil sem trajetória ou seção.")
    points=[p for loop in loops for p in loop["points"]]
    umin=min(p[0] for p in points);umax=max(p[0] for p in points)
    vmin=min(p[1] for p in points);vmax=max(p[1] for p in points)
    if umax-umin<1e-9 or vmax-vmin<1e-9:
        raise FillError("Perfil complexo degenerado.")
    mesh=Mesh()
    rings=[]
    for i,(x,y,z) in enumerate(path):
        before=path[max(0,i-1)];after=path[min(len(path)-1,i+1)]
        dx=after[0]-before[0];dz=after[2]-before[2]
        length=math.hypot(dx,dz)
        if length<1e-9:raise FillError("Trajetória de travessa degenerada.")
        tx=dx/length;tz=dz/length
        # For vertical member, the secondary axis points horizontally across X.
        # Horizontal member: transverse axis is normal to its XZ path.
        ring=[]
        for loop in loops:
            verts=[]
            for u,v in loop["points"]:
                yy=(u-(umin+umax)/2)/(umax-umin)*depth
                cross=(v-(vmin+vmax)/2)/(vmax-vmin)*width
                verts.append(QVector3D(x-tz*cross,y+yy,z+tx*cross))
            ring.append(verts)
        rings.append(ring)
    outers=[i for i,l in enumerate(loops) if not l.get("hole")]
    holes=[i for i,l in enumerate(loops) if l.get("hole")]
    if not outers:raise FillError("Perfil sem perímetro externo.")
    # Closed sweep: holes are passed natively as inner loops to Mesh.add_face.
    for o in outers:
        hole_ids=[]
        if holes:
            from .complex_profile import point_in_polygon
            for idx in holes:
                if point_in_polygon(loops[idx]["points"][0],loops[o]["points"]):
                    hole_ids.append(idx)
        front=list(reversed(rings[0][o]))
        back=rings[-1][o]
        if hole_ids:
            mesh.add_face(front,[list(reversed(rings[0][i])) for i in hole_ids])
            mesh.add_face(back,[rings[-1][i] for i in hole_ids])
        else:
            mesh.add_face(front);mesh.add_face(back)
    for a,b in zip(rings,rings[1:]):
        for li,loop in enumerate(loops):
            for j in range(len(a[li])):
                k=(j+1)%len(a[li])
                mesh.add_face([a[li][j],a[li][k],b[li][k],b[li][j]])
    return mesh


def _section_member(name, polygon, y0, y1, config, target_width, *,
                    arc_path=None, vertical=False, pivot=None, angle=0.0):
    """Generate a real section sweep for round or complex structural bars."""
    shape=config.get("shape","rect")
    if shape=="rect":
        depth=config.get("depth",y1-y0)
        return _profile_part(name,polygon,(y0+y1-depth)/2,
                             (y0+y1+depth)/2,pivot=pivot,angle=angle)
    from .complex_profile import profile_loops
    if shape=="circle":
        n=24
        loops=[{"points":[(math.cos(2*math.pi*i/n),math.sin(2*math.pi*i/n))
                           for i in range(n)],"hole":False}]
        # The same effective width is also used for the circular section,
        # including when the uniform-structure switch is enabled.
        depth=target_width
    elif shape=="complex":
        loops=profile_loops(config["profile_data"])
        depth=config.get("depth",y1-y0)
    else:
        raise FillError("Seção de travessa desconhecida.")
    xs=[p[0] for p in polygon];zs=[p[1] for p in polygon]
    xa,xb=min(xs),max(xs);za,zb=min(zs),max(zs)
    y=(y0+y1)/2
    if arc_path is not None:
        path=[(x,y,z) for x,z in arc_path]
    elif vertical:
        path=[((xa+xb)/2,y,za),((xa+xb)/2,y,zb)]
    else:
        path=[(xa,y,(za+zb)/2),(xb,y,(za+zb)/2)]
    if pivot is not None:
        c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
        out=[]
        for x,yy,z in path:
            xx=x-pivot[0];dy=yy-pivot[1]
            out.append((pivot[0]+c*xx-s*dy,pivot[1]+s*xx+c*dy,z))
        path=out
    mesh=_section_mesh(path,loops,target_width,depth)
    obj=Group(mesh,name=name)
    obj.component=False
    return obj


def _part(name, *size, **kwargs):
    part = Group(_prism(*size, **kwargs), name=name)
    part.component = False
    return part


def _arched_band(x0, x1, z_crown, rise, thickness, y0, y1,
                 name, *, outside=False):
    """True circular top crosspiece following the arch, not a flat lintel."""
    from .door_leaf_grid import arc_height
    # The same 40 stations as the leaf arc, with exact end and crown values.
    # Both sides use the same samples, avoiding tapered triangular slivers.
    samples = 40
    grid = {"top_arc_enabled": True, "top_arc_rise": rise}
    high = [(x0 + (x1-x0)*i/samples,
             arc_height(grid,x1-x0,z_crown,(x1-x0)*i/samples))
            for i in range(samples+1)]
    high[0] = (x0, z_crown-rise)
    high[-1] = (x1, z_crown-rise)
    low = [(x, z-thickness) for x,z in reversed(high)]
    return _profile_part(name,high+low,y0,y1)


def _arched_u_member(x0, x1, bottom, crown, rise, width, y0, y1, name):
    """One watertight U-shaped arch section: two jambs + curved head.

    This replaces three overlapping solids. Front/back each consist of a
    single planar contour, so diagonal ear-clipping seams aren't exposed as
    edges. The lower ends remain open as in a door jamb (no threshold).
    """
    from .door_leaf_grid import arc_height
    if (width <= 0 or x1-x0 <= 2*width or
            crown-rise-width <= bottom):
        raise FillError("Arco sem espaço suficiente para o marco e as ombreiras.")
    steps=40
    def arch(a,b,top):
        grid={"top_arc_enabled":True,"top_arc_rise":rise}
        points=[(a+(b-a)*i/steps,
                 arc_height(grid,b-a,top,(b-a)*i/steps))
                for i in range(steps+1)]
        points[0]=(a,top-rise)
        points[-1]=(b,top-rise)
        return points
    outside=arch(x0,x1,crown)
    inside=arch(x0+width,x1-width,crown-width)
    polygon=[(x0,bottom)]+outside+[(x1,bottom),
         (x1-width,bottom)]+list(reversed(inside))+[(x0+width,bottom)]
    return _profile_part(name,polygon,y0,y1)


def _physical_f01_parts(spec, wall_thickness, wall_faces):
    """Physical F01: independent leaf, side jambs, operating/installation gaps.

    X runs across the rough cut, Y spans finished wall faces, Z is above
    the lower rough opening. The host's source station never changes here.
    """
    unit_width, unit_height = f01_unit_size(spec)
    minimum_width, _minimum_height = f01_minimum_unit(spec)
    frame = spec["frame_thickness"]
    x0 = spec["clearance_left"]
    x1 = x0 + unit_width
    z0 = spec["clearance_bottom"]
    z1 = z0 + unit_height
    trim_width = spec["trim_width"]
    trim_depth = spec["trim_thickness"]
    depth = (wall_thickness if spec["frame_depth_mode"] == "auto"
             else spec["frame_depth"])
    if depth <= 0:
        raise FillError("Profundidade do batente inválida.")
    lower_face, upper_face = wall_faces
    recess = spec["frame_recess"]
    if spec["host_face"] == "left":
        y0 = lower_face + recess
        y1 = y0 + depth
    else:
        y1 = upper_face - recess
        y0 = y1 - depth
    center_y = (y0 + y1) / 2
    leaf_thickness = spec["leaf_thickness"]
    # A manually shallow frame cannot enclose the specified physical leaf.
    if leaf_thickness >= depth:
        raise FillError("O batente deve ser mais profundo que a folha.")
    extra = (unit_width - minimum_width) / 2
    leaf_left = x0 + frame + spec["operating_gap_left"] + extra
    leaf_right = leaf_left + spec["width"]
    leaf_top = z0 + spec["height"]
    hinge = leaf_left if spec["hinge"] == "left" else leaf_right
    direction = 1 if spec["hinge"] == "left" else -1
    sliding = spec.get("family_key") in ("sliding_surface", "sliding_pocket")
    angle = 0.0 if sliding else direction * spec["swing"] * spec["model_angle"]
    pivot = None if sliding else (hinge, center_y)
    result = []

    def add(name, component, *bounds, polygon=None, part_id=None,
            override_material=None, **kwargs):
        if polygon is None:
            part = _part(name, *bounds, **kwargs)
        else:
            part = _profile_part(name, polygon, bounds[0], bounds[1], **kwargs)
        part.ext = {"opentrace_component": component}
        if part_id:
            part.ext["opentrace_part_id"] = part_id
        material = override_material or spec.get("material_" + component)
        if material is None and component in (
                "leaf_stile", "leaf_rail", "leaf_mullion",
                "leaf_transom", "leaf_solid", "leaf_louver"):
            material = spec.get("material_leaf_edge")
        if material is None and component == "leaf_glass":
            material = {"color": (175.0, 210.0, 230.0), "opacity": 0.35}
        if material is not None:
            part.material = copy.deepcopy(material)
        result.append(part)
        return part

    grid = spec.get("leaf_grid") or {}
    arch = (spec.get("leaf_variant") == "grid"
            and bool(grid.get("top_arc_enabled")))
    rise = float(grid.get("top_arc_rise", 0.0)) if arch else 0.0
    if arch:
        # Continuous arched jamb/rail eliminates the side gaps and artificial
        # butt edges from three independent, partly overlapping solids.
        frame_part=_arched_u_member(x0,x1,z0,z1,rise,frame,y0,y1,
                                    "Marco contínuo em arco")
        frame_part.ext={"opentrace_component":"frame"}
        if spec.get("material_frame") is not None:
            frame_part.material=copy.deepcopy(spec["material_frame"])
        result.append(frame_part)
    else:
        add("Marco esquerdo", "frame", x0, x0+frame, y0, y1, z0, z1)
        add("Marco direito", "frame", x1-frame, x1, y0, y1, z0, z1)
        add("Verga do marco", "frame", x0+frame, x1-frame,
            y0, y1, z1-frame, z1)

    # Unlike a cosmetic overlay, a glazed design does NOT contain an opaque
    # full-size slab behind its panes. Every member follows the 3D swing.
    if spec["leaf_variant"] == "grid":
        from .door_leaf_grid import leaf_shapes, grid_material
        grid = spec["leaf_grid"]
        shapes=list(leaf_shapes(grid,spec["width"],spec["height"]))
        supports_join=_can_join_uniform_frame(grid,shapes,leaf_thickness)
        body=None
        if grid.get("mode")=="inset":
            if grid.get("top_arc_enabled"):
                body=_continuous_inset_body(grid,spec["width"],spec["height"],
                         leaf_thickness,x_offset=leaf_left,z_offset=z0,
                         center_y=center_y,pivot=pivot,angle=angle)
            else:
                body=_continuous_structure([part for part in shapes if part[0]=="body"],
                         leaf_thickness,x_offset=leaf_left,z_offset=z0,
                         center_y=center_y,pivot=pivot,angle=angle,
                         name="Folha lisa contínua com recorte")
            if body is None:
                raise FillError("Não foi possível gerar recorte do visor na folha.")
            body.ext={"opentrace_component":"leaf_solid","opentrace_part_id":"body"}
            body.material=copy.deepcopy(grid_material(grid,"body","leaf_solid")
                               or spec.get("material_leaf_solid")
                               or spec.get("material_leaf_edge"))
            result.append(body)
        joined=None
        if supports_join:
            from .door_leaf_grid import part_group
            structural=[piece for piece in shapes if part_group(piece[2])=="structure"]
            joined=_continuous_framed_grid(grid,spec["width"],spec["height"],
                        leaf_thickness,x_offset=leaf_left,z_offset=z0,
                        center_y=center_y,pivot=pivot,angle=angle)
            if joined is None:
                joined=_continuous_structure(structural,leaf_thickness,
                             x_offset=leaf_left,z_offset=z0,
                             center_y=center_y,pivot=pivot,angle=angle)
            if joined is not None:
                joined.ext={"opentrace_component":"leaf_structure"}
                joined.material=copy.deepcopy(grid_material(grid,"rail_top","leaf_rail")
                                     or spec.get("material_leaf_stile")
                                     or spec.get("material_leaf_edge"))
                result.append(joined)
        for part_id, name, component, polygon in shapes:
            if part_id=="body" and body is not None:
                continue
            if joined is not None and part_group(component)=="structure":
                continue
            xs=[v[0] for v in polygon];zs=[v[1] for v in polygon]
            xa,xb,za,zb=min(xs),max(xs),min(zs),max(zs)
            recipe=grid_material(grid,part_id,component)
            if component == "leaf_louver":
                n = max(1, int((zb-za)/.065))
                bar = min(.022, (zb-za)/(n*2))
                for i in range(n):
                    zbar=za+(i+.5)*(zb-za)/n
                    add(name+" régua "+str(i+1),component,
                        leaf_left+xa,leaf_left+xb,
                        center_y-grid["panel_thickness"]/2,
                        center_y+grid["panel_thickness"]/2,
                        z0+zbar-bar/2,z0+zbar+bar/2,
                        part_id=part_id,override_material=recipe,
                        pivot=pivot,angle=angle)
                continue
            dep=(grid["glass_thickness"] if component == "leaf_glass" else
                 (leaf_thickness if grid["columns"]==grid["rows"]==1 and
                  not grid.get("stiles_enabled",True) and
                  not grid.get("rails_enabled",True) else
                  grid["panel_thickness"]) if component == "leaf_solid" else
                 grid["panel_thickness"] if component == "leaf_louver" else leaf_thickness)
            shifted=tuple((leaf_left+x,z0+z) for x,z in polygon)
            section_key=({"leaf_rail":"rail","leaf_transom":"transom",
                          "leaf_stile":"rail","leaf_mullion":"transom"}
                         .get(component))
            from .door_leaf_grid import resolved_member
            member=resolved_member(grid,part_id) if section_key else None
            section=member["profile"] if member else {}
            if section_key and section.get("shape","rect")!="rect":
                from .door_leaf_grid import member_widths, arc_height
                target=member["width"]
                path=None
                if part_id=="rail_top" and grid.get("top_arc_enabled"):
                    extent=spec["width"]
                    left=resolved_member(grid,"stile_left")["width"]
                    right=resolved_member(grid,"stile_right")["width"]
                    rise=member["width"]/2
                    path=[(leaf_left+left+(extent-left-right)*i/40,
                           z0+arc_height(grid,extent,spec["height"],
                           left+(extent-left-right)*i/40)-rise)
                          for i in range(41)]
                part=_section_member(name,shifted,center_y-dep/2,center_y+dep/2,
                                     section,target,arc_path=path,vertical=component in ("leaf_stile","leaf_mullion"),
                                     pivot=pivot,angle=angle)
                part.ext={"opentrace_component":component,"opentrace_part_id":part_id}
                part.material=copy.deepcopy(recipe or spec.get("material_"+component)
                                       or spec.get("material_leaf_edge"))
                result.append(part)
            else:
                if section_key and section.get("shape")=="rect":
                    dep=section.get("depth",dep)
                add(name,component,center_y-dep/2,center_y+dep/2,
                    polygon=shifted,part_id=part_id,override_material=recipe,
                    pivot=pivot,angle=angle)
    else:
        # Physical leaf is always EXACTLY width x height in both its 3D geometry
        # and data contract; thin independently painted front/back skins cover it.
        add("Folha de abrir", "leaf_edge", leaf_left, leaf_right,
            center_y-leaf_thickness/2, center_y+leaf_thickness/2,
            z0, leaf_top, pivot=pivot, angle=angle)
        skin = min(0.0006, leaf_thickness/8)
        for side, component, ya, yb in (
            ("A", "leaf_front", center_y-leaf_thickness/2-skin,
             center_y-leaf_thickness/2),
            ("B", "leaf_back", center_y+leaf_thickness/2,
             center_y+leaf_thickness/2+skin),
        ):
            add("Face " + side + " da folha", component,
                leaf_left, leaf_right, ya, yb, z0, leaf_top,
                pivot=pivot, angle=angle)
            if spec["leaf_variant"] == "grooved":
                # Each groove is parametric and has its own distinct 3D element.
                # Keep the original shallow face relief so existing project files
                # retain the exact same appearance with default parameters.
                for i, xa, xb, za, zb in groove_spans(spec, spec["width"], spec["height"]):
                    add("Friso " + side + " " + str(i), component,
                        leaf_left+xa, leaf_left+xb,
                        ya-skin if side == "A" else yb,
                        ya if side == "A" else yb+skin,
                        z0+za, z0+zb, pivot=pivot, angle=angle)
            elif spec["leaf_variant"] == "panelled":
                # Two inset-looking applied raised rectangular panels, not cuts.
                border = min(0.09, spec["width"]/6, spec["height"]/8)
                for i in range(2):
                    low = z0 + border + (spec["height"]-3*border)*i/2
                    high = low+(spec["height"]-3*border)/2
                    add("Almofada " + side + " " + str(i+1), component,
                        leaf_left+border, leaf_right-border,
                        ya-skin if side == "A" else yb,
                        ya if side == "A" else yb+skin,
                        low, high, pivot=pivot, angle=angle)
    
    
    # Alizares cover both finished faces; disabling one never affects the other.
    for side, enabled, face, material in (
        ("A", spec["trim_front_enabled"], lower_face, "trim_front"),
        ("B", spec["trim_back_enabled"], upper_face, "trim_back"),
    ):
        if not enabled:
            continue
        ya, yb = ((face-trim_depth, face) if side == "A"
                  else (face, face+trim_depth))
        if arch:
            part=_arched_u_member(x0-trim_width,x1+trim_width,z0,
                                 z1+trim_width,rise,trim_width,ya,yb,
                                 "Alizar " + side + " contínuo em arco")
            part.ext={"opentrace_component":material}
            recipe=spec.get("material_"+material)
            if recipe is not None:part.material=copy.deepcopy(recipe)
            result.append(part)
        else:
            add("Alizar " + side + " esquerdo", material,
                x0-trim_width, x0, ya, yb, z0, z1+trim_width)
            add("Alizar " + side + " direito", material,
                x1, x1+trim_width, ya, yb, z0, z1+trim_width)
            add("Alizar " + side + " superior", material,
                x0, x1, ya, yb, z1, z1+trim_width)
    if sliding:
        # The moving leaves translate as one parametric sash; frame and trims
        # stay in place. This is a static display of the open percentage.
        travel = (spec["width"] + spec["slide_overlap"]) * spec["slide_open_fraction"]
        dx = travel * (-1 if spec["slide_side"] == "left" else 1)
        if spec["family_key"] == "sliding_surface":
            # Surface installation: sash is shown just outside the finished
            # face; never intersect the wall with the closed leaf.
            desired_y = (lower_face - leaf_thickness/2 - .012 if
                         spec["host_face"] == "left" else
                         upper_face + leaf_thickness/2 + .012)
            dy = desired_y - center_y
        else:
            # Pocket is visually recessed at the middle of the wall. The
            # separate wall pocket void is NOT generated in this phase.
            dy = 0.0
        # Apply travel to the actual local mesh. Child Group.xform may be a
        # copy-returning Qt property; our host signatures, selection and export
        # inspect Mesh.vertices rather than child transforms.
        for part in result:
            component = part.ext.get("opentrace_component", "")
            if component.startswith("leaf"):
                for vertex in part.mesh.vertices:
                    old = vertex.position
                    vertex.position = QVector3D(old.x()+dx, old.y()+dy, old.z())
        # Real separate guide/rail pieces in the generated geometry.
        guide_y = center_y + dy
        track_x0 = leaf_left - (spec["width"] if spec["slide_side"] == "left" else 0)
        track_x1 = leaf_right + (spec["width"] if spec["slide_side"] == "right" else 0)
        rail = add("Trilho superior de correr", "hardware",
                   track_x0, track_x1, guide_y-.009, guide_y+.009,
                   z0+spec["height"]+.006, z0+spec["height"]+.021)
        rail.ext["opentrace_sliding_family"] = spec["family_key"]
        if (spec["family_key"] == "sliding_pocket" and
                spec.get("pocket_layout", "legacy") == "sleeve"):
            # The wall was cut for the full sleeve by opening_request().
            # Reconstruct two *closed*, individually selectable wall skins
            # around a free-running central cavity, with end/top/bottom caps.
            from .door_window_core import pocket_extent, wallhole_size
            passage_width, passage_height = wallhole_size(spec)
            sleeve = pocket_extent(spec)
            sleeve_lo = -sleeve if spec["slide_side"] == "left" else passage_width
            sleeve_hi = 0.0 if spec["slide_side"] == "left" else passage_width+sleeve
            # Coordinates are relative to rough-opening bottom, not the leaf:
            # skins must fill exactly the same vertical sleeve the wall removes.
            sleeve_low = 0.0
            sleeve_high = passage_height
            cavity_depth = leaf_thickness + .024
            cavity_low = center_y-cavity_depth/2
            cavity_high = center_y+cavity_depth/2
            skin_a = cavity_low-lower_face
            skin_b = upper_face-cavity_high
            if min(skin_a, skin_b) < .012:
                raise FillError("Porta embutida exige parede com espessura suficiente para duas faces e a folha.")
            pocket_material = spec.get("material_pocket_skin")
            # Generated fill-owned wall closures survive undo/redo with door.
            for label, ya, yb in (
                ("A",lower_face,cavity_low),
                ("B",cavity_high,upper_face)):
                skin = add("Fechamento do bolso " + label, "pocket_skin",
                           sleeve_lo,sleeve_hi,ya,yb,sleeve_low,sleeve_high,
                           override_material=pocket_material)
                skin.ext["opentrace_pocket_part"] = True
            # Sleeve termination and header/floor closures meet the skins,
            # but never occupy the travel cavity inside the pocket.
            cap_thick = min(.016,sleeve/10)
            cap_x0,cap_x1=(sleeve_lo,sleeve_lo+cap_thick) if spec["slide_side"] == "left" else (sleeve_hi-cap_thick,sleeve_hi)
            for name, xaa, xbb, zaa, zbb in (
                ("Tampa de fundo do bolso",cap_x0,cap_x1,sleeve_low,sleeve_high),
                ("Fechamento superior do bolso",sleeve_lo,sleeve_hi,sleeve_high-.018,sleeve_high),
                ("Fechamento inferior do bolso",sleeve_lo,sleeve_hi,sleeve_low,sleeve_low+.012)):
                closure=add(name,"pocket_skin",xaa,xbb,
                            cavity_low,cavity_high,zaa,zbb,
                            override_material=pocket_material)
                closure.ext["opentrace_pocket_part"] = True
        elif spec["family_key"] == "sliding_pocket":
            # Read-only backward compatibility for V7 pockets: no new cut.
            casing_x = leaf_left - .025 if spec["slide_side"] == "left" else leaf_right + .025
            marker = add("Linha de alojamento (sem recorte na parede)", "hardware",
                         casing_x-.006, casing_x+.006, guide_y-.008,
                         guide_y+.008, z0, z0+spec["height"])
            marker.ext["opentrace_pocket_not_cut"] = True
    return result


def build_fill_parts(raw, *, wall_thickness=0.10, wall_faces=None):
    """Build one opening-filling object as named parametric geometric parts.

    A door has three frame parts plus one swinging leaf. A window has a
    four-sided frame, optional mullions, and glass units. All geometry is
    real manifold host Mesh data; the fill remains separate from its wall.
    """
    spec = normalize_fill(raw)
    thickness = float(wall_thickness)
    if not math.isfinite(thickness) or thickness <= 0.002:
        raise FillError("Espessura da parede inválida.")
    if wall_faces is None:
        wall_faces = (-thickness/2, thickness/2)
    if spec["kind"] == "door" and spec.get("f01_layout") == "physical":
        return _physical_f01_parts(spec, thickness, wall_faces)
    f = spec["frame_thickness"]
    if spec["kind"] == "door":
        x0 = spec["clearance_left"]
        z0 = spec["clearance_bottom"]
        w = spec.get("unit_width", spec["width"])
        h = spec.get("unit_height", spec["height"])
    else:
        x0 = z0 = 0.0
        w, h = spec["width"], spec["height"]
    x1, z1 = x0 + w, z0 + h
    if f >= min(w, h) / 2:
        raise FillError("Marco muito grande para o vão.")
    depth = max(thickness, f)
    y0, y1 = -depth / 2, depth / 2
    parts = [
        _part("Marco esquerdo", x0, x0 + f, y0, y1, z0, z1),
        _part("Marco direito", x1 - f, x1, y0, y1, z0, z1),
        _part("Verga do marco", x0 + f, x1 - f, y0, y1, z1 - f, z1),
    ]
    if spec["kind"] == "door":
        leaf = spec["leaf_thickness"]
        if leaf >= thickness:
            raise FillError("A folha deve ser menos espessa que a parede.")
        hinge = x0 + f if spec["hinge"] == "left" else x1 - f
        sign = 1 if spec["hinge"] == "left" else -1
        rotation = sign * spec["swing"] * spec["model_angle"]
        parts.append(_part(
            "Folha de abrir", x0 + f, x1 - f, -leaf / 2, leaf / 2,
            z0, z1 - f, pivot=(hinge, 0.0), angle=rotation,
        ))
    else:
        parts.append(_part("Marco inferior", f, w-f, y0, y1, 0, f))
        # Optional graphical sash composition. Separate physical prisms, from
        # the same canonical grid layout as door leaves; legacy panes untouched.
        if spec.get("window_grid_enabled"):
            from .door_leaf_grid import leaf_shapes, grid_material
            grid = spec["window_grid"]
            shapes=list(leaf_shapes(grid,w-2*f,h-2*f))
            supports_join=_can_join_uniform_frame(grid,shapes,depth)
            body=None
            if grid.get("mode")=="inset":
                if grid.get("top_arc_enabled"):
                    body=_continuous_inset_body(grid,w-2*f,h-2*f,f,
                                               x_offset=f,z_offset=f,center_y=0)
                else:
                    body=_continuous_structure([part for part in shapes if part[0]=="body"],
                                 f,x_offset=f,z_offset=f,center_y=0,
                                 name="Caixilho liso contínuo com recorte")
                if body is None:
                    raise FillError("Não foi possível gerar recorte do visor no caixilho.")
                body.ext={"opentrace_component":"window_solid","opentrace_part_id":"body"}
                body.material=copy.deepcopy(grid_material(grid,"body","leaf_solid")
                                   or spec.get("material_window_frame"))
                parts.append(body)
            joined=None
            if supports_join:
                from .door_leaf_grid import part_group
                structural=[piece for piece in shapes if part_group(piece[2])=="structure"]
                joined=_continuous_framed_grid(grid,w-2*f,h-2*f,depth,
                             x_offset=f,z_offset=f,center_y=0)
                if joined is None:
                    joined=_continuous_structure(structural,depth,
                             x_offset=f,z_offset=f,center_y=0)
                if joined is not None:
                    joined.ext={"opentrace_component":"window_structure"}
                    joined.material=copy.deepcopy(grid_material(grid,"rail_top","leaf_rail")
                                         or spec.get("material_window_frame"))
                    parts.append(joined)
            for part_id, name, component, polygon in shapes:
                if part_id=="body" and body is not None:
                    continue
                if joined is not None and part_group(component)=="structure":
                    continue
                shifted=tuple((f+x,f+z) for x,z in polygon)
                xs=[v[0] for v in shifted];zs=[v[1] for v in shifted]
                xa,xb,za,zb=min(xs),max(xs),min(zs),max(zs)
                recipe=grid_material(grid,part_id,component)
                if component == "leaf_louver":
                    n=max(1,int((zb-za)/.065))
                    bar=min(.022,(zb-za)/(2*n))
                    for i in range(n):
                        cz=za+(i+.5)*(zb-za)/n
                        part=_part(name+" régua "+str(i+1),xa,xb,
                                   -grid["panel_thickness"]/2,
                                   grid["panel_thickness"]/2,
                                   cz-bar/2,cz+bar/2)
                        part.ext={"opentrace_component":"window_louver",
                                  "opentrace_part_id":part_id}
                        if recipe is not None:part.material=copy.deepcopy(recipe)
                        parts.append(part)
                    continue
                dep=(grid["glass_thickness"] if component=="leaf_glass" else
                     grid["panel_thickness"] if component=="leaf_solid" else depth)
                section_key={"leaf_rail":"rail","leaf_transom":"transom",
                             "leaf_stile":"rail","leaf_mullion":"transom"}.get(component)
                from .door_leaf_grid import resolved_member
                member=resolved_member(grid,part_id) if section_key else None
                section=member["profile"] if member else {}
                if section_key and section.get("shape","rect")!="rect":
                    from .door_leaf_grid import member_widths, arc_height
                    target=member["width"]
                    path=None
                    if part_id=="rail_top" and grid.get("top_arc_enabled"):
                        iw,ih=w-2*f,h-2*f
                        left=resolved_member(grid,"stile_left")["width"]
                        right=resolved_member(grid,"stile_right")["width"]
                        rise=member["width"]/2
                        path=[(f+left+(iw-left-right)*i/40,
                               f+arc_height(grid,iw,ih,left+(iw-left-right)*i/40)-rise)
                              for i in range(41)]
                    part=_section_member(name,shifted,-dep/2,dep/2,section,target,
                                         arc_path=path,
                                         vertical=component in ("leaf_stile","leaf_mullion"))
                else:
                    if section_key and section.get("shape")=="rect":
                        dep=section.get("depth",dep)
                    part=_profile_part(name,shifted,-dep/2,dep/2)
                part.ext={"opentrace_component":(
                    "window_glass" if component=="leaf_glass" else
                    "window_"+component[5:]),"opentrace_part_id":part_id}
                if recipe is not None:part.material=copy.deepcopy(recipe)
                parts.append(part)
        else:
            panels = spec["panes"]
            panel_width = (w-2*f)/panels
            if panel_width <= 2*f:
                raise FillError("Largura insuficiente para a quantidade de folhas.")
            for i in range(1, panels):
                x = f+panel_width*i
                parts.append(_part(f"Montante {i}", x-f/2, x+f/2,
                                   y0, y1, f, h-f))
            glass_thickness = spec.get("glass_thickness", min(.006, thickness/3))
            if glass_thickness >= thickness:
                raise FillError("Vidro é mais espesso que a parede.")
            for i in range(panels):
                a = f+panel_width*i + (f/2 if i else 0)
                b = f+panel_width*(i+1) - (f/2 if i+1 < panels else 0)
                parts.append(_part(f"Vidro {i+1}", a, b,
                                   -glass_thickness/2, glass_thickness/2, f, h-f))
    if spec["kind"] == "window":
        general = None
        if spec.get("material_name"):
            from .materials import material_catalog
            name = spec["material_name"]
            recipe = material_catalog().get(name, {})
            general = {"mat": name}
            general.update({
                key: copy.deepcopy(value) for key, value in recipe.items()
                if key in ("color", "texture", "opacity") and value is not None
            })
        frame_material = spec.get("material_window_frame") or general
        glass_material = spec.get("material_window_glass") or general
        for part in parts:
            component = getattr(part, "ext", {}).get("opentrace_component", "")
            material = (glass_material if (part.name.startswith("Vidro ")
                           or component == "window_glass") else frame_material)
            if component == "window_glass" and material is None:
                material = {"color": (175.0,210.0,230.0), "opacity": 0.35}
            if material is not None and getattr(part,"material",None) is None:
                part.material = copy.deepcopy(material)
    return parts


def make_fill_group(raw, *, wall_thickness=0.10, wall_faces=None):
    """A free, unplaced fill assembly ready for hosted placement.

    No global ID is generated here: the caller chooses persistent identifiers
    before build and stores the same fill ID in the wall opening source_id.
    """
    spec = normalize_fill(raw)
    group = Group(name=spec["name"])
    group.adopt(build_fill_parts(
        spec, wall_thickness=wall_thickness, wall_faces=wall_faces))
    group.component = False
    group.ext = {
        "arquitetura_parametrica": {
            "schema": spec["schema"],
            "kind": spec["kind"],
            "host_id": spec["host_id"],
            "opening_id": spec["opening_id"],
            "source_id": spec["id"],
            "params": copy.deepcopy(spec),
        }
    }
    group.ifc = {"class": "IfcDoor" if spec["kind"] == "door"
                 else "IfcWindow", "name": spec["name"],
                 "overall_width": spec["width"],
                 "overall_height": spec["height"]}
    if spec["kind"] == "door":
        from .door_window_core import wallhole_size
        group.ifc["overall_width"], group.ifc["overall_height"] = wallhole_size(spec)
        group.ifc["predefined_type"] = "DOOR"
    if spec.get("ifc_global_id"):
        group.ifc["global_id"] = spec["ifc_global_id"]
    return group


def place_fill_on_wall(raw, wall_group):
    """Create an uninserted fill object aligned with an existing hosted void.

    Call only after an opening request with the same source_id was committed
    to the wall through EditWall. This does not touch the wall or scene.
    Real hosted walls supply a world-space reference path and local elevation.
    """
    from .door_window_core import (station_span, wallhole_span, wallhole_size,
                                   check_hosted_clearance)
    from .model import (
        WallError, _path_cumulative, _point_on_path_distance, path_world,
        profile_at_fraction, read_wall, wall_offsets,
    )
    from PySide6.QtGui import QMatrix4x4

    spec = normalize_fill(raw)
    if getattr(wall_group, "uid", None) != spec["host_id"]:
        raise FillError("O ID do hospedeiro não corresponde à parede escolhida.")
    try:
        values = read_wall(wall_group)
    except WallError as exc:
        raise FillError(f"Parede de destino inválida: {exc}") from exc
    opening = next((item for item in values["openings"]
                    if item.get("id") == spec["opening_id"]), None)
    if opening is None or opening.get("source_id") != spec["id"]:
        raise FillError("O vão não está associado a esta porta ou janela.")
    # Hosted door arches are genuine curved wall cuts. Compare against the
    # canonical requested outline instead of rejecting all non-rectangles.
    from .door_window_core import center_station, opening_request
    expected = opening_request(spec, opening_guid=opening.get("ifc_global_id"))
    if opening.get("kind") != expected["kind"]:
        raise FillError("Contorno da abertura incompatível com a folha.")
    if expected["kind"] == "polygon":
        actual_pts, target_pts = opening.get("polygon"), expected["polygon"]
        actual_edges, target_edges = opening.get("edges"), expected["edges"]
        if (not isinstance(actual_pts, list) or len(actual_pts) != len(target_pts)
                or any(len(a) != 2 or any(abs(float(x)-float(y)) > 1e-5
                         for x,y in zip(a,b)) for a,b in zip(actual_pts,target_pts))
                or actual_edges != target_edges):
            raise FillError("Abertura em arco não corresponde à porta paramétrica.")
    if spec["kind"] == "door":
        left, right = wallhole_span(spec)
        expected_width, expected_height = wallhole_size(spec)
        # Pocket host void is wider than the passage; both are canonical.
        expected_center=expected['position'] if expected['kind']=='rect' else (left+right)/2
    else:
        left, right = station_span(spec)
        expected_width, expected_height = spec["width"], spec["height"]
        expected_center = center_station(spec)
    if expected["kind"] == "rect" and (
            abs(opening["width"] - expected["width"]) > 1.0e-5
            or abs(opening["height"] - expected_height) > 1.0e-5
            or abs(opening["sill"] - spec["sill"]) > 1.0e-5
            or abs(opening["position"] - expected_center) > 1.0e-5):
        raise FillError("Posição, peitoril e dimensões da esquadria devem acompanhar o vão.")

    points, cumulative = _path_cumulative(path_world(wall_group))
    L = cumulative[-1]
    check_hosted_clearance(spec,L)
    # For curved walls, the origin is the left station and rotation follows
    # the local chord: the leaf itself remains straight and parametrically
    # linked to the host's reference station.
    point = _point_on_path_distance(points, cumulative, left)
    center = _point_on_path_distance(points, cumulative, (left+right)/2)
    end = _point_on_path_distance(points, cumulative, right)
    tangent = end-point
    tangent.setZ(0)
    if tangent.length() < 1.0e-8:
        raise FillError("Trajetória da parede degenerada na região do vão.")
    tangent.normalize()
    normal = QVector3D(-tangent.y(), tangent.x(), 0)
    lo, hi = wall_offsets(values)
    offset = (lo + hi) / 2
    # Use the overall finished faces, including every composite finish layer.
    finished_depth = hi - lo
    b, _t, _xy = profile_at_fraction(values, left/L)
    assembly = make_fill_group(
        spec, wall_thickness=finished_depth,
        wall_faces=(lo-offset, hi-offset))
    matrix = QMatrix4x4()
    matrix.translate(point.x()+normal.x()*offset,
                     point.y()+normal.y()*offset,
                     point.z()+b+spec["sill"])
    matrix.rotate(math.degrees(math.atan2(tangent.y(), tangent.x())),
                  0, 0, 1)
    assembly.xform = matrix
    return assembly
