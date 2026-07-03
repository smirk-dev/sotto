"""Check if EcoQoS/priority throttling explains slow inference: matmul GFLOPS +
transcribe latency, before and after disabling power throttling."""

import ctypes
import os
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def gflops():
    a = np.random.rand(2000, 2000).astype(np.float32)
    t0 = time.perf_counter()
    for _ in range(5):
        a @ a
    dt = time.perf_counter() - t0
    return 5 * 2 * 2000**3 / dt / 1e9


class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [("Version", ctypes.c_ulong), ("ControlMask", ctypes.c_ulong),
                ("StateMask", ctypes.c_ulong)]


def disable_throttling():
    k32 = ctypes.WinDLL("kernel32")
    PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
    state = PROCESS_POWER_THROTTLING_STATE(1, PROCESS_POWER_THROTTLING_EXECUTION_SPEED, 0)
    ok = k32.SetProcessInformation(k32.GetCurrentProcess(), 4,  # ProcessPowerThrottling
                                   ctypes.byref(state), ctypes.sizeof(state))
    k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00008000)  # ABOVE_NORMAL
    return bool(ok)


print(f"gflops before: {gflops():.1f}")
print(f"disable throttling ok: {disable_throttling()}")
print(f"gflops after:  {gflops():.1f}")

from faster_whisper import WhisperModel
from sotto.engine import model_dir

with wave.open(os.path.join(os.path.dirname(__file__), "wav", "short.wav")) as w:
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
model = WhisperModel(model_dir("small.en"), device="cpu", compute_type="int8", cpu_threads=8)
for run in range(3):
    t0 = time.perf_counter()
    segs, _ = model.transcribe(audio, language="en", beam_size=1, vad_filter=True,
                               condition_on_previous_text=False)
    _ = " ".join(s.text for s in segs)
    print(f"transcribe run {run}: {time.perf_counter()-t0:.2f}s")
