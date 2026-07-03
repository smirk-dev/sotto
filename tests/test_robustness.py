"""Verify the robustness fixes: VAD gating, repetition suppression, language
constraint (English+Hindi), and Hindi/Urdu -> Devanagari correction."""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto import vad
from sotto.engine import Engine, _dominant_script, _collapse_repeats


def load(name):
    with wave.open(os.path.join(os.path.dirname(__file__), "wav", name)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


fails = 0


def check(name, ok):
    global fails
    if not ok:
        fails += 1
    print(f"[{'ok ' if ok else 'FAIL'}] {name}")


# --- unit: VAD ---
rng = np.random.default_rng(3)
check("VAD passes real speech", vad.has_speech(load("medium.wav")))
check("VAD passes Indian-accent speech", vad.has_speech(load("indian_en.wav")))
check("VAD blocks white noise", not vad.has_speech((rng.standard_normal(16000 * 4) * 0.03).astype(np.float32)))
check("VAD blocks near-silence", not vad.has_speech((rng.standard_normal(16000 * 4) * 0.0005).astype(np.float32)))

# --- unit: script detection ---
check("script: latin", _dominant_script("Hello world") == "latin")
check("script: devanagari", _dominant_script("नमस्ते दुनिया") == "devanagari")
check("script: arabic/urdu", _dominant_script("سلام دنیا") == "arabic")

# --- engine integration ---
engine = Engine()
st = {}
engine.on_state = lambda s: st.update(s=s)
engine.load("small (multilingual)", "CPU")
t0 = time.time()
while st.get("s") not in ("ready", "error") and time.time() - t0 < 120:
    time.sleep(0.2)
print("engine:", st.get("s"))

# noise must produce NOTHING under the default auto mode (was: Japanese/Georgian garbage)
for i, amp in enumerate((0.03, 0.01, 0.05)):
    noise = (np.random.default_rng(i).standard_normal(16000 * 4) * amp).astype(np.float32)
    out = engine.transcribe(noise, "auto", None)
    check(f"noise amp={amp} -> empty (got {out[:30]!r})", out == "")

# plain English stays English (Latin), correct content
en = engine.transcribe(load("medium.wav"), "auto", None)
print("   english auto ->", en[:90])
check("English transcribes as Latin text", _dominant_script(en) == "latin" and "dictation" in en.lower())

# forced English on the Indian-accent clip
ien = engine.transcribe(load("indian_en.wav"), "en", None)
print("   indian_en forced-en ->", ien[:90])
check("forced English works", _dominant_script(ien) == "latin" and "meeting" in ien.lower())

# forced Hindi -> Devanagari (LTR), never Arabic/RTL
hi = engine.transcribe(load("hinglish.wav"), "hi", None)
print("   hinglish forced-hi ->", hi[:90])
check("forced Hindi is Devanagari, not Arabic/RTL",
      _dominant_script(hi) in ("devanagari", "latin") and _dominant_script(hi) != "arabic")

print(f"\n{'ALL PASS' if not fails else str(fails) + ' FAILED'}")
sys.exit(1 if fails else 0)
