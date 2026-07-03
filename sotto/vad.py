"""Cheap voice-activity gate — pure numpy, no model.

Distinguishes real speech from static/broadband noise and silence using energy
plus spectral flatness. Static/white noise has a flat spectrum (flatness → 1);
speech has peaky formants (flatness ≈ 0.15–0.35). This stops Whisper from being
handed noise and hallucinating a random foreign language.

Measured on this machine (tests/probe_vad.py): speech 0.18–0.23, white noise 0.85,
silence 1.0 (gated by energy). Threshold 0.5 separates them with margin.
"""

import numpy as np

FRAME = 1024
HOP = 512
VOICED_RMS = 0.01        # a frame counts as "voiced" above this energy
FLATNESS_MAX = 0.50      # mean flatness over voiced frames above this => noise
MIN_VOICED_FRAC = 0.10   # need at least this fraction of frames to be voiced
_WIN = np.hanning(FRAME)


def has_speech(audio: np.ndarray) -> bool:
    """True if `audio` plausibly contains speech (not silence or static noise)."""
    if len(audio) < FRAME:
        return float(np.sqrt(np.mean(audio ** 2))) > VOICED_RMS
    voiced = 0
    total = 0
    flats = []
    for i in range(0, len(audio) - FRAME, HOP):
        frame = audio[i:i + FRAME]
        total += 1
        if np.sqrt(np.mean(frame ** 2)) < VOICED_RMS:
            continue
        voiced += 1
        mag = np.abs(np.fft.rfft(frame * _WIN)) + 1e-10
        flats.append(float(np.exp(np.mean(np.log(mag))) / np.mean(mag)))
    if total == 0 or voiced == 0 or voiced / total < MIN_VOICED_FRAC:
        return False
    return float(np.mean(flats)) < FLATNESS_MAX
