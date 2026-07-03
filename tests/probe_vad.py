"""Compare a pure-numpy spectral-flatness gate vs Silero (fed the whole clip)
for separating speech from static noise."""

import os
import sys
import wave

import numpy as np
import onnxruntime as ort

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(name):
    with wave.open(os.path.join(os.path.dirname(__file__), "wav", name)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


rng = np.random.default_rng(1)
samples = {
    "english": load("medium.wav"),
    "hinglish": load("hinglish.wav"),
    "indian_en": load("indian_en.wav"),
    "white_noise": (rng.standard_normal(16000 * 4) * 0.03).astype(np.float32),
    "pink_ish": np.cumsum(rng.standard_normal(16000 * 4)).astype(np.float32) * 0.001,
    "silence": (rng.standard_normal(16000 * 4) * 0.0005).astype(np.float32),
}


def spectral_flatness(audio, frame=1024):
    """Mean spectral flatness over voiced-energy frames. ~1 = flat (noise),
    low = tonal/peaky (speech)."""
    flats = []
    for i in range(0, len(audio) - frame, frame // 2):
        f = audio[i:i + frame] * np.hanning(frame)
        mag = np.abs(np.fft.rfft(f)) + 1e-10
        rms = np.sqrt(np.mean(f ** 2))
        if rms < 0.005:            # ignore quiet frames
            continue
        gmean = np.exp(np.mean(np.log(mag)))
        amean = np.mean(mag)
        flats.append(gmean / amean)
    return float(np.mean(flats)) if flats else 1.0


print("=== spectral flatness (low=speech, high=noise) + energy ===")
for name, audio in samples.items():
    sf = spectral_flatness(audio)
    rms = float(np.sqrt(np.mean(audio ** 2)))
    voiced = np.mean([np.sqrt(np.mean((audio[i:i+1024])**2)) > 0.01
                      for i in range(0, len(audio)-1024, 512)])
    print(f"[{name:11}] flatness={sf:.3f}  rms={rms:.4f}  voiced_frac={voiced:.2f}")

# retry Silero: feed the whole clip at once
print("\n=== Silero fed whole clip ===")
sess = ort.InferenceSession(os.path.join("build_assets", "silero_vad.onnx"),
                            providers=["CPUExecutionProvider"])
for name, audio in samples.items():
    try:
        state = np.zeros((2, 1, 128), dtype=np.float32)
        out, _ = sess.run(None, {"input": audio.reshape(1, -1).astype(np.float32),
                                 "state": state, "sr": np.array(16000, dtype=np.int64)})
        print(f"[{name:11}] whole-clip out shape={np.array(out).shape} val={np.array(out).ravel()[:4]}")
    except Exception as e:
        print(f"[{name:11}] error: {str(e)[:80]}")
