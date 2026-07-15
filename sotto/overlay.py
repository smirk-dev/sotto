"""Floating recording pill: bottom-center, live waveform, never takes focus.

States: listening (live bars), transcribing (pulsing dots), inserted (check),
error (message). The window has WS_EX_NOACTIVATE so it can never steal focus.
"""

import math
import sys

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget

from . import theme

_BAR_COUNT = 20
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


class OverlayPill(QWidget):
    # Compact by default: listening/transcribing are the states that sit on screen
    # for as long as you speak, so they stay as small as the waveform allows. The
    # text states are brief and must stay legible, so they widen to fit their
    # message instead of clipping it (see _width_for).
    W, H = 150, 34
    _PAD_X = 14   # inset from the rounded ends for both bars and text

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(self.W, self.H)
        self._levels = [0.0] * _BAR_COUNT
        self._state = "listening"
        self._message = ""
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def _apply_noactivate(self):
        # Windows: set WS_EX_NOACTIVATE so the pill can never steal focus. On other
        # platforms the Qt flags in __init__ (Tool | WindowStaysOnTop |
        # WA_ShowWithoutActivating | NoFocus) already achieve this.
        if sys.platform != "win32":
            return
        import ctypes
        hwnd = int(self.winId())
        user32 = ctypes.WinDLL("user32")
        user32.GetWindowLongPtrW.restype = ctypes.c_longlong
        user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]
        style = user32.GetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
        user32.SetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_EXSTYLE,
                                 style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)

    def _place(self):
        screen = self.screen() or self.window().screen()
        geo = screen.availableGeometry()
        self.move(geo.center().x() - self.width() // 2, geo.bottom() - self.height() - 28)

    def _text_font(self):
        f = QFont(self.font())
        f.setPointSize(8)
        f.setWeight(QFont.DemiBold)
        return f

    def _text_for(self, state, message):
        if state == "inserted":
            return "✓  inserted"
        return message or "error"

    def _width_for(self, state, message):
        """Compact for the waveform states, wide enough to hold the text ones."""
        if state in ("listening", "transcribing"):
            return self.W
        advance = QFontMetrics(self._text_font()).horizontalAdvance(
            self._text_for(state, message))
        return max(self.W, advance + 2 * self._PAD_X + 12)

    # ---- public API (call from the GUI thread) ----

    def show_state(self, state: str, message: str = ""):
        self._state = state
        self._message = message
        self._phase = 0
        self._hide_timer.stop()
        if state in ("listening", "transcribing"):
            self._timer.start(50)
        else:
            self._timer.stop()
            self._hide_timer.start(1400 if state == "inserted" else 2600)
        width = self._width_for(state, message)
        resized = width != self.width()
        if resized:
            self.setFixedSize(width, self.H)
        if not self.isVisible():
            self._place()
            self.show()
            self._apply_noactivate()
        elif resized:
            self._place()   # keep it centred as the pill grows or shrinks
        self.update()

    def push_level(self, level: float):
        self._levels = self._levels[1:] + [level]

    def dismiss(self):
        self._timer.stop()
        self.hide()

    # ---- painting ----

    def _tick(self):
        self._phase += 1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.height()
        rect = QRectF(1, 1, self.width() - 2, h - 2)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(QColor(16, 16, 20, 242))
        p.drawRoundedRect(rect, h / 2 - 1, h / 2 - 1)

        if self._state == "listening":
            self._paint_bars(p, QColor(theme.ACCENT))
        elif self._state == "transcribing":
            self._paint_dots(p)
        elif self._state == "inserted":
            self._paint_text(p, self._text_for("inserted", ""), theme.OK)
        elif self._state == "error":
            self._paint_text(p, self._text_for("error", self._message), theme.ERROR)
        p.end()

    def _paint_bars(self, p, color):
        bw = (self.width() - 2 * self._PAD_X) / _BAR_COUNT
        cy = self.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        for i, lvl in enumerate(self._levels):
            h = max(2.0, min(1.0, lvl) * (self.height() - 14))
            x = self._PAD_X + i * bw
            p.drawRoundedRect(QRectF(x + bw * 0.22, cy - h / 2, bw * 0.56, h), 1.5, 1.5)

    def _paint_dots(self, p):
        cy = self.height() / 2
        d, gap = 5.0, 12.0
        x0 = self.width() / 2 - gap - d / 2
        p.setPen(Qt.NoPen)
        for i in range(3):
            k = (self._phase * 0.18 - i * 0.55)
            a = 0.35 + 0.65 * max(0.0, math.sin(k)) ** 2
            c = QColor(theme.ACCENT)
            c.setAlphaF(a)
            p.setBrush(c)
            p.drawEllipse(QRectF(x0 + i * gap, cy - d / 2, d, d))

    def _paint_text(self, p, text, color):
        p.setPen(QColor(color))
        p.setFont(self._text_font())
        p.drawText(self.rect(), Qt.AlignCenter, text)
