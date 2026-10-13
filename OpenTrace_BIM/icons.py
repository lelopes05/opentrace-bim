# SPDX-License-Identifier: GPL-3.0-or-later
"""Small vector icon family for the Parametric Architecture UI.

The icons are painted at runtime with Qt so the plugin stays self contained and
can carry the same visual language to other hosts later without shipping a pile
of bitmap assets.
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QGuiApplication, QPalette

BLUE = QColor("#42658d")
BLUE_LIGHT = QColor("#a9bfd7")
BLUE_MID = QColor("#7e9fbe")
ORANGE = QColor("#c46b2d")
SAND = QColor("#d8c49e")
GREEN = QColor("#6e9872")
INK = QColor("#34404b")


def _pm(size=32):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    return pm


def _painter(pm):
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    return p


def _pen(color=BLUE, width=2.0):
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _legacy_icon(name: str, size: int = 32) -> QIcon:
    name = str(name or "").lower()
    # Runtime palette makes vector symbols legible on the DARK IngeTrazo
    # theme used by the maintainer; previous blue strokes almost disappeared.
    palette = QGuiApplication.palette()
    dark = palette.color(QPalette.Window).lightness() < 128
    if dark:
        BLUE = QColor("#c7e0f4")
        BLUE_LIGHT = QColor("#648fb0")
        BLUE_MID = QColor("#406d91")
        ORANGE = QColor("#ffac68")
        SAND = QColor("#c2a47d")
        INK = QColor("#d3e1ed")
    else:
        BLUE, BLUE_LIGHT, BLUE_MID, ORANGE, SAND, INK = (
            globals()["BLUE"], globals()["BLUE_LIGHT"],
            globals()["BLUE_MID"], globals()["ORANGE"],
            globals()["SAND"], globals()["INK"])
    pm = _pm(size)
    p = _painter(pm)
    s = float(size) / 32.0
    def q(v): return v * s
    p.setPen(_pen(BLUE, q(2.0)))
    p.setBrush(Qt.NoBrush)

    if name in ("home", "architecture", "plugin"):
        roof = QPolygonF([QPointF(q(5),q(15)), QPointF(q(16),q(6)), QPointF(q(27),q(15))])
        p.drawPolyline(roof)
        p.drawRect(QRectF(q(8),q(14),q(16),q(12)))
        p.setBrush(BLUE_LIGHT); p.drawRect(QRectF(q(13),q(18),q(6),q(8)))
    elif name == "wall":
        p.setBrush(BLUE_LIGHT); p.drawRoundedRect(QRectF(q(4),q(8),q(24),q(16)),q(1.5),q(1.5))
        p.drawLine(QPointF(q(4),q(16)),QPointF(q(28),q(16)))
        p.drawLine(QPointF(q(12),q(8)),QPointF(q(12),q(16)))
        p.drawLine(QPointF(q(20),q(16)),QPointF(q(20),q(24)))
    elif name == "wall_composite":
        for y, col in ((7,BLUE_LIGHT),(13,BLUE_MID),(19,SAND)):
            p.setBrush(col); p.drawRect(QRectF(q(4),q(y),q(24),q(6)))
    elif name == "wall_curve":
        p.setBrush(Qt.NoBrush); p.setPen(_pen(BLUE,q(3)))
        p.drawArc(QRectF(q(5),q(5),q(22),q(22)), 25*16, 130*16)
        p.drawArc(QRectF(q(9),q(9),q(14),q(14)), 25*16, 130*16)
    elif name == "slab":
        p.setBrush(BLUE_LIGHT); p.drawPolygon(QPolygonF([
            QPointF(q(5),q(11)),QPointF(q(22),q(7)),QPointF(q(28),q(12)),QPointF(q(11),q(17))]))
        p.setBrush(BLUE_MID); p.drawPolygon(QPolygonF([
            QPointF(q(5),q(11)),QPointF(q(11),q(17)),QPointF(q(11),q(22)),QPointF(q(5),q(16))]))
        p.drawPolygon(QPolygonF([QPointF(q(11),q(17)),QPointF(q(28),q(12)),QPointF(q(28),q(17)),QPointF(q(11),q(22))]))
    elif name == "slab_composite":
        for y, col in ((8,BLUE_LIGHT),(14,BLUE_MID),(20,SAND)):
            p.setBrush(col); p.drawRect(QRectF(q(5),q(y),q(22),q(5)))
    elif name == "column":
        p.setBrush(BLUE_LIGHT); p.drawRect(QRectF(q(10),q(5),q(11),q(22)))
        p.setBrush(BLUE_MID); p.drawPolygon(QPolygonF([
            QPointF(q(21),q(5)),QPointF(q(26),q(9)),QPointF(q(26),q(27)),QPointF(q(21),q(27))]))
        p.drawLine(QPointF(q(10),q(5)),QPointF(q(15),q(9)))
    elif name == "beam":
        p.setBrush(BLUE_LIGHT); p.drawRect(QRectF(q(4),q(11),q(24),q(10)))
        p.setBrush(BLUE_MID); p.drawRect(QRectF(q(7),q(8),q(18),q(3))); p.drawRect(QRectF(q(7),q(21),q(18),q(3)))
    elif name in ("profile", "profiles"):
        p.setBrush(Qt.NoBrush); p.setPen(_pen(BLUE,q(2.2)))
        pts=[(6,25),(6,7),(20,7),(26,12),(20,17),(13,17),(13,25),(6,25)]
        for a,b in zip(pts,pts[1:]): p.drawLine(QPointF(q(a[0]),q(a[1])),QPointF(q(b[0]),q(b[1])))
        p.setPen(_pen(ORANGE,q(1.8))); p.drawEllipse(QRectF(q(17),q(10),q(4),q(4)))
    elif name in ("library", "presets"):
        p.setBrush(BLUE_LIGHT); p.drawRoundedRect(QRectF(q(6),q(6),q(20),q(20)),q(2),q(2))
        p.setBrush(Qt.NoBrush); p.drawLine(QPointF(q(11),q(11)),QPointF(q(22),q(11)))
        p.drawLine(QPointF(q(11),q(16)),QPointF(q(22),q(16))); p.drawLine(QPointF(q(11),q(21)),QPointF(q(19),q(21)))
        p.setPen(_pen(ORANGE,q(2))); p.drawEllipse(QRectF(q(7),q(9),q(2),q(2))); p.drawEllipse(QRectF(q(7),q(14),q(2),q(2))); p.drawEllipse(QRectF(q(7),q(19),q(2),q(2)))
    elif name == "layers":
        p.setBrush(BLUE_LIGHT); p.drawPolygon(QPolygonF([QPointF(q(5),q(11)),QPointF(q(16),q(5)),QPointF(q(27),q(11)),QPointF(q(16),q(17))]))
        p.setBrush(Qt.NoBrush); p.drawPolyline(QPolygonF([QPointF(q(5),q(16)),QPointF(q(16),q(22)),QPointF(q(27),q(16))]))
        p.drawPolyline(QPolygonF([QPointF(q(5),q(21)),QPointF(q(16),q(27)),QPointF(q(27),q(21))]))
    elif name == "bim":
        p.setBrush(BLUE_LIGHT); p.drawPolygon(QPolygonF([QPointF(q(6),q(10)),QPointF(q(16),q(5)),QPointF(q(26),q(10)),QPointF(q(16),q(15))]))
        p.setBrush(BLUE_MID); p.drawPolygon(QPolygonF([QPointF(q(6),q(10)),QPointF(q(16),q(15)),QPointF(q(16),q(27)),QPointF(q(6),q(22))]))
        p.setBrush(SAND); p.drawPolygon(QPolygonF([QPointF(q(16),q(15)),QPointF(q(26),q(10)),QPointF(q(26),q(22)),QPointF(q(16),q(27))]))
        p.setPen(_pen(ORANGE,q(1.6))); p.setBrush(Qt.NoBrush); p.drawEllipse(QRectF(q(12),q(9),q(8),q(8)))
    elif name == "add_vertex":
        p.drawLine(QPointF(q(7),q(16)),QPointF(q(25),q(16))); p.setPen(_pen(ORANGE,q(2.5)))
        p.drawLine(QPointF(q(16),q(9)),QPointF(q(16),q(23))); p.drawLine(QPointF(q(9),q(16)),QPointF(q(23),q(16)))
    elif name == "move":
        p.setPen(_pen(BLUE,q(2.2))); p.drawLine(QPointF(q(6),q(16)),QPointF(q(26),q(16))); p.drawLine(QPointF(q(6),q(16)),QPointF(q(11),q(11))); p.drawLine(QPointF(q(6),q(16)),QPointF(q(11),q(21))); p.drawLine(QPointF(q(26),q(16)),QPointF(q(21),q(11))); p.drawLine(QPointF(q(26),q(16)),QPointF(q(21),q(21)))
    elif name == "vertical":
        p.drawLine(QPointF(q(16),q(5)),QPointF(q(16),q(27))); p.drawLine(QPointF(q(16),q(5)),QPointF(q(11),q(10))); p.drawLine(QPointF(q(16),q(5)),QPointF(q(21),q(10))); p.drawLine(QPointF(q(16),q(27)),QPointF(q(11),q(22))); p.drawLine(QPointF(q(16),q(27)),QPointF(q(21),q(22)))
    elif name in ("curve", "curve_h"):
        path=QPainterPath(QPointF(q(5),q(22))); path.cubicTo(QPointF(q(9),q(6)),QPointF(q(23),q(6)),QPointF(q(27),q(22))); p.drawPath(path)
        p.setBrush(ORANGE); p.setPen(Qt.NoPen); p.drawEllipse(QRectF(q(14),q(8),q(4),q(4)))
    elif name == "curve_v":
        path=QPainterPath(QPointF(q(5),q(10))); path.cubicTo(QPointF(q(9),q(26)),QPointF(q(23),q(26)),QPointF(q(27),q(10))); p.drawPath(path)
    elif name == "opening":
        p.setBrush(BLUE_LIGHT); p.drawRect(QRectF(q(5),q(7),q(22),q(18))); p.setBrush(Qt.transparent); p.setPen(_pen(ORANGE,q(2.2))); p.drawRect(QRectF(q(11),q(12),q(10),q(13)))
    elif name == "delete":
        p.setPen(_pen(ORANGE,q(2.4))); p.drawLine(QPointF(q(9),q(9)),QPointF(q(23),q(23))); p.drawLine(QPointF(q(23),q(9)),QPointF(q(9),q(23)))
    elif name == "extend":
        p.drawLine(QPointF(q(5),q(16)),QPointF(q(25),q(16))); p.drawLine(QPointF(q(25),q(16)),QPointF(q(19),q(10))); p.drawLine(QPointF(q(25),q(16)),QPointF(q(19),q(22))); p.setPen(_pen(ORANGE,q(2))); p.drawLine(QPointF(q(10),q(9)),QPointF(q(10),q(23)))
    elif name == "height":
        p.drawLine(QPointF(q(8),q(24)),QPointF(q(24),q(24))); p.drawLine(QPointF(q(16),q(24)),QPointF(q(16),q(6))); p.drawLine(QPointF(q(16),q(6)),QPointF(q(11),q(12))); p.drawLine(QPointF(q(16),q(6)),QPointF(q(21),q(12)))
    elif name == "incline":
        p.drawLine(QPointF(q(7),q(25)),QPointF(q(25),q(25))); p.drawLine(QPointF(q(9),q(24)),QPointF(q(23),q(8))); p.setPen(_pen(ORANGE,q(1.6))); p.drawArc(QRectF(q(8),q(15),q(13),q(13)),0,58*16)
    elif name == "offset":
        p.drawRect(QRectF(q(5),q(7),q(16),q(16))); p.setPen(_pen(ORANGE,q(2))); p.drawRect(QRectF(q(11),q(13),q(16),q(14)))
    elif name == "stretch":
        p.drawRect(QRectF(q(6),q(12),q(12),q(10))); p.setPen(_pen(ORANGE,q(2))); p.drawLine(QPointF(q(18),q(17)),QPointF(q(27),q(8))); p.drawLine(QPointF(q(27),q(8)),QPointF(q(21),q(9))); p.drawLine(QPointF(q(27),q(8)),QPointF(q(26),q(14)))
    elif name == "chamfer":
        poly=QPolygonF([QPointF(q(6),q(24)),QPointF(q(6),q(8)),QPointF(q(20),q(8)),QPointF(q(26),q(14)),QPointF(q(26),q(24))]); p.drawPolyline(poly); p.setPen(_pen(ORANGE,q(2))); p.drawLine(QPointF(q(20),q(8)),QPointF(q(26),q(14)))
    elif name == "fillet":
        p.drawLine(QPointF(q(7),q(25)),QPointF(q(7),q(13))); p.drawLine(QPointF(q(19),q(7)),QPointF(q(25),q(7))); p.setPen(_pen(ORANGE,q(2.4))); p.drawArc(QRectF(q(7),q(7),q(24),q(24)),90*16,90*16)
    elif name == "rect":
        p.setBrush(BLUE_LIGHT); p.drawRect(QRectF(q(6),q(8),q(20),q(16)))
    elif name == "polygon":
        p.setBrush(BLUE_LIGHT); p.drawPolygon(QPolygonF([QPointF(q(7),q(21)),QPointF(q(10),q(8)),QPointF(q(22),q(6)),QPointF(q(27),q(17)),QPointF(q(18),q(26))]))
    elif name == "center_arc":
        p.drawEllipse(QRectF(q(14),q(14),q(4),q(4))); p.drawArc(QRectF(q(6),q(6),q(20),q(20)),20*16,120*16)
        p.setPen(_pen(ORANGE,q(1.5))); p.drawLine(QPointF(q(16),q(16)),QPointF(q(24),q(10)))
    elif name == "three_points":
        path=QPainterPath(QPointF(q(5),q(22))); path.quadTo(QPointF(q(16),q(5)),QPointF(q(27),q(22))); p.drawPath(path); p.setBrush(ORANGE);p.setPen(Qt.NoPen)
        for x,y in ((5,22),(16,10),(27,22)):p.drawEllipse(QRectF(q(x-2),q(y-2),q(4),q(4)))
    elif name == "wall_base":
        # Four-wall rectangle specified by a baseline and perpendicular depth.
        p.drawRect(QRectF(q(6),q(8),q(20),q(16)))
        p.setPen(_pen(ORANGE,q(2.2)))
        p.drawLine(QPointF(q(6),q(27)),QPointF(q(26),q(27)))
        p.drawLine(QPointF(q(6),q(24)),QPointF(q(6),q(30)))
        p.drawLine(QPointF(q(26),q(24)),QPointF(q(26),q(30)))
    elif name in ("anchor_left","anchor_center","anchor_right"):
        p.drawLine(QPointF(q(5),q(23)),QPointF(q(27),q(23)))
        p.drawRect(QRectF(q(7),q(8),q(18),q(13)))
        x={"anchor_left":7,"anchor_center":16,"anchor_right":25}[name]
        p.setPen(_pen(ORANGE,q(2.2)))
        p.drawLine(QPointF(q(x),q(5)),QPointF(q(x),q(27)))
    elif name == "swing":
        p.drawLine(QPointF(q(6),q(24)),QPointF(q(6),q(7)))
        p.drawLine(QPointF(q(6),q(24)),QPointF(q(23),q(24)))
        p.setPen(_pen(ORANGE,q(2.2)))
        p.drawArc(QRectF(q(6),q(7),q(18),q(18)),0,90*16)
        p.drawLine(QPointF(q(24),q(16)),QPointF(q(22),q(10)))
        p.drawLine(QPointF(q(24),q(16)),QPointF(q(17),q(14)))
    elif name == "join":
        p.drawLine(QPointF(q(6),q(8)),QPointF(q(16),q(16))); p.drawLine(QPointF(q(6),q(24)),QPointF(q(16),q(16))); p.drawLine(QPointF(q(16),q(16)),QPointF(q(27),q(16))); p.setBrush(ORANGE);p.setPen(Qt.NoPen);p.drawEllipse(QRectF(q(13.5),q(13.5),q(5),q(5)))
    else:
        p.setPen(_pen(INK,q(2))); p.drawEllipse(QRectF(q(7),q(7),q(18),q(18)))
        p.drawLine(QPointF(q(16),q(11)),QPointF(q(16),q(18))); p.drawEllipse(QRectF(q(15),q(21),q(2),q(2)))
    p.end()
    return QIcon(pm)


_SYMBOL_MAP = {
    "＋": "add_vertex", "+": "add_vertex", "✥": "move", "↔": "move",
    "↕": "vertical", "⌒": "curve_h", "∪": "curve_v", "▣": "opening",
    "□": "opening", "⊘": "delete", "⌫": "delete", "→": "extend",
    "⇧": "height", "∠": "incline", "⤢": "offset", "⇱": "stretch",
    "◩": "chamfer", "◜": "fillet", "▱": "rect", "⬠": "polygon",
    "⊥": "rect", "／": "wall", "⊙": "center_arc", "∴": "three_points",
    "⋈": "join", "": "curve_v",
}


def set_symbol_icon(button, symbol: str, size=22):
    """Replace legacy glyph buttons with consistent vector icons.

    Unknown symbols keep their text, so experimental commands remain usable.
    """
    key = _SYMBOL_MAP.get(str(symbol))
    if key is None:
        button.setText(str(symbol))
        return button
    button.setText("")
    button.setIcon(icon(key, 32))
    button.setIconSize(QSize(size, size))
    return button


# Design-system icons (24 x 24 coordinates, stroke-only).
# Existing symbols above remain available until the 7b widget integration.
_NAMES = (
    "wall", "wall_composite", "wall_curved", "slab", "slab_composite",
    "column", "beam", "profile", "opening", "door", "window",
    "opening_rect", "opening_square", "opening_circle", "opening_free",
    "anchor_left", "anchor_center", "anchor_right",
    "geo_segment", "geo_rect_diagonal", "geo_rect_base_width",
    "geo_arc_normal", "geo_arc_center", "geo_arc_three",
    "help", "collapse", "expand", "overflow",
)


def _stroke_path(*commands):
    path = QPainterPath()
    for op, coords in commands:
        if op == "M":
            path.moveTo(*coords)
        elif op == "L":
            path.lineTo(*coords)
        elif op == "Q":
            path.quadTo(*coords)
        elif op == "C":
            path.cubicTo(*coords)
        elif op == "Z":
            path.closeSubpath()
        elif op == "R":
            path.addRect(QRectF(*coords))
        elif op == "E":
            path.addEllipse(QRectF(*coords))
        else:
            raise ValueError(f"Unknown path operation: {op}")
    return path


@lru_cache(maxsize=len(_NAMES))
def _parts(name):
    """A distinctive primary silhouette and its one changeable accent."""
    def path(*ops):
        # Keep the reusable spec as immutable Python data. Construct only the
        # requested icon's two QPainterPaths, never all 56 on every repaint.
        return ops

    M = lambda x, y: ("M", (x, y))
    L = lambda x, y: ("L", (x, y))
    Q = lambda a, b, x, y: ("Q", (a, b, x, y))
    C = lambda a, b, c, d, x, y: ("C", (a, b, c, d, x, y))
    R = lambda x, y, w, h: ("R", (x, y, w, h))
    E = lambda x, y, w, h: ("E", (x, y, w, h))
    Z = ("Z", ())
    shapes = {
        "wall": (path(R(3, 6, 18, 12), M(3, 12), L(21, 12),
                      M(9, 6), L(9, 12), M(15, 12), L(15, 18)),
                 path(M(3, 18), L(9, 18))),
        "wall_composite": (path(R(3, 4, 18, 4), R(3, 10, 18, 4), R(3, 16, 18, 4)),
                           path(M(7, 8), L(7, 10), M(17, 14), L(17, 16))),
        "wall_curved": (path(M(4, 20), C(5, 8, 11, 3, 21, 4),
                             M(9, 21), C(10, 13, 14, 10, 21, 10)),
                        path(M(4, 20), L(9, 21))),
        "slab": (path(M(3, 11), L(16, 6), L(21, 10), L(8, 16), Z,
                      M(8, 16), L(8, 20), L(3, 15), L(3, 11)),
                 path(M(8, 20), L(21, 14), L(21, 10))),
        "slab_composite": (path(M(3, 7), L(15, 3), L(21, 7), L(9, 11), Z,
                                M(3, 12), L(9, 16), L(21, 12),
                                M(3, 17), L(9, 21), L(21, 17)),
                           path(M(9, 11), L(9, 16))),
        "column": (path(M(6, 6), L(15, 3), L(20, 7), L(11, 10), Z,
                        M(6, 6), L(6, 19), L(11, 22), L(11, 10),
                        M(11, 22), L(20, 19), L(20, 7)),
                   path(M(15, 3), L(15, 16))),
        "beam": (path(M(3, 5), L(21, 5), M(6, 8), L(18, 8), M(12, 8),
                      L(12, 18), M(6, 20), L(18, 20), M(3, 22), L(21, 22)),
                 path(M(12, 5), L(12, 8))),
        "profile": (path(M(5, 20), L(5, 5), L(15, 5), L(20, 9), L(15, 13),
                         L(10, 13), L(10, 20), Z),
                    path(E(13, 7, 4, 4))),
        "opening": (path(R(3, 5, 18, 15), M(3, 11), L(7, 11),
                         M(17, 11), L(21, 11)),
                    path(R(7, 9, 10, 11))),
        "door": (path(M(5, 20), L(5, 5), M(5, 20), L(19, 20),
                      M(5, 20), L(17, 8)),
                 path(M(19, 20), Q(19, 9, 5, 6))),
        "window": (path(R(4, 5, 16, 15), R(7, 8, 10, 9), M(12, 8), L(12, 17)),
                   path(M(7, 17), L(12, 12), L(17, 17))),
        "opening_rect": (path(R(3, 7, 18, 10)),
                         path(M(6, 17), L(18, 17))),
        "opening_square": (path(R(6, 5, 12, 12)),
                           path(M(18, 17), L(21, 20))),
        "opening_circle": (path(E(4, 4, 16, 16)),
                           path(M(12, 2), L(12, 5))),
        "opening_free": (path(M(4, 18), L(5, 7), L(14, 4), L(20, 11),
                              L(17, 20), Z),
                         path(M(14, 4), L(17, 7))),
        "anchor_left": (path(R(5, 7, 14, 11), M(3, 21), L(21, 21)),
                        path(M(5, 3), L(5, 21))),
        "anchor_center": (path(R(5, 7, 14, 11), M(3, 21), L(21, 21)),
                          path(M(12, 3), L(12, 21))),
        "anchor_right": (path(R(5, 7, 14, 11), M(3, 21), L(21, 21)),
                         path(M(19, 3), L(19, 21))),
        "geo_segment": (path(M(5, 18), L(19, 5)), path(E(3, 16, 4, 4), E(17, 3, 4, 4))),
        "geo_rect_diagonal": (path(R(4, 5, 16, 13)), path(M(4, 18), L(20, 5))),
        "geo_rect_base_width": (path(R(4, 4, 16, 12), M(4, 20), L(20, 20),
                                     M(4, 18), L(4, 22), M(20, 18), L(20, 22)),
                                path(M(12, 16), L(12, 20))),
        "geo_arc_normal": (path(M(4, 19), Q(10, 3, 20, 17)),
                           path(M(4, 19), L(8, 19), M(20, 17), L(20, 13))),
        "geo_arc_center": (path(M(4, 18), Q(11, 2, 20, 18), E(10, 12, 4, 4)),
                           path(M(12, 14), L(18, 9))),
        "geo_arc_three": (path(M(3, 19), Q(11, 2, 21, 19)),
                          path(E(2, 17, 2, 2), E(10, 7, 2, 2), E(20, 17, 2, 2))),
        "help": (path(E(3, 3, 18, 18), M(8, 9), Q(9, 5, 13, 7),
                      Q(18, 10, 12, 14), L(12, 16)),
                 path(M(12, 19), L(12, 20))),
        "collapse": (path(R(4, 4, 16, 16)), path(M(8, 14), L(12, 10), L(16, 14))),
        "expand": (path(R(4, 4, 16, 16)), path(M(8, 10), L(12, 14), L(16, 10))),
        "overflow": (path(E(4, 10, 3, 3), E(10.5, 10, 3, 3)),
                     path(E(17, 10, 3, 3))),
    }
    return tuple(_stroke_path(*commands) for commands in shapes[name])


def pixmap(name, size=24, state="normal", palette=None):
    """Paint a sharp stroke icon, using a constant 1.5 physical-pixel width."""
    if name not in _NAMES:
        return _legacy_icon(name, size).pixmap(size, size)
    from .style import tokens
    if palette is None:
        palette = QGuiApplication.palette()
    colors = tokens(palette)
    key = {
        "normal": "icon", "active": "icon-on-active",
        "marked": "icon-accent", "disabled": "icon-disabled",
    }.get(state)
    if key is None:
        raise ValueError(f"Unsupported icon state: {state}")
    # Rasterize on CPU-owned QImage. Painting many QPixmaps directly on
    # offscreen Qt 6.10 can corrupt native pixmap lifetime at shutdown.
    image = QImage(int(size), int(size), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(float(size) / 24, float(size) / 24)
    stroke = 1.5 * 24 / float(size)
    pen = QPen(colors[key], stroke)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setBrush(Qt.NoBrush)
    primary, accent = _parts(name)
    painter.setPen(pen)
    painter.drawPath(primary)
    if state == "normal":
        pen.setColor(colors["icon-accent"])
        painter.setPen(pen)
    painter.drawPath(accent)
    painter.end()
    return QPixmap.fromImage(image)


def icon(name, size=32, state="normal", palette=None):
    """Old 32 px call sites stay untouched until 7b; opt-in uses design paths."""
    if size == 32 and state == "normal" and palette is None:
        return _legacy_icon(name, size)
    return QIcon(pixmap(name, size, state, palette))
