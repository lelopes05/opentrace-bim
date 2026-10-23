# SPDX-License-Identifier: GPL-3.0-or-later
"""Executable regression comparison with the unchanged OpenTrace 0.44.0 ZIP."""
from __future__ import annotations

import ast
import math
from pathlib import Path
import random
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from OpenTrace_BIM import rust_bridge, wall_polygon, door_grooves


def close(a, b, *, eps=2.0e-6):
    assert math.isclose(a, b, abs_tol=eps, rel_tol=1.0e-7), (a, b)


class Vec:
    def __init__(self, x, y=None, z=0.0):
        if y is None:
            self._v = tuple(x._v if isinstance(x, Vec) else x)
        else:
            self._v = (float(x), float(y), float(z))

    def x(self): return self._v[0]
    def y(self): return self._v[1]
    def z(self): return self._v[2]
    def __add__(self, other): return Vec(*(a+b for a,b in zip(self._v, other._v)))
    def __sub__(self, other): return Vec(*(a-b for a,b in zip(self._v, other._v)))
    def __mul__(self, k): return Vec(*(a*k for a in self._v))
    __rmul__ = __mul__
    def length(self): return math.sqrt(sum(x*x for x in self._v))


def legacy_functions(archive, file_name, names, *, constants=None):
    src = archive.read("OpenTrace_BIM/" + file_name).decode("utf-8")
    tree = ast.parse(src, filename=file_name)
    body = [item for item in tree.body
            if isinstance(item, (ast.FunctionDef, ast.ClassDef)) and item.name in names]
    assert len(body) == len(names), (file_name, names)
    scope = {"math": math, "QVector3D": Vec, **(constants or {})}
    exec(compile(ast.Module(body=body, type_ignores=[]), file_name, "exec"), scope)
    return scope


def compare_points(left, right, eps=2.0e-6):
    assert len(left) == len(right), (len(left), len(right))
    for a, b in zip(left, right):
        close(a[0], b[0], eps=eps)
        close(a[1], b[1], eps=eps)


