"""Round-trip injection test against a real console window.

Spawns a PowerShell console with a unique window title, brings it to the
foreground (ALT-tap + SetForegroundWindow), injects text with each method,
and verifies the console captured exactly what we sent. Injection only
happens if the console really has focus (never types into another window).
"""

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto import inject

user32 = ctypes.WinDLL("user32")
user32.FindWindowW.restype = wt.HWND
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.GetForegroundWindow.restype = wt.HWND
VK_MENU = 0x12


def alt_tap():
    # pressing ALT makes Windows grant SetForegroundWindow to this process
    for flags in (0, 2):
        inp = inject._key_event(vk=VK_MENU, flags=flags)
        arr = (inject.INPUT * 1)(inp)
        user32.SendInput(1, arr, ctypes.sizeof(inject.INPUT))


def run_case(name, mode, text):
    out = os.path.join(tempfile.gettempdir(), f"sotto_inject_{name}.txt")
    if os.path.exists(out):
        os.remove(out)
    title = f"SOTTO_TEST_{name}_{os.getpid()}"
    ps = (f"$host.UI.RawUI.WindowTitle = '{title}'; "
          f"$x = Read-Host; Set-Content -Path '{out}' -Value $x -Encoding utf8")
    proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", ps],
                            creationflags=subprocess.CREATE_NEW_CONSOLE)
    hwnd = None
    for _ in range(50):
        time.sleep(0.1)
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            break
    if not hwnd:
        proc.kill()
        return f"[FAIL] {name}: console window not found"
    for _ in range(10):
        alt_tap()
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.15)
        if user32.GetForegroundWindow() == hwnd:
            break
    if user32.GetForegroundWindow() != hwnd:
        proc.kill()
        return f"[skip] {name}: could not focus console"
    time.sleep(0.3)
    ok = inject.insert_text(text + "\n", mode=mode, paste_threshold=10_000)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        return f"[FAIL] {name}: console never got the Enter key (insert ok={ok})"
    time.sleep(0.3)
    if not os.path.exists(out):
        return f"[FAIL] {name}: no output file (insert ok={ok})"
    with open(out, encoding="utf-8-sig") as f:
        got = f.read().strip()
    status = "ok " if got == text else "FAIL"
    return f"[{status}] {name}: sent={text!r} got={got!r}"


results = []

# 1) unicode typing path
results.append(run_case("type", "type",
                        "Sotto types anywhere — even em-dashes, café, naïve, 日本語."))

# 2) clipboard-paste path with save/restore
sentinel = "SENTINEL-" + str(int(time.time()))
inject._set_clipboard_text(sentinel)
results.append(run_case("paste", "paste", "Pasted by Sotto: quick brown fox 12345."))
time.sleep(0.5)
restored = inject._get_clipboard_text()
results.append(("[ok ] clipboard restored" if restored == sentinel
                else f"[FAIL] clipboard not restored: {restored!r}"))

print("\n".join(results))
sys.exit(1 if any("FAIL" in r for r in results) else 0)
