from PySide6.QtWidgets import QApplication

app = QApplication([])

import OpenTrace_BIM.icons
import OpenTrace_BIM.style
from views.theme import dark_palette

p = dark_palette()
del p
