"""What does the FIRST GPU load cost a user, with no compile cache?

PROGRESS.md rejected the GPU partly on an "84 s first compile" (small.en, an
older OpenVINO). That is a real first-run cost: the app loads the model at
startup, so a long compile is dead time before the first dictation works.

Moves the cache aside, times a cold compile + a warm reload, then restores it.
"""

import os
import shutil
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.config import MODELS
from sotto.engine import CACHE_DIR, model_dir

import openvino_genai

name = "large-v3-turbo (multilingual)"
path = model_dir(name)
with wave.open(os.path.join(os.path.dirname(__file__), "wav", "short.wav")) as w:
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

stash = CACHE_DIR + ".stash"
for p in (stash,):
    if os.path.exists(p):
        shutil.rmtree(p)
if os.path.exists(CACHE_DIR):
    shutil.move(CACHE_DIR, stash)
os.makedirs(CACHE_DIR, exist_ok=True)

try:
    for label in ("COLD (empty cache)", "WARM (cache populated)"):
        t0 = time.perf_counter()
        pipe = openvino_genai.WhisperPipeline(path, "GPU", CACHE_DIR=CACHE_DIR)
        load = time.perf_counter() - t0
        t0 = time.perf_counter()
        pipe.generate(audio)
        gen = time.perf_counter() - t0
        size = sum(os.path.getsize(os.path.join(CACHE_DIR, f))
                   for f in os.listdir(CACHE_DIR))
        print(f"{label:24} load {load:6.1f}s   first generate {gen:5.2f}s   "
              f"cache now {size/1e6:6.1f} MB")
        del pipe
finally:
    shutil.rmtree(CACHE_DIR, ignore_errors=True)
    if os.path.exists(stash):
        shutil.move(stash, CACHE_DIR)
    print("cache restored")
