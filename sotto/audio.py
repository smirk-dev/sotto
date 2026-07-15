"""Microphone capture at 16 kHz mono float32 (what Whisper expects).

The input stream is opened once and kept warm — opening a WASAPI stream takes
~1 s, which would clip the first words of every dictation. While idle the
callback discards audio immediately; frames are kept only between begin() and
end().
"""

import sys
import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK = 1600  # 100 ms

# A muted mic still delivers frames, but only the ±1 LSB of dither the driver
# emits (peak 1/32768 = 3.05e-5). Real capture — even a silent room — sits orders
# of magnitude above that, so a whole utterance under this peak means no signal
# ever reached us (muted endpoint or hardware mute key) rather than "you were
# quiet". Kept 10x above the dither floor and well under room tone (~5e-3).
SILENCE_PEAK = 3e-4

# Prefer one host API per platform so the picker isn't cluttered with duplicates
# (WASAPI on Windows; PulseAudio/PipeWire on Linux, avoiding raw-ALSA dupes).
_PREFERRED_APIS = ("WASAPI",) if sys.platform == "win32" else ("PipeWire", "Pulse", "PulseAudio")


def list_input_devices():
    """Input devices of the preferred host API for this platform (full names)."""
    apis = sd.query_hostapis()
    preferred = None
    for name in _PREFERRED_APIS:
        preferred = next((i for i, a in enumerate(apis) if name.lower() in a["name"].lower()), None)
        if preferred is not None:
            break
    devices = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and (preferred is None or d["hostapi"] == preferred):
            devices.append((i, d["name"]))
    return devices


def resolve_device(name_substring):
    if not name_substring:
        return None  # system default
    for idx, name in list_input_devices():
        if name_substring.lower() in name.lower():
            return idx
    return None


def _extra_settings(device):
    """WASAPI-specific stream settings, or None for other host APIs.

    WASAPI in shared mode only opens at the endpoint's native mix rate (48 kHz
    here), so asking for our 16 kHz raises "Invalid sample rate [-9997]" — which
    is every device the picker lists, since list_input_devices() is WASAPI-only.
    auto_convert lets PortAudio resample for us. It is rejected on other host
    APIs, so it is only attached to genuine WASAPI devices (device=None is the
    PortAudio default, typically MME, which resamples on its own).
    """
    if sys.platform != "win32":
        return None
    try:
        idx = sd.default.device[0] if device is None else device
        api = sd.query_hostapis(sd.query_devices(idx)["hostapi"])["name"]
        if "wasapi" in api.lower():
            return sd.WasapiSettings(auto_convert=True)
    except Exception:
        pass  # unknown device: let InputStream raise the real error
    return None


def open_input_stream(device, callback, blocksize=BLOCK):
    """A 16 kHz mono float32 input stream, with per-host-API quirks handled."""
    return sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=blocksize,
        device=device, callback=callback, extra_settings=_extra_settings(device),
    )


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
        """(Re)open the warm stream. Safe to call again with the same device.

        A stream that has gone inactive (device unplugged, or the endpoint reset
        under us) is reopened rather than kept: PortAudio does not resurrect it,
        and holding it would silently capture nothing until the app restarts.
        """
        if self._stream is not None and device == self._device and self._stream.active:
            return
        self.close()
        self._stream = open_input_stream(device, self._callback)
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
