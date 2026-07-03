"""Probe openvino_genai Whisper API + reproduce the noise-hallucination and
Hindi/Urdu problems so the fixes are grounded in observed behavior."""

import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.config import MODELS_DIR

import openvino_genai

# --- 1. API surface ---
cfg = openvino_genai.WhisperGenerationConfig()
print("WhisperGenerationConfig fields:")
for a in sorted(dir(cfg)):
    if not a.startswith("_"):
        try:
            print(f"   {a} = {getattr(cfg, a)!r}")
        except Exception as e:
            print(f"   {a} (?: {e})")

model_path = os.path.join(MODELS_DIR, "whisper-small-int8-ov")
pipe = openvino_genai.WhisperPipeline(model_path, "CPU")
print("\nWhisperPipeline.generate doc:")
print(getattr(openvino_genai.WhisperPipeline.generate, "__doc__", "")[:1500])

# --- 2. reproduce: static noise + near-silence under auto-detect ---
rng = np.random.default_rng(0)
clips = {
    "white_noise_mid": (rng.standard_normal(16000 * 4) * 0.05).astype(np.float32),
    "white_noise_low": (rng.standard_normal(16000 * 4) * 0.01).astype(np.float32),
    "near_silence": (rng.standard_normal(16000 * 4) * 0.001).astype(np.float32),
}
for name, audio in clips.items():
    rms = float(np.sqrt(np.mean(audio ** 2)))
    res = pipe.generate(audio)  # auto-detect, no language
    print(f"\n[{name} rms={rms:.4f}] -> {str(res)!r}")

# --- 3. Hindi forced vs auto on the synthetic hinglish clip ---
hp = os.path.join(os.path.dirname(__file__), "wav", "hinglish.wav")
if os.path.exists(hp):
    with wave.open(hp) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    print("\n--- hinglish clip ---")
    print("auto:", str(pipe.generate(a))[:120])
    try:
        c = openvino_genai.WhisperGenerationConfig()
        c.language = "<|hi|>"
        c.task = "transcribe"
        print("forced hi:", str(pipe.generate(a, c))[:120])
    except Exception as e:
        print("forced hi failed:", e)
