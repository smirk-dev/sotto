"""Smoke test: enumerate input devices and capture 1 s from the default mic."""

import numpy as np
import sounddevice as sd

default_in = sd.default.device[0]
print("default input index:", default_in)
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        mark = "*" if i == default_in else " "
        print(f"{mark} [{i}] {d['name']} ({d['hostapi']}) ch={d['max_input_channels']}")

rec = sd.rec(int(1.0 * 16000), samplerate=16000, channels=1, dtype="float32")
sd.wait()
rms = float(np.sqrt(np.mean(rec**2)))
peak = float(np.max(np.abs(rec)))
print(f"captured 1.0s ok  rms={rms:.6f} peak={peak:.6f}")
