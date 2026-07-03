"""Benchmark NVIDIA Parakeet-TDT 0.6B v2 int8 via onnx-asr (CPU)."""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.config import MODELS_DIR

import onnx_asr

WAV_DIR = os.path.join(os.path.dirname(__file__), "wav")


def load_wav(name):
    with wave.open(os.path.join(WAV_DIR, f"{name}.wav")) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


t0 = time.perf_counter()
model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2", quantization="int8")
print(f"load: {time.perf_counter()-t0:.1f}s")

for clip in ("short", "medium", "long"):
    audio = load_wav(clip)
    for run in (1, 2):
        t0 = time.perf_counter()
        text = model.recognize(audio)
        dt = time.perf_counter() - t0
        print(f"[{clip} {len(audio)/16000:4.1f}s run{run}] {dt:5.2f}s -> {text[:110] if run==2 else ''}")
