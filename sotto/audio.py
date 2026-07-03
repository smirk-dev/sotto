"""Microphone capture at 16 kHz mono float32 (what Whisper expects).

The input stream is opened once and kept warm — opening a WASAPI stream takes
~1 s, which would clip the first words of every dictation. While idle the
callback discards audio immediately; frames are kept only between begin() and
end().
"""

import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK = 1600  # 100 ms


def list_input_devices():
    """Input devices of the WASAPI host API (full names, no MME duplicates)."""
    apis = sd.query_hostapis()
    wasapi = next((i for i, a in enumerate(apis) if "WASAPI" in a["name"]), None)
    devices = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and (wasapi is None or d["hostapi"] == wasapi):
            devices.append((i, d["name"]))
    return devices


def resolve_device(name_substring):
    if not name_substring:
        return None  # system default
    for idx, name in list_input_devices():
        if name_substring.lower() in name.lower():
            return idx
    return None


class Recorder:
    """Warm persistent stream; capture happens only between begin()/end()."""

    def __init__(self, on_level=None):
        self.on_level = on_level  # callback(float 0..1) per 100 ms while capturing
        self._stream = None
        self._device = "unset"
        self._capturing = False
        self._chunks = []
        self._samples = 0
        self._lock = threading.Lock()

    def open(self, device=None):
        """(Re)open the warm stream. Safe to call again with the same device."""
        if self._stream is not None and device == self._device:
            return
        self.close()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            blocksize=BLOCK, device=device, callback=self._callback,
        )
        self._stream.start()
        self._device = device

    def close(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
            self._device = "unset"

    @property
    def ready(self):
        return self._stream is not None and self._stream.active

    def _callback(self, indata, frames, time_info, status):
        if not self._capturing:
            return
        data = indata[:, 0].copy()
        with self._lock:
            if self._capturing:
                self._chunks.append(data)
                self._samples += len(data)
        if self.on_level:
            rms = float(np.sqrt(np.mean(data**2)))
            self.on_level(min(1.0, rms * 18.0))

    def begin(self, device=None):
        """Start keeping audio. Opens the stream first if needed (cold path)."""
        self.open(device)
        with self._lock:
            self._chunks = []
            self._samples = 0
            self._capturing = True

    @property
    def sample_count(self):
        with self._lock:
            return self._samples

    def read_range(self, start, end):
        """Samples [start:end) as one array (for incremental transcription)."""
        with self._lock:
            joined = np.concatenate(self._chunks) if self._chunks else np.empty(0, np.float32)
        return joined[start:end]

    def end(self):
        """Stop keeping audio; returns everything captured. Stream stays warm."""
        with self._lock:
            self._capturing = False
            audio = np.concatenate(self._chunks) if self._chunks else np.empty(0, np.float32)
            self._chunks = []
            self._samples = 0
        return audio
