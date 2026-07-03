"""Nail down: res.language format, repetition_penalty impact on real speech,
and Silero VAD speech-vs-noise discrimination."""

import os
import sys
import wave

import numpy as np
import onnxruntime as ort

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.config import MODELS_DIR

import openvino_genai

pipe = openvino_genai.WhisperPipeline(os.path.join(MODELS_DIR, "whisper-small-int8-ov"), "CPU")


def load(name):
    with wave.open(os.path.join(os.path.dirname(__file__), "wav", name)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


rng = np.random.default_rng(1)
noise = (rng.standard_normal(16000 * 4) * 0.03).astype(np.float32)
samples = {"english": load("medium.wav"), "hinglish": load("hinglish.wav"),
           "indian_en": load("indian_en.wav"), "noise": noise}

print("=== detected language + repetition_penalty sweep ===")
for name, audio in samples.items():
    r = pipe.generate(audio)
    langs = getattr(r, "language", None)
    print(f"\n[{name}] detected language = {langs!r}")
    for rp in (1.0, 1.15, 1.3):
        gc = pipe.get_generation_config()
        gc.repetition_penalty = rp
        txt = str(pipe.generate(audio, gc))
        print(f"   rp={rp}: {txt[:95]}")

# === Silero VAD ===
print("\n=== Silero VAD (speech prob per sample) ===")
sess = ort.InferenceSession(os.path.join("build_assets", "silero_vad.onnx"),
                            providers=["CPUExecutionProvider"])
print("inputs:", [(i.name, i.shape, i.type) for i in sess.get_inputs()])
print("outputs:", [(o.name, o.shape) for o in sess.get_outputs()])


def speech_probs(audio):
    state = np.zeros((2, 1, 128), dtype=np.float32)
    sr = np.array(16000, dtype=np.int64)
    probs = []
    for i in range(0, len(audio) - 512, 512):
        win = audio[i:i + 512].astype(np.float32).reshape(1, -1)
        out, state = sess.run(None, {"input": win, "state": state, "sr": sr})
        probs.append(float(out[0][0]))
    return np.array(probs) if probs else np.zeros(1)


for name, audio in samples.items():
    p = speech_probs(audio)
    print(f"[{name:9}] max={p.max():.2f} mean={p.mean():.2f} frac>0.5={np.mean(p>0.5):.2f}")
