"""Benchmark small (multilingual) with language=auto vs small.en on the English
clips: confirms auto-detect keeps English accurate and measures latency."""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.engine import Engine

WAV = os.path.join(os.path.dirname(__file__), "wav")


def load(name):
    with wave.open(os.path.join(WAV, name)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


clips = {n: load(f"{n}.wav") for n in ("short", "medium", "long") if os.path.exists(os.path.join(WAV, f"{n}.wav"))}
# optional extra clips (Hinglish / Indian-accent) if they were generated
for extra in ("indian_en", "hinglish"):
    p = os.path.join(WAV, f"{extra}.wav")
    if os.path.exists(p):
        clips[extra] = load(f"{extra}.wav")

for model in ("small.en", "small (multilingual)"):
    e = Engine()
    st = {}
    e.on_state = lambda s: st.update(s=s)
    e.load(model, "CPU")
    t0 = time.time()
    while st.get("s") not in ("ready", "error") and time.time() - t0 < 120:
        time.sleep(0.2)
    print(f"\n=== {model} ({st.get('s')}) ===")
    for name, audio in clips.items():
        for _ in range(2):
            t0 = time.perf_counter()
            txt = e.transcribe(audio, "auto", None)
            dt = time.perf_counter() - t0
        dur = len(audio) / 16000
        print(f"[{name:9} {dur:5.1f}s] {dt:5.2f}s ({dur/dt:.1f}x rt) -> {txt[:120]}")
