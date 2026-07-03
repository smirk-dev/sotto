"""Resample the WinRT clips to 16 kHz mono, then compare base.en vs
small (multilingual) auto on Indian-accent English and Hinglish."""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.engine import Engine

WAV = os.path.join(os.path.dirname(__file__), "wav")


def read_any(path):
    with wave.open(path) as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[sw]
    data = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if sw == 2:
        data /= 32768.0
    elif sw == 4:
        data /= 2147483648.0
    else:
        data = (data - 128) / 128.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if sr != 16000:  # linear resample
        n = int(len(data) * 16000 / sr)
        data = np.interp(np.linspace(0, len(data), n, endpoint=False),
                         np.arange(len(data)), data).astype(np.float32)
    return data


for name in ("indian_en", "hinglish"):
    src = os.path.join(WAV, f"{name}.src.wav")
    if not os.path.exists(src):
        continue
    audio = read_any(src)
    out = os.path.join(WAV, f"{name}.wav")
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    print(f"{name}: {len(audio)/16000:.1f}s -> {out}")

clips = {n: read_any(os.path.join(WAV, f"{n}.src.wav"))
         for n in ("indian_en", "hinglish") if os.path.exists(os.path.join(WAV, f"{n}.src.wav"))}

for model in ("base.en", "small (multilingual)"):
    e = Engine()
    st = {}
    e.on_state = lambda s: st.update(s=s)
    e.load(model, "CPU")
    t0 = time.time()
    while st.get("s") not in ("ready", "error") and time.time() - t0 < 120:
        time.sleep(0.2)
    print(f"\n=== {model} ({st.get('s')}) ===")
    for name, audio in clips.items():
        t0 = time.perf_counter()
        txt = e.transcribe(audio, "auto", None)
        dt = time.perf_counter() - t0
        print(f"[{name:9} {len(audio)/16000:4.1f}s {dt:4.1f}s] {txt}")
