"""End-to-end pipeline: WAV -> incremental DictationSession -> textproc -> injection.

Uses a fake recorder that replays the long test clip as if it were being spoken
live, so the >14 s incremental chunk-commit path actually runs.
"""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.engine import Engine, DictationSession
from sotto import textproc

EXPECTED_PHRASES = [
    "quick brown fox", "lazy dog", "microphone", "neural network",
    "focus", "subscription", "open source", "free of cost",
]


class FakeRecorder:
    """Replays a wav as if being captured live (2x speed)."""

    def __init__(self, audio):
        self.audio = audio
        self.t0 = time.monotonic()

    @property
    def sample_count(self):
        n = int((time.monotonic() - self.t0) * 2 * 16000)
        return min(n, len(self.audio))

    def read_range(self, start, end):
        return self.audio[start:end]


with wave.open(os.path.join(os.path.dirname(__file__), "wav", "long.wav")) as w:
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

engine = Engine()
state = {}
engine.on_state = lambda s: state.update(s=s)
engine.load("base.en", "CPU")
t0 = time.time()
while state.get("s") not in ("ready", "error") and time.time() - t0 < 120:
    time.sleep(0.2)
print(f"engine: {state.get('s')}")

rec = FakeRecorder(audio)
session = DictationSession(engine, rec, "auto", ["Suryansh"])
feeds = 0
while rec.sample_count < len(audio):
    session.feed()
    feeds += 1
    time.sleep(0.25)
committed_before_finish = session.committed
t0 = time.perf_counter()
session.finish(audio)
finish_dt = time.perf_counter() - t0
text = textproc.clean(session.full_text(), strip_fillers=True, dictionary=["Suryansh"])

print(f"chunks committed while 'speaking': {len(session.parts)} "
      f"({committed_before_finish/16000:.1f}s of {len(audio)/16000:.1f}s)")
print(f"finish (tail) latency: {finish_dt:.2f}s")
print(f"text: {text}")

missing = [p for p in EXPECTED_PHRASES if p not in text.lower()]
incremental_ok = committed_before_finish > 0
latency_ok = finish_dt < 2.0
print(f"[{'ok ' if incremental_ok else 'FAIL'}] incremental commits happened during recording")
print(f"[{'ok ' if latency_ok else 'FAIL'}] tail transcribed in <2s after stop")
print(f"[{'ok ' if not missing else 'FAIL'}] content check (missing: {missing})")
sys.exit(0 if (incremental_ok and latency_ok and not missing) else 1)
