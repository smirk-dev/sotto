"""Compare compute types and P-core affinity for ctranslate2 on hybrid CPU."""

import ctypes
import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from faster_whisper import WhisperModel
from sotto.engine import model_dir

with wave.open(os.path.join(os.path.dirname(__file__), "wav", "short.wav")) as w:
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

affinity = sys.argv[1] if len(sys.argv) > 1 else "all"
if affinity == "pcores":
    # i7-1360P: logical 0-7 are the 4 P-cores with HT
    ctypes.WinDLL("kernel32").SetProcessAffinityMask(
        ctypes.WinDLL("kernel32").GetCurrentProcess(), 0x00FF)

for ct in ("int8", "int8_float32", "float32"):
    try:
        model = WhisperModel(model_dir("small.en"), device="cpu", compute_type=ct, cpu_threads=8)
    except Exception as e:
        print(f"{ct}: load failed: {e}")
        continue
    times = []
    for _ in range(2):
        t0 = time.perf_counter()
        segs, _ = model.transcribe(audio, language="en", beam_size=1, vad_filter=True,
                                   condition_on_previous_text=False)
        _ = " ".join(s.text for s in segs)
        times.append(time.perf_counter() - t0)
    print(f"affinity={affinity} {ct}: {', '.join(f'{t:.2f}s' for t in times)}")
    del model
