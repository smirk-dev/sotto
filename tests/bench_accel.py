"""Can large-v3-turbo be made fast enough to use as the daily driver?

PROGRESS.md rejected the GPU on small.en ("similar, 84 s first compile, high
variance"). That verdict may not carry to large-v3-turbo: its encoder is ~6x
bigger and compute-bound, which is the workload an iGPU is actually good at,
while small.en is dominated by the memory-bound autoregressive decoder.

Measures each candidate config cold (first call after load, what the user feels
on their first utterance) and warm (steady state), since the two diverge a lot.

Usage: bench_accel.py [model-key-substring]
"""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.config import MODELS, MODELS_DIR
from sotto.engine import CACHE_DIR, model_dir

import openvino_genai

WAV_DIR = os.path.join(os.path.dirname(__file__), "wav")
CLIPS = ("short", "indian_en", "medium")
WARM_RUNS = 3

# i7-1360P: 4 P-cores (8 logical w/ HT) + 8 E-cores. OpenVINO's default spreads
# work across all of them; on a hybrid chip the E-cores finish late and the fast
# threads block at the join, so latency tracks the SLOWEST core, not the mean.
CONFIGS = {
    "CPU (current default)": ("CPU", {}),
    "CPU +LATENCY": ("CPU", {"PERFORMANCE_HINT": "LATENCY"}),
    "CPU +LATENCY +PCORE_ONLY": ("CPU", {
        "PERFORMANCE_HINT": "LATENCY", "SCHEDULING_CORE_TYPE": "PCORE_ONLY"}),
    "CPU +LATENCY +PCORE_ONLY -HT": ("CPU", {
        "PERFORMANCE_HINT": "LATENCY", "SCHEDULING_CORE_TYPE": "PCORE_ONLY",
        "ENABLE_HYPER_THREADING": False}),
    "GPU": ("GPU", {}),
    "GPU +LATENCY": ("GPU", {"PERFORMANCE_HINT": "LATENCY"}),
}


def load_wav(name):
    with wave.open(os.path.join(WAV_DIR, f"{name}.wav")) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else "large-v3-turbo"
    name = next(k for k in MODELS if want in k)
    path = model_dir(name)
    audio = {c: load_wav(c) for c in CLIPS}
    print(f"=== {name} ===")
    print(f"clips: " + ", ".join(f"{c} {len(audio[c])/16000:.1f}s" for c in CLIPS))
    os.makedirs(CACHE_DIR, exist_ok=True)

    results = {}
    for label, (device, props) in CONFIGS.items():
        t0 = time.perf_counter()
        try:
            pipe = openvino_genai.WhisperPipeline(path, device, CACHE_DIR=CACHE_DIR, **props)
        except Exception as e:
            print(f"\n{label}: LOAD FAILED: {str(e)[:120]}")
            continue
        load_s = time.perf_counter() - t0
        print(f"\n{label}  (load {load_s:.1f}s)")
        row = {}
        for clip in CLIPS:
            times = []
            for run in range(WARM_RUNS + 1):
                t0 = time.perf_counter()
                text = str(pipe.generate(audio[clip]))
                times.append(time.perf_counter() - t0)
            cold, warm = times[0], min(times[1:])
            row[clip] = warm
            print(f"  {clip:10} cold {cold:6.2f}s   warm {warm:6.2f}s   "
                  f"({len(audio[clip])/16000/warm:4.1f}x realtime)")
            if clip == "short":
                print(f"             -> {text[:70]!r}")
        results[label] = row
        del pipe

    if results:
        base = results.get("CPU (current default)", {})
        print(f"\n{'config':32} {'short':>8} {'vs base':>9}")
        for label, row in sorted(results.items(), key=lambda kv: kv[1].get("short", 9e9)):
            s = row.get("short")
            rel = f"{base['short']/s:.2f}x" if base.get("short") and s else "-"
            print(f"{label:32} {s:7.2f}s {rel:>9}")


if __name__ == "__main__":
    main()
