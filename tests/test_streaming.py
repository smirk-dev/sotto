"""Verify live-typing streaming: chunks are produced DURING recording (not only
at stop), they concatenate to the full transcript, and the repetition guard works."""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.engine import Engine, DictationSession, _collapse_repeats
from sotto import textproc

# --- repetition guard unit checks ---
rep = "तो मने कल का प्ल" + "्ट" * 200
assert len(_collapse_repeats(rep)) < 40, "runaway cluster not collapsed"
assert _collapse_repeats("aaaaaaaa") == "aa", _collapse_repeats("aaaaaaaa")
assert _collapse_repeats("hello world") == "hello world", "harmed normal text"
assert _collapse_repeats("that's the thing") == "that's the thing", "harmed normal text"
print("[ok ] repetition guard: collapses loops, leaves normal text intact")


class FakeRecorder:
    """Replays a wav as if captured live at `speed`x."""

    def __init__(self, audio, speed=3.0):
        self.audio, self.speed = audio, speed
        self.t0 = time.monotonic()

    @property
    def sample_count(self):
        return min(int((time.monotonic() - self.t0) * self.speed * 16000), len(self.audio))

    def read_range(self, start, end):
        return self.audio[start:end]


with wave.open(os.path.join(os.path.dirname(__file__), "wav", "long.wav")) as w:
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

engine = Engine()
st = {}
engine.on_state = lambda s: st.update(s=s)
engine.load("small (multilingual)", "CPU")
t0 = time.time()
while st.get("s") not in ("ready", "error") and time.time() - t0 < 120:
    time.sleep(0.2)
print(f"engine: {st.get('s')}")

rec = FakeRecorder(audio, speed=2.0)   # match real STREAM_MIN_S/STREAM_MAX_S
session = DictationSession(engine, rec, "auto", ["Suryansh"], min_commit_s=4, max_commit_s=24)

emitted = []          # (seconds_into_recording, text)
stream_full = ""
while rec.sample_count < len(audio):
    raw = session.feed()
    if raw:
        chunk = textproc.clean(raw, True, ["Suryansh"])
        emitted.append((round(time.monotonic() - rec.t0, 1), chunk))
        sep = " " if stream_full and not stream_full.endswith((" ", "\n")) else ""
        stream_full += sep + chunk
    time.sleep(0.2)

tail_raw = session.finish(audio)
tail = textproc.clean(tail_raw, True, ["Suryansh"])
if tail:
    stream_full += (" " if not stream_full.endswith((" ", "\n")) else "") + tail

total_playback = len(audio) / 16000 / 3.0  # wall seconds the "recording" lasted
print(f"emitted {len(emitted)} live chunks during a {total_playback:.1f}s recording:")
for t, c in emitted:
    print(f"   @{t:4.1f}s  {c[:70]}")
print(f"tail: {tail[:70]}")
print(f"full: {stream_full}")

live_ok = len(emitted) >= 2
early_ok = emitted and emitted[0][0] < total_playback - 1  # first chunk well before the end
phrases = ["quick brown fox", "neural network", "free of cost"]
content_ok = all(p in stream_full.lower() for p in phrases)
print(f"[{'ok ' if live_ok else 'FAIL'}] multiple chunks streamed during recording")
print(f"[{'ok ' if early_ok else 'FAIL'}] first chunk arrived mid-recording, not at the end")
print(f"[{'ok ' if content_ok else 'FAIL'}] streamed text covers the full transcript")
sys.exit(0 if (live_ok and early_ok and content_ok) else 1)
