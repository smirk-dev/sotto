"""Isolate the latency problem: thread counts, VAD on/off, repeat runs."""

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

print(f"clip: {len(audio)/16000:.1f}s   os.cpu_count={os.cpu_count()}")
for threads in (0, 4, 8, 12, 16):
    model = WhisperModel(model_dir("small.en"), device="cpu", compute_type="int8",
                         cpu_threads=threads)
    for run in (1, 2):
        for vad in (True, False):
            t0 = time.perf_counter()
            segs, _ = model.transcribe(audio, language="en", beam_size=1, vad_filter=vad,
                                       condition_on_previous_text=False)
            _ = " ".join(s.text for s in segs)
            print(f"threads={threads:2d} run={run} vad={int(vad)}: {time.perf_counter()-t0:5.2f}s")
    del model
