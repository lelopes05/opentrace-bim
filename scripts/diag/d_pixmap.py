import gc
from PySide6.QtGui import QPixmapCache
from PySide6.QtWidgets import QApplication

app = QApplication([])

import OpenTrace_BIM.icons
import OpenTrace_BIM.style
from views.theme import dark_palette, light_palette

# Reproduce the full production sheet workload in one Python process.
# Retain the pixmaps through exit to test interpreter/Qt finalization.
palettes = (dark_palette(), light_palette())
states = ("normal", "active", "marked", "disabled")
sizes = (16, 20, 24)
pixmaps = [
    OpenTrace_BIM.icons.pixmap(name, size, state, palette)
    for name in OpenTrace_BIM.icons._NAMES
    for state in states
    for palette in palettes
    for size in sizes
]
print(f"Produced {len(pixmaps)} pixmaps across {len(OpenTrace_BIM.icons._NAMES)} icons", flush=True)

gc.collect()
QPixmapCache.clear()
QApplication.processEvents()
QApplication.shutdown()
print("Shutdown sequence completed", flush=True)
