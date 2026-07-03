"""Benchmark OpenVINO whisper-base.en int8 on CPU + test initial_prompt support."""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.config import MODELS_DIR

import openvino_genai

WAV_DIR = os.path.join(os.path.dirname(__file__), "wav")


def load_wav(name):
    with wave.open(os.path.join(WAV_DIR, f"{name}.wav")) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


model_path = os.path.join(MODELS_DIR, "whisper-base.en-int8-ov")
if not os.path.exists(os.path.join(model_path, "openvino_encoder_model.xml")):
    from huggingface_hub import snapshot_download
    print("downloading OpenVINO/whisper-base.en-int8-ov ...")
    snapshot_download("OpenVINO/whisper-base.en-int8-ov", local_dir=model_path)

t0 = time.perf_counter()
pipe = openvino_genai.WhisperPipeline(model_path, "CPU")
print(f"CPU: ready in {time.perf_counter()-t0:.1f}s")
for clip in ("short", "medium", "long"):
    audio = load_wav(clip)
    for run in (1, 2):
        t0 = time.perf_counter()
        result = pipe.generate(audio)
        dt = time.perf_counter() - t0
        print(f"  [{clip} {len(audio)/16000:4.1f}s run{run}] {dt:5.2f}s -> {str(result)[:110] if run==2 else ''}")

# does this openvino_genai support initial_prompt (for dictionary biasing)?
cfg = pipe.get_generation_config()
has_prompt = hasattr(cfg, "initial_prompt")
print("initial_prompt supported:", has_prompt)
if has_prompt:
    audio = load_wav("medium")
    t0 = time.perf_counter()
    r = pipe.generate(audio, initial_prompt="Vocabulary: Suryansh.")
    print(f"  with prompt {time.perf_counter()-t0:5.2f}s -> {str(r)[:110]}")
