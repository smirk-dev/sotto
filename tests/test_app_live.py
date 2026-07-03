"""Drive the real running app with injected hotkeys (SOTTO_ACCEPT_INJECTED=1):
hold Ctrl+Win for ~1.2 s of (probably silent) mic audio, release, and confirm
via the log that the full record->transcribe cycle ran. Also checks
single-instance: a second launch must exit immediately.
"""

import ctypes
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto import inject
from sotto.config import LOG_PATH

user32 = ctypes.WinDLL("user32")
VK_LCTRL, VK_LWIN = 0xA2, 0x5B
PY = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "python.exe"))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def send_vk(vk, up=False):
    inp = inject._key_event(vk=vk, flags=2 if up else 0)
    arr = (inject.INPUT * 1)(inp)
    user32.SendInput(1, arr, ctypes.sizeof(inject.INPUT))
    time.sleep(0.06)


env = dict(os.environ, SOTTO_ACCEPT_INJECTED="1", PYTHONIOENCODING="utf-8")
if os.path.exists(LOG_PATH):
    os.remove(LOG_PATH)
stderr_path = os.path.join(tempfile := os.environ.get("TEMP", "."), "sotto_app_stderr.txt")
app = subprocess.Popen([PY, "-m", "sotto"], cwd=ROOT, env=env,
                       stdout=open(stderr_path, "w"), stderr=subprocess.STDOUT)
print("waiting for model load…")
time.sleep(25)
assert app.poll() is None, "app died on startup"

# hold Ctrl+Win 1.2s, release  -> record + transcribe cycle (mic likely silent)
send_vk(VK_LCTRL); send_vk(VK_LWIN)
time.sleep(1.2)
send_vk(VK_LWIN, up=True); send_vk(VK_LCTRL, up=True)
time.sleep(8)

# toggle mode (Ctrl+Alt+D) on, wait, off -> exercises the live-typing/streaming path
VK_LALT, VK_D = 0xA4, 0x44
send_vk(VK_LCTRL); send_vk(VK_LALT); send_vk(VK_D)
send_vk(VK_D, up=True); send_vk(VK_LALT, up=True); send_vk(VK_LCTRL, up=True)
time.sleep(2.0)
send_vk(VK_LCTRL); send_vk(VK_LALT); send_vk(VK_D)
send_vk(VK_D, up=True); send_vk(VK_LALT, up=True); send_vk(VK_LCTRL, up=True)
time.sleep(8)

# single instance: second launch should exit quickly on its own
second = subprocess.Popen([PY, "-m", "sotto"], cwd=ROOT, env=env)
try:
    rc = second.wait(timeout=15)
    print(f"[ok ] second instance exited by itself (rc={rc})")
    single_ok = True
except subprocess.TimeoutExpired:
    second.kill()
    print("[FAIL] second instance kept running")
    single_ok = False

alive = app.poll() is None
print(f"[{'ok ' if alive else 'FAIL'}] app still running after dictation cycle")
app.terminate()

log_text = ""
if os.path.exists(LOG_PATH):
    with open(LOG_PATH, encoding="utf-8") as f:
        log_text = f.read()
print("--- app.log ---")
print(log_text or "(empty — no errors logged)")
time.sleep(1)
with open(stderr_path, encoding="utf-8", errors="replace") as f:
    err = f.read().strip()
print("--- app stdout/stderr ---")
print(err or "(empty)")
errors = [l for l in log_text.splitlines() if "ERROR" in l and "mic open failed" not in l]
print(f"[{'ok ' if not errors else 'FAIL'}] no unexpected errors in log")
cycle_ok = "dictation started" in log_text and "dictation finished" in log_text
print(f"[{'ok ' if cycle_ok else 'FAIL'}] full record->transcribe cycle ran")
stream_ok = "streaming=True" in log_text
print(f"[{'ok ' if stream_ok else 'FAIL'}] toggle mode ran in live-streaming mode")
sys.exit(0 if (alive and single_ok and not errors and cycle_ok and stream_ok) else 1)
