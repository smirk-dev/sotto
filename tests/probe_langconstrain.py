"""Validate constraining Whisper's language choice via suppress_tokens, and
repeat-loop suppression via no_repeat_ngram_size."""

import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.config import MODELS_DIR

import openvino_genai

pipe = openvino_genai.WhisperPipeline(os.path.join(MODELS_DIR, "whisper-small-int8-ov"), "CPU")
gc = pipe.get_generation_config()
lang_to_id = dict(gc.lang_to_id)
print("num language tokens:", len(lang_to_id))
for k in ("<|en|>", "<|hi|>", "<|ur|>", "<|ja|>", "<|zh|>"):
    print(f"   {k} -> {lang_to_id.get(k)}")


def load(name):
    with wave.open(os.path.join(os.path.dirname(__file__), "wav", name)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


hinglish = load("hinglish.wav")
english = load("medium.wav")

# suppress every language token except en + hi -> detection constrained to {en, hi}
keep = {"<|en|>", "<|hi|>"}
suppress = [tid for tok, tid in lang_to_id.items() if tok not in keep]

print("\n-- hinglish, unconstrained auto --")
print(str(pipe.generate(hinglish))[:140])
print("-- hinglish, constrained to en+hi (Urdu suppressed) --")
print(str(pipe.generate(hinglish, suppress_tokens=suppress, task="transcribe"))[:140])

print("\n-- english, constrained to en+hi --")
print(str(pipe.generate(english, suppress_tokens=suppress, task="transcribe"))[:140])

# force-hi + suppress-all-but-hi: does English audio get transcribed as Hindi? (proves control)
only_hi = [tid for tok, tid in lang_to_id.items() if tok != "<|hi|>"]
print("\n-- english audio, forced to Hindi-only (sanity: should be Devanagari) --")
print(str(pipe.generate(english, suppress_tokens=only_hi, task="transcribe"))[:140])

# repeat-loop suppression on white noise
rng = np.random.default_rng(1)
noise = (rng.standard_normal(16000 * 4) * 0.03).astype(np.float32)
print("\n-- white noise, default --")
print(repr(str(pipe.generate(noise))[:80]))
print("-- white noise, no_repeat_ngram_size=3 + en/hi constrained --")
print(repr(str(pipe.generate(noise, suppress_tokens=suppress, no_repeat_ngram_size=3))[:80]))