def main(zip_path):
    rng = random.Random(44044)
    comparisons = 0
    with zipfile.ZipFile(zip_path) as archive:
        # The original pure-Python opening geometry can be executed unchanged.
        original = {}
        exec(compile(archive.read("OpenTrace_BIM/wall_polygon.py").decode("utf-8"),
                     "original/wall_polygon.py", "exec"), original)
        for _ in range(1800):
            a = (rng.uniform(-5, 5), rng.uniform(-3, 3))
            b = (a[0]+rng.uniform(-2, 2), a[1]+rng.uniform(-2, 2))
            c = (rng.uniform(-5, 5), rng.uniform(-3, 3))
            d = (c[0]+rng.uniform(-2, 2), c[1]+rng.uniform(-2, 2))
            assert original["_intersect"](a,b,c,d) == wall_polygon._intersect(a,b,c,d)
            comparisons += 1
        for h in (0.0,1.e-10,0.05,-0.05,0.3,-0.3,1.0,-1.0,3.0,-3.0):
            for _ in range(60):
                a=(rng.uniform(-5,5),rng.uniform(-5,5))
                b=(a[0]+rng.uniform(0.1,8),a[1]+rng.uniform(-1,1))
                compare_points(original["arc_samples"](a,b,h),wall_polygon.arc_samples(a,b,h))
                comparisons += 1
        for _ in range(300):
            x=rng.uniform(0.2,3)
            y=rng.uniform(0.2,3)
            rect=[(0.0,0.0),(x,0.0),(x,y),(0.0,y)]
            length=5.0
            original_poly=original["normalize_polygon"]([(px+0.5,py+0.2) for px,py in rect],length)
            new_poly=wall_polygon.normalize_polygon([(px+0.5,py+0.2) for px,py in rect],length)
            assert original_poly == new_poly
            comparisons += 1

        slab=legacy_functions(archive,"slab_model.py",
            ["_cross","_on_segment","_segments_intersect","polygon_area",
             "_circumcenter2","_wrap_angle","arc_points","_point_in_polygon_xy"],
            constants={"MIN_DIM":0.001,"ARC_EPS":1.e-7,"ARC_MAX_STEP_DEG":7.5,
                       "ARC_MAX_SEGMENT":0.25,"ARC_MAX_SAMPLES":256,
                       "SlabError":ValueError})
        for _ in range(1100):
            a,b,c,d=[Vec(rng.uniform(-5,5),rng.uniform(-5,5)) for i in range(4)]
            expected=slab["_segments_intersect"](a,b,c,d)
            actual=rust_bridge.segments_intersect(
                (a.x(),a.y()),(b.x(),b.y()),(c.x(),c.y()),(d.x(),d.y()))
            assert expected==actual
            comparisons+=1
        for h in (0.0,1.e-8,1.e-5,0.03,-0.03,0.3,-0.3,1.0,-1.0):
            for _ in range(35):
                a=Vec(rng.uniform(-5,5),rng.uniform(-5,5))
                b=Vec(a.x()+rng.uniform(0.1,7),a.y()+rng.uniform(-2,2))
                expected=slab["arc_points"](a,b,h)
                if abs(h)<1e-7:
                    actual=[(a.x(),a.y()),(b.x(),b.y())]
                else:
                    actual=rust_bridge.sample_arc_xy(
                        (a.x(),a.y()),(b.x(),b.y()),h,
                        step_deg=7.5,max_segment=0.25,max_samples=256,min_spans=4)
                compare_points([(p.x(),p.y()) for p in expected],actual)
                comparisons+=1

        profile=legacy_functions(archive,"complex_profile.py",["signed_area","point_in_polygon"],
                                 constants={"_EPS":1e-10})
        for _ in range(1000):
            w=rng.uniform(0.01,10);h=rng.uniform(0.01,10)
            rect=[(0,0),(w,0),(w,h),(0,h)]
            close(profile["signed_area"](rect),rust_bridge.signed_area(rect))
            p=(rng.uniform(-1,w+1),rng.uniform(-1,h+1))
            assert profile["point_in_polygon"](p,rect)==rust_bridge.point_in_polygon(p,rect)
            comparisons+=2

        beam=legacy_functions(archive,"beam_model.py",
            ["_circumcenter2","_vertical_z_values"],constants={"MIN_DIM":0.001,"BeamError":ValueError})
        for _ in range(700):
            length=rng.uniform(0.5,12)
            rise=rng.uniform(-2,2)
            h=rng.choice([-1,1])*rng.uniform(0.001,0.05)
            positions=[length*i/24 for i in range(25)]
            try:
                expected=beam["_vertical_z_values"](positions,length,rise,h)
            except ValueError:
                try:
                    rust_bridge.beam_vertical_z(positions,length,rise,h)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Rust should reject beam self-intersection")
            else:
                actual=rust_bridge.beam_vertical_z(positions,length,rise,h)
                assert len(expected)==len(actual)
                for a,b in zip(expected,actual):close(a,b)
            comparisons+=1

        original_door={}
        exec(compile(archive.read("OpenTrace_BIM/door_grooves.py").decode("utf-8"),
                     "original/door_grooves.py", "exec"),original_door)
        for _ in range(500):
            width=rng.uniform(0.5,3)
            height=rng.uniform(1.5,4)
            count=rng.randint(1,9)
            raw={"groove_count":count,"groove_width":0.003,
                 "groove_end_margin":0.1,"groove_offset":0.0}
            try:
                expected=list(original_door["groove_spans"](raw,width,height))
            except ValueError:
                try:list(door_grooves.groove_spans(raw,width,height))
                except ValueError:pass
                else:raise AssertionError("Groove validation diverged")
            else:
                actual=list(door_grooves.groove_spans(raw,width,height))
                assert len(expected)==len(actual)
                for a,b in zip(expected,actual):
                    assert a[0]==b[0]
                    for x,y in zip(a[1:],b[1:]):close(x,y)
            comparisons+=1

        for _ in range(300):
            x0=rng.uniform(-5,5);x1=x0+rng.uniform(.01,3)
            y0=rng.uniform(-5,5);y1=y0+rng.uniform(.01,1)
            z0=rng.uniform(-1,1);z1=z0+rng.uniform(.1,4)
            pivot=(rng.uniform(-2,2),rng.uniform(-2,2))
            angle=rng.uniform(-180,180)
            c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
            source=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
                    (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
            actual=rust_bridge.prism_vertices(x0,x1,y0,y1,z0,z1,pivot=pivot,angle=angle)
            for (x,y,z),(xx,yy,zz) in zip(source,actual):
                dx,dy=x-pivot[0],y-pivot[1]
                close(xx,pivot[0]+c*dx-s*dy)
                close(yy,pivot[1]+s*dx+c*dy)
                close(zz,z)
            comparisons+=1

    print(f"Original 0.44.0 ↔ Rust geometry comparisons passed: {comparisons}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
