from PySide6.QtWidgets import QApplication

app = QApplication([])

import OpenTrace_BIM.icons
import OpenTrace_BIM.style

pm = OpenTrace_BIM.icons.pixmap("wall", 24, palette=app.palette())
