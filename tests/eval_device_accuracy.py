"""Does moving the big model to the iGPU cost accuracy on Hindi/Hinglish?

The device change is only worth taking if it is free in quality — large-v3-turbo
was chosen precisely for code-switched Hindi, so a faster-but-worse GPU path
would defeat the point. CPU runs int8; the GPU path runs fp16 internally, so the
two are not bit-identical and the difference has to be measured, not assumed.

Scores character error rate against ground truth (Devanagari + English nouns, so
CER is fairer than WER here). Clips live in tests/wav/hi with truth.tsv; regenerate
or extend them with tests/make_hinglish_clips.py.

The absolute CER (~15%) is mostly a TTS artifact — Kokoro pronounces "plan
finalize" with a Hindi accent and Whisper faithfully writes "प्लान फाइनलाईस". It is
the CPU-vs-GPU *delta* that this test exists to watch.

Usage: eval_device_accuracy.py [clip-dir]
"""

import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto import textproc
from sotto.engine import Engine

CLIP_DIR = (sys.argv[1] if len(sys.argv) > 1
            else os.path.join(os.path.dirname(os.path.abspath(__file__)), "wav", "hi"))
MODEL = "large-v3-turbo (multilingual)"


def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def norm(s):
    """Ignore punctuation/case/spacing — we are scoring recognition, not formatting."""
    keep = [c.lower() for c in s if c.isalnum() or c.isspace()]
    return " ".join("".join(keep).split())


def load_wav(p):
    with wave.open(p) as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return d.astype(np.float32) / 32768.0


truth = {}
with open(os.path.join(CLIP_DIR, "truth.tsv"), encoding="utf-8") as f:
    for line in f:
        k, t = line.rstrip("\n").split("\t")
        truth[k] = t
clips = {k: load_wav(os.path.join(CLIP_DIR, f"{k}.wav")) for k in truth}
print(f"{len(clips)} clips, model={MODEL}\n")


def ready(device):
    e = Engine()
    st = {}
    e.on_state = lambda s: st.update(s=s)
    e.load(MODEL, device)
    t0 = time.time()
    while st.get("s") not in ("ready", "error") and time.time() - t0 < 300:
        time.sleep(0.2)
    if st.get("s") != "ready":
        raise SystemExit(f"{device} load failed: {e.error}")
    return e


results = {}
for device in ("CPU", "GPU"):
    e = ready(device)
    per_clip, tot_err, tot_len, tot_t = {}, 0, 0, 0.0
    for k, audio in clips.items():
        t0 = time.perf_counter()
        raw = e.transcribe(audio, "auto", None)
        tot_t += time.perf_counter() - t0
        got = textproc.clean(raw, True, ["Suryansh"])
        ref, hyp = norm(truth[k]), norm(got)
        err = levenshtein(ref, hyp)
        per_clip[k] = (err / max(1, len(ref)), got)
        tot_err += err
        tot_len += len(ref)
    results[device] = (tot_err / tot_len, tot_t / len(clips), per_clip)
    print(f"{device}: CER {tot_err/tot_len:.1%}  mean {tot_t/len(clips):.2f}s/clip"
          f"  (engine used {e.device})")
    del e

cpu_cer, cpu_t, cpu_clips = results["CPU"]
gpu_cer, gpu_t, gpu_clips = results["GPU"]
print(f"\n{'clip':6} {'CPU CER':>8} {'GPU CER':>8}   text")
for k in sorted(clips):
    c_cer, c_txt = cpu_clips[k]
    g_cer, g_txt = gpu_clips[k]
    flag = "" if abs(c_cer - g_cer) < 0.02 else ("  <-- GPU WORSE" if g_cer > c_cer
                                                 else "  <-- GPU BETTER")
    print(f"{k:6} {c_cer:7.1%} {g_cer:7.1%}{flag}")
    print(f"       truth: {truth[k]}")
    if c_txt != g_txt:
        print(f"       CPU  : {c_txt}")
        print(f"       GPU  : {g_txt}")
    else:
        print(f"       both : {c_txt}")

print(f"\nCER  CPU {cpu_cer:.1%}  vs  GPU {gpu_cer:.1%}   "
      f"(delta {gpu_cer-cpu_cer:+.1%})")
print(f"time CPU {cpu_t:.2f}s vs  GPU {gpu_t:.2f}s   ({cpu_t/gpu_t:.2f}x faster)")
