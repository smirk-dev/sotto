"""End-to-end check of the device change through the real transcribe() path.

bench_accel.py measures raw pipe.generate(). This goes through Engine.transcribe
as the app calls it — VAD gate, auto-language detection and correction, repeat
collapsing — so the numbers are what a user actually waits for, and the text is
what actually lands at their cursor.

Old behaviour (compute_device="CPU") vs new default ("Auto"), same clips.
"""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto import textproc
from sotto.engine import Engine

MODEL = "large-v3-turbo (multilingual)"
CLIPS = ("short", "indian_en", "medium", "hinglish")
RUNS = 3


def load_wav(n):
    with wave.open(os.path.join(os.path.dirname(__file__), "wav", f"{n}.wav")) as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return d.astype(np.float32) / 32768.0


def ready(device):
    e = Engine()
    st = {}
    e.on_state = lambda s: st.update(s=s)
    t0 = time.time()
    e.load(MODEL, device)
    while st.get("s") not in ("ready", "error") and time.time() - t0 < 300:
        time.sleep(0.2)
    if st.get("s") != "ready":
        raise SystemExit(f"{device}: load failed: {e.error}")
    print(f"{device:5} -> resolved to {e.device}, load {time.time()-t0:.1f}s")
    return e


clips = {c: load_wav(c) for c in CLIPS}
out = {}
for device in ("CPU", "Auto"):
    e = ready(device)
    out[device] = {}
    for c in CLIPS:
        times = []
        for _ in range(RUNS):
            t0 = time.perf_counter()
            raw = e.transcribe(clips[c], "auto", None)
            times.append(time.perf_counter() - t0)
        out[device][c] = (min(times), textproc.clean(raw, True, ["Suryansh"]))
    del e

print(f"\n{'clip':11} {'len':>5} {'CPU':>7} {'Auto':>7} {'speedup':>8}  text match")
for c in CLIPS:
    cpu_t, cpu_txt = out["CPU"][c]
    new_t, new_txt = out["Auto"][c]
    same = "same" if cpu_txt == new_txt else "DIFFERS"
    print(f"{c:11} {len(clips[c])/16000:4.1f}s {cpu_t:6.2f}s {new_t:6.2f}s "
          f"{cpu_t/new_t:7.2f}x  {same}")
    if cpu_txt != new_txt:
        print(f"    CPU : {cpu_txt!r}")
        print(f"    Auto: {new_txt!r}")
