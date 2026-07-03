"""Benchmark downloaded models on this machine: load time, transcribe time, output text."""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from faster_whisper import WhisperModel
from sotto.engine import model_dir

WAV_DIR = os.path.join(os.path.dirname(__file__), "wav")


def load_wav(path):
    with wave.open(path) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


clips = {n: load_wav(os.path.join(WAV_DIR, f"{n}.wav")) for n in ("short", "medium", "long")}

for name in ("small.en", "distil-small.en"):
    t0 = time.perf_counter()
    model = WhisperModel(model_dir(name), device="cpu", compute_type="int8")
    print(f"\n=== {name}  (load {time.perf_counter()-t0:.1f}s) ===")
    for clip, audio in clips.items():
        for beam in (1, 5):
            t0 = time.perf_counter()
            segs, _ = model.transcribe(audio, language="en", beam_size=beam,
                                       vad_filter=True, condition_on_previous_text=False,
                                       hotwords="Suryansh")
            text = " ".join(s.text.strip() for s in segs)
            dt = time.perf_counter() - t0
            dur = len(audio) / 16000
            print(f"[{clip} {dur:4.1f}s beam={beam}] {dt:5.2f}s -> {text}")
    del model
