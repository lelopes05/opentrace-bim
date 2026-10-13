# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a visual icon review artifact outside the host unittest process."""
from pathlib import Path
import gc

from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication
from views.theme import dark_palette, light_palette

from OpenTrace_BIM.icons import _NAMES, pixmap
from OpenTrace_BIM.style import tokens


def render_sheet(app, destination):
    """Render every icon in both themes and all four states."""
    palettes = (("Escuro", dark_palette()), ("Claro", light_palette()))
    states = ("normal", "active", "marked", "disabled")
    row_height, cell_width, label_width = 38, 47, 135
    width = label_width + len(palettes) * len(states) * cell_width
    height = 45 + row_height * len(_NAMES)

    sheet = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    sheet.fill(QColor("#FFFFFF"))
    painter = QPainter(sheet)
    try:
        font = QFont(app.font())
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(QColor("#111111"))
        for theme_index, (heading, _palette) in enumerate(palettes):
            for state_index, state in enumerate(states):
                x = label_width + (theme_index * len(states) + state_index) * cell_width
                painter.drawText(x, 22, heading[:1] + " " + state[:5])

        for index, name in enumerate(_NAMES):
            y = 45 + index * row_height
            painter.setPen(QColor("#111111"))
            painter.drawText(4, y + 22, name)
            for theme_index, (_heading, palette) in enumerate(palettes):
                for state_index, state in enumerate(states):
                    x = label_width + (theme_index * len(states) + state_index) * cell_width
                    painter.fillRect(x, y, cell_width, row_height, tokens(palette)["panel"])
                    painter.drawPixmap(x + 11, y + 7, pixmap(name, 24, state, palette))
    finally:
        painter.end()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not sheet.save(str(destination), "PNG"):
        raise RuntimeError(f"Cannot save icon sheet: {destination}")


def main():
    destination = Path(__file__).resolve().parents[1] / "docs" / "icons_sheet.png"
    app = QApplication.instance() or QApplication([])
    try:
        render_sheet(app, destination)
        print(f"Icon sheet created: {destination}")
    finally:
        app.quit()
        del app
        gc.collect()


if __name__ == "__main__":
    main()
