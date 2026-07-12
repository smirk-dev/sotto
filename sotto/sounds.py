"""Subtle start/stop blips, generated once and played asynchronously.

Windows uses winsound; other platforms play the generated WAV through
sounddevice (already a dependency for mic capture).
"""

import math
import os
import struct
import sys
import threading
import wave

from .config import APP_DIR

_SOUND_DIR = os.path.join(APP_DIR, "sounds")
RATE = 22050

if sys.platform == "win32":
    import winsound


def _write_blip(path, f0, f1, ms=110, vol=0.16):
    n = int(RATE * ms / 1000)
    frames = bytearray()
    for i in range(n):
        t = i / RATE
        f = f0 + (f1 - f0) * (i / n)
        env = math.sin(math.pi * i / n)  # fade in/out
        s = int(32767 * vol * env * math.sin(2 * math.pi * f * t))
        frames += struct.pack("<h", s)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


def ensure_sounds():
    os.makedirs(_SOUND_DIR, exist_ok=True)
    start = os.path.join(_SOUND_DIR, "start.wav")
    stop = os.path.join(_SOUND_DIR, "stop.wav")
    if not os.path.exists(start):
        _write_blip(start, 660, 990)
    if not os.path.exists(stop):
        _write_blip(stop, 880, 550)
    return start, stop


def _play_sounddevice(path):
    try:
        import numpy as np
        import sounddevice as sd
        with wave.open(path, "rb") as w:
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        sd.play(data, RATE)  # non-blocking; plays on the default output device
    except Exception:
        pass


def play(which: str):
    start, stop = ensure_sounds()
    path = start if which == "start" else stop
    if sys.platform == "win32":
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except RuntimeError:
            pass
    else:
        threading.Thread(target=_play_sounddevice, args=(path,), daemon=True).start()
