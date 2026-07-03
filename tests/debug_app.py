"""Diagnose: run SottoApp in-process, inject Ctrl+Win hold/release, trace signals."""

import ctypes
import logging
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SOTTO_ACCEPT_INJECTED"] = "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stdout)

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from sotto import inject, theme
from sotto.app import SottoApp

user32 = ctypes.WinDLL("user32")
VK_LCTRL, VK_LWIN = 0xA2, 0x5B


def send_vk(vk, up=False):
    inp = inject._key_event(vk=vk, flags=2 if up else 0)
    arr = (inject.INPUT * 1)(inp)
    user32.SendInput(1, arr, ctypes.sizeof(inject.INPUT))


qapp = QApplication(sys.argv)
qapp.setStyleSheet(theme.QSS)
app = SottoApp(qapp)

app.sig_hold_down.connect(lambda: print(">> sig_hold_down"))
app.sig_hold_up.connect(lambda: print(">> sig_hold_up"))
app.sig_finished.connect(lambda t, d, ok: print(f">> sig_finished text={t!r} ok={ok}"))


def drive():
    while app.engine.state != "ready":
        time.sleep(0.3)
    print("engine ready; pressing Ctrl+Win")
    send_vk(VK_LCTRL); time.sleep(0.08); send_vk(VK_LWIN)
    time.sleep(1.5)
    print("releasing")
    send_vk(VK_LWIN, up=True); time.sleep(0.08); send_vk(VK_LCTRL, up=True)
    time.sleep(6)
    print(f"final: recording={app.recording} busy={app.busy}")
    QTimer.singleShot(0, app.quit)


threading.Thread(target=drive, daemon=True).start()
qapp.exec()
print("exited cleanly")
