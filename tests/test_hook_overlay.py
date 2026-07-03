"""Verify the LL keyboard hook (chord + toggle, via injected events in test mode)
and that the overlay pill never steals focus. Also saves a screenshot of the pill."""

import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.hotkey import HotkeyHook
from sotto import inject

user32 = ctypes.WinDLL("user32")
VK_LCTRL, VK_LWIN, VK_LALT, VK_D = 0xA2, 0x5B, 0xA4, 0x44
KEYUP = 0x0002

fired = []


def send_vk(vk, up=False):
    inp = inject._key_event(vk=vk, flags=KEYUP if up else 0)
    arr = (inject.INPUT * 1)(inp)
    user32.SendInput(1, arr, ctypes.sizeof(inject.INPUT))
    time.sleep(0.05)


hook = HotkeyHook(lambda: fired.append("down"), lambda: fired.append("up"),
                  lambda: fired.append("toggle"))
hook.accept_injected = True
hook.set_bindings("Ctrl+Win", "Ctrl+Alt+D")
hook.start()
time.sleep(0.6)

# chord: hold Ctrl+Win, release
send_vk(VK_LCTRL); send_vk(VK_LWIN)
time.sleep(0.2)
send_vk(VK_LWIN, up=True); send_vk(VK_LCTRL, up=True)
time.sleep(0.2)

# toggle: Ctrl+Alt+D
send_vk(VK_LCTRL); send_vk(VK_LALT); send_vk(VK_D)
send_vk(VK_D, up=True); send_vk(VK_LALT, up=True); send_vk(VK_LCTRL, up=True)
time.sleep(0.3)
hook.stop()

expect = ["down", "up", "toggle"]
print(f"[{'ok ' if fired == expect else 'FAIL'}] hook events: {fired} (expected {expect})")

# ---- overlay focus test ----
from PySide6.QtWidgets import QApplication
from sotto.overlay import OverlayPill

app = QApplication(sys.argv)
fg_before = user32.GetForegroundWindow()
pill = OverlayPill()
pill.show_state("listening")
for i in range(24):
    pill.push_level(0.2 + 0.6 * ((i * 7) % 10) / 10)
app.processEvents()
time.sleep(0.5)
app.processEvents()
fg_after = user32.GetForegroundWindow()
print(f"[{'ok ' if fg_before == fg_after else 'FAIL'}] overlay does not steal focus "
      f"(fg {fg_before} -> {fg_after})")
print(f"[{'ok ' if pill.isVisible() else 'FAIL'}] overlay visible")

shot = os.path.join(os.path.dirname(__file__), "overlay.png")
pill.grab().save(shot)
print(f"screenshot -> {shot}")

pill.show_state("transcribing"); app.processEvents()
pill.grab().save(os.path.join(os.path.dirname(__file__), "overlay_transcribing.png"))
pill.show_state("inserted"); app.processEvents()
pill.grab().save(os.path.join(os.path.dirname(__file__), "overlay_inserted.png"))

ok = fired == expect and fg_before == fg_after
sys.exit(0 if ok else 1)
