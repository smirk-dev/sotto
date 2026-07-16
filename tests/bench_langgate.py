"""Can we stop Whisper mis-tagging Hindi, instead of paying to re-decode it?

engine.transcribe(language="auto") decodes once to auto-detect, and when Whisper
tags Hindi speech as Urdu/other Indic it decodes the WHOLE clip a second time
forcing "hi". On large-v3-turbo that second pass re-runs the 645 MB encoder --
the dominant cost -- so the Hinglish path costs ~2x the English one.

"auto" means English+Hindi. If suppress_tokens can take the other 98 language
tokens out of play, the model can only ever pick <|en|> or <|hi|>, so the
mis-tag (and the second pass) becomes impossible.

This checks whether openvino_genai actually honours that for the language slot.
"""

import json
import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.engine import CACHE_DIR, model_dir

import openvino_genai

NAME = "large-v3-turbo (multilingual)"
DEVICE = sys.argv[1] if len(sys.argv) > 1 else "GPU"
KEEP = ("<|en|>", "<|hi|>")


def load_wav(n):
    with wave.open(os.path.join(os.path.dirname(__file__), "wav", f"{n}.wav")) as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return d.astype(np.float32) / 32768.0


path = model_dir(NAME)
lang_to_id = json.load(open(os.path.join(path, "generation_config.json")))["lang_to_id"]
blocked = sorted(i for k, i in lang_to_id.items() if k not in KEEP)
print(f"{NAME} on {DEVICE}")
print(f"languages: {len(lang_to_id)} total, keeping {KEEP}, suppressing {len(blocked)}\n")

pipe = openvino_genai.WhisperPipeline(path, DEVICE, CACHE_DIR=CACHE_DIR)
clips = {n: load_wav(n) for n in ("hinglish", "short", "indian_en")}


def run(clip, suppress):
    gc = pipe.get_generation_config()
    gc.repetition_penalty = 1.2
    gc.task = "transcribe"
    gc.language = None                       # auto-detect
    gc.max_new_tokens = 440
    gc.suppress_tokens = list(blocked) if suppress else []
    t0 = time.perf_counter()
    res = pipe.generate(clips[clip], gc)
    dt = time.perf_counter() - t0
    return dt, str(res).strip(), (getattr(res, "language", "") or "")


for clip in ("hinglish", "short", "indian_en"):
    print(f"--- {clip} ({len(clips[clip])/16000:.1f}s) ---")
    for suppress in (False, True):
        try:
            dt, text, lang = run(clip, suppress)
        except Exception as e:
            print(f"  suppress={str(suppress):5} FAILED: {str(e)[:90]}")
            continue
        tag = "en+hi only" if suppress else "all 100  "
        print(f"  {tag}  {dt:5.2f}s  lang={lang or '?':8} {text[:64]!r}")
    print()
