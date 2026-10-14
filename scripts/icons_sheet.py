# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a visual icon review artifact outside the host unittest process."""
from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from views.theme import dark_palette, light_palette

from OpenTrace_BIM.icons import _NAMES, pixmap
from OpenTrace_BIM.style import tokens


def render_sheet(app, destination):
    """Render every icon in both themes and all four states."""
    palettes = (("Escuro", dark_palette()), ("Claro", light_palette()))
    states = ("normal", "active", "marked", "disabled")
    row_height, cell_width, margin = 38, 47, 12
    width = margin * 2 + len(palettes) * len(states) * cell_width
    height = margin * 2 + row_height * len(_NAMES)

    # Do not load Qt fonts in the offscreen artifact generator: Qt's font
    # database may crash during Python interpreter shutdown (none_dealloc).
    sheet = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    sheet.fill(QColor("#FFFFFF"))
    painter = QPainter(sheet)
    try:
        for index, name in enumerate(_NAMES):
            y = margin + index * row_height
            for theme_index, (_heading, palette) in enumerate(palettes):
                for state_index, state in enumerate(states):
                    x = margin + (theme_index * len(states) + state_index) * cell_width
                    painter.fillRect(x, y, cell_width, row_height, tokens(palette)["panel"])
                    painter.drawPixmap(x + 11, y + 7, pixmap(name, 24, state, palette))
    finally:
        painter.end()

    destination.parent.mkdir(parents=True, exist_ok=True)
    if not sheet.save(str(destination), "PNG"):
        raise RuntimeError(f"Cannot save icon sheet: {destination}")

    label_file = destination.with_suffix(".txt")
    labels = [
        "OpenTrace BIM icon sheet — no font rendering",
        "Columns from left to right (47 px each):",
        *[f"{heading}: {state}" for heading, _palette in palettes for state in states],
        "Rows from top to bottom (38 px each, starting at y=12):",
        *[f"{index + 1:03d}. {name}" for index, name in enumerate(_NAMES)],
    ]
    label_file.write_text("\n".join(labels) + "\n", encoding="utf-8")


def main():
    destination = Path(__file__).resolve().parents[1] / "docs" / "icons_sheet.png"
    app = QApplication.instance() or QApplication([])
    try:
        render_sheet(app, destination)
        print(f"Icon sheet created: {destination}")
    finally:
        app.quit()


if __name__ == "__main__":
    main()
