"""Dictation history window: search, click to copy."""

import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel,
    QApplication, QFrame,
)

from . import theme, history
from .settings_ui import TitleBar


class HistoryWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool)
        self.setWindowTitle("Sotto history")
        self.setFixedSize(520, 620)
        self._entries = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar("Dictation history", self))

        col = QVBoxLayout()
        col.setContentsMargins(18, 6, 18, 18)
        col.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.textChanged.connect(self._refill)
        col.addWidget(self.search)
        self.hint = QLabel("Click an entry to copy it.")
        self.hint.setProperty("muted", True)
        col.addWidget(self.hint)
        self.listw = QListWidget()
        self.listw.setWordWrap(True)
        self.listw.setFrameShape(QFrame.NoFrame)
        self.listw.itemClicked.connect(self._copy)
        col.addWidget(self.listw, 1)
        outer.addLayout(col)
        self.setStyleSheet(theme.QSS)

    def showEvent(self, e):
        super().showEvent(e)
        self._entries = history.load()
        self._refill()

    def _refill(self):
        q = self.search.text().lower().strip()
        self.listw.clear()
        for entry in self._entries:
            text = entry["text"]
            if q and q not in text.lower():
                continue
            when = datetime.datetime.fromtimestamp(entry["ts"]).strftime("%d %b %H:%M")
            item = QListWidgetItem(f"{when} · {entry['seconds']}s\n{text}")
            item.setData(Qt.UserRole, text)
            self.listw.addItem(item)
        if not self.listw.count():
            self.listw.addItem("Nothing here yet." if not q else "No matches.")

    def _copy(self, item):
        text = item.data(Qt.UserRole)
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.hint.setText("Copied ✓")
        QTimer.singleShot(1200, lambda: self.hint.setText("Click an entry to copy it."))
