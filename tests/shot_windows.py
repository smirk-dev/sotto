"""Grab screenshots of the settings and history windows for a design check."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication

from sotto import theme, history
from sotto.config import Config
from sotto.settings_ui import SettingsWindow
from sotto.history_ui import HistoryWindow

app = QApplication(sys.argv)
app.setStyleSheet(theme.QSS)
cfg = Config()

history.append("This is what a dictated entry looks like in history.", 4.2)
history.append("Sotto keeps everything on this computer — nothing is uploaded.", 6.8)

s = SettingsWindow(cfg)
s.show()
app.processEvents()
s.grab().save(os.path.join(os.path.dirname(__file__), "settings.png"))

h = HistoryWindow()
h.show()
app.processEvents()
h.grab().save(os.path.join(os.path.dirname(__file__), "history.png"))
print("saved settings.png, history.png")
s.hide(); h.hide()
