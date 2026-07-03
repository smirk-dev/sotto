"""Benchmark large-v3-turbo (multilingual) latency vs small on this machine."""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.engine import Engine


def load(name):
    with wave.open(os.path.join(os.path.dirname(__file__), "wav", name)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


clips = {n: load(f"{n}.wav") for n in ("short", "medium", "long", "indian_en")}

for model in ("large-v3-turbo (multilingual)",):
    e = Engine()
    st = {}
    e.on_state = lambda s: st.update(s=s)
    t0 = time.time()
    e.load(model, "CPU")
    while st.get("s") not in ("ready", "error") and time.time() - t0 < 300:
        time.sleep(0.3)
    print(f"=== {model} ({st.get('s')}) load {time.time()-t0:.1f}s ===")
    for name, audio in clips.items():
        for _ in range(2):
            t0 = time.perf_counter()
            txt = e.transcribe(audio, "auto", None)
            dt = time.perf_counter() - t0
        dur = len(audio) / 16000
        print(f"[{name:9} {dur:4.1f}s] {dt:5.2f}s ({dur/dt:.1f}x rt) -> {txt[:90]}")
