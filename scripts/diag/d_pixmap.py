"""Probe PySide6 None refcounts and high-volume icon rendering (diagnostics only)."""
import argparse
import gc
import sys

import PySide6
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication
from views.theme import dark_palette, light_palette

import OpenTrace_BIM.icons as icons
import OpenTrace_BIM.style  # same import context as the original reproduction


OPERATIONS = (
    "pixmap", "moveTo", "lineTo", "cubicTo", "quadTo", "closeSubpath",
    "addRect", "addEllipse", "drawPath", "setPen", "QPen",
    "setCapStyle", "setJoinStyle", "setColor", "fill", "fromImage",
    "setRenderHint", "scale", "setBrush",
)


def probe(operation_name, repeats, app):
    """Keep all supporting Qt objects alive outside the refcount interval."""
    dark = dark_palette()
    path = QPainterPath()
    path.moveTo(2.0, 3.0)
    rectangle = QRectF(2.0, 3.0, 8.0, 9.0)
    color = QColor("#42658d")
    pen = QPen(color, 1.5)
    image = QImage(24, 24, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = None
    if operation_name in ("drawPath", "setPen", "setRenderHint", "scale", "setBrush"):
        painter = QPainter(image)
    ops = {
        "pixmap": lambda: icons.pixmap("wall", 24, palette=dark),
        "moveTo": lambda: path.moveTo(5.0, 6.0),
        "lineTo": lambda: path.lineTo(7.0, 8.0),
        "cubicTo": lambda: path.cubicTo(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
        "quadTo": lambda: path.quadTo(1.0, 2.0, 3.0, 4.0),
        "closeSubpath": lambda: path.closeSubpath(),
        "addRect": lambda: path.addRect(rectangle),
        "addEllipse": lambda: path.addEllipse(rectangle),
        "drawPath": lambda: painter.drawPath(path),
        "setPen": lambda: painter.setPen(pen),
        "QPen": lambda: QPen(color, 1.5),
        "setCapStyle": lambda: pen.setCapStyle(Qt.RoundCap),
        "setJoinStyle": lambda: pen.setJoinStyle(Qt.RoundJoin),
        "setColor": lambda: pen.setColor(color),
        "fill": lambda: image.fill(Qt.transparent),
        "fromImage": lambda: QPixmap.fromImage(image),
        "setRenderHint": lambda: painter.setRenderHint(QPainter.Antialiasing),
        "scale": lambda: painter.scale(1.0, 1.0),
        "setBrush": lambda: painter.setBrush(Qt.NoBrush),
    }
    # GC happens before the baseline, never between measured calls.
    gc.collect()
    baseline = sys.getrefcount(None)
    for _ in range(repeats):
        ops[operation_name]()
    after = sys.getrefcount(None)
    print(
        f"REFCOUNT op={operation_name} n={repeats} before={baseline} "
        f"after={after} delta={after - baseline}", flush=True,
    )
    if painter is not None:
        painter.end()


def volume():
    app = QApplication.instance()
    palettes = (dark_palette(), light_palette())
    states = ("normal", "active", "marked", "disabled")
    sizes = (16, 20, 24)
    pixmaps = []
    for name in icons._NAMES:
        for state in states:
            for palette in palettes:
                for size in sizes:
                    pixmaps.append(icons.pixmap(name, size, state, palette))
        print(f"VOLUME count={len(pixmaps)} last_icon={name}", flush=True)
    print(f"VOLUME complete={len(pixmaps)} python={sys.version.split()[0]} "
          f"pyside={PySide6.__version__}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--operation", choices=OPERATIONS)
    group.add_argument("--volume", action="store_true")
    parser.add_argument("--repeats", type=int, choices=(1, 64), default=1)
    args = parser.parse_args()
    app = QApplication([])
    print(f"ENV python={sys.version.split()[0]} pyside={PySide6.__version__}", flush=True)
    if args.volume:
        volume()
    else:
        probe(args.operation, args.repeats, app)


if __name__ == "__main__":
    main()
