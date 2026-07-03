"""Test the correct API path: modify the pipeline's own generation config object
(not a fresh one, not kwargs). Check language forcing, suppression, no_repeat,
and whether the result exposes the detected language."""

import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.config import MODELS_DIR

import openvino_genai

pipe = openvino_genai.WhisperPipeline(os.path.join(MODELS_DIR, "whisper-small-int8-ov"), "CPU")


def load(name):
    with wave.open(os.path.join(os.path.dirname(__file__), "wav", name)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


english = load("medium.wav")
rng = np.random.default_rng(1)
noise = (rng.standard_normal(16000 * 4) * 0.03).astype(np.float32)

# result introspection
res = pipe.generate(english)
print("WhisperDecodedResults attrs:", [a for a in dir(res) if not a.startswith("_")])
for a in ("texts", "scores", "chunks"):
    if hasattr(res, a):
        v = getattr(res, a)
        print(f"   {a}: {str(v)[:100]}")

# force Hindi on English audio via config OBJECT -> should be Devanagari if control works
gc = pipe.get_generation_config()
gc.language = "<|hi|>"
gc.task = "transcribe"
print("\nforce hi (config obj) on english:", str(pipe.generate(english, gc))[:120])

# no_repeat via config object on noise
gc2 = pipe.get_generation_config()
gc2.no_repeat_ngram_size = 3
print("\nnoise + no_repeat_ngram_size=3 (config obj):", repr(str(pipe.generate(noise, gc2))[:90]))

gc3 = pipe.get_generation_config()
gc3.repetition_penalty = 2.0
print("noise + repetition_penalty=2.0 (config obj):", repr(str(pipe.generate(noise, gc3))[:90]))

gc4 = pipe.get_generation_config()
gc4.max_new_tokens = 40
print("noise + max_new_tokens=40 (config obj):", repr(str(pipe.generate(noise, gc4))[:90]))
