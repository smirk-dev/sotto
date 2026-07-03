"""Config, paths, stats. Everything lives under %LOCALAPPDATA%\\Sotto."""

import json
import os
import threading

APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Sotto")
MODELS_DIR = os.path.join(APP_DIR, "models")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
HISTORY_PATH = os.path.join(APP_DIR, "history.jsonl")
LOG_PATH = os.path.join(APP_DIR, "app.log")

# name -> (HF repo of official OpenVINO int8 conversion, approx size, note)
MODELS = {
    "tiny.en": ("OpenVINO/whisper-tiny.en-int8-ov", "~60 MB", "fastest, lowest accuracy"),
    "base.en": ("OpenVINO/whisper-base.en-int8-ov", "~95 MB", "recommended — fast & accurate"),
    "small.en": ("OpenVINO/whisper-small.en-int8-ov", "~300 MB", "most accurate English"),
    "base (multilingual)": ("OpenVINO/whisper-base-int8-ov", "~95 MB", "fast, any language"),
    "small (multilingual)": ("OpenVINO/whisper-small-int8-ov", "~300 MB", "accurate, any language"),
    "large-v3-turbo (multilingual)": ("OpenVINO/whisper-large-v3-turbo-int8-ov", "~1.7 GB",
                                      "best accuracy, slow on this machine"),
}

# Hold-to-talk chord presets: name -> set of "sides" of modifiers, resolved in hotkey.py
HOLD_CHORDS = ["Ctrl+Win", "Alt+Win", "Ctrl+Alt", "F9 (hold)"]
TOGGLE_COMBOS = ["Ctrl+Alt+D", "Ctrl+Shift+Space", "Ctrl+Alt+Space", "F10", "Disabled"]

CONFIG_VERSION = 2               # bump to migrate existing installs (see Config.__init__)

DEFAULTS = {
    "config_version": CONFIG_VERSION,
    "model": "small (multilingual)",  # understands Hindi/Hinglish/English out of the box
    "compute_device": "CPU",     # CPU | GPU (Intel graphics via OpenVINO)
    "language": "auto",          # "auto" (detect per chunk) or an ISO code; .en models force en
    "hold_chord": "Ctrl+Win",
    "toggle_combo": "Ctrl+Alt+D",
    "input_device": None,        # None = system default; else device name substring
    "strip_fillers": True,
    "sounds": True,
    "history_enabled": True,
    "live_typing": True,         # in toggle mode, insert text as you speak (not just at stop)
    "paste_threshold": 400,      # chars; above this use clipboard paste instead of typed input
    "injection": "type",         # "type" (SendInput unicode) or "paste"
    "start_with_windows": False,
    "dictionary": ["Suryansh"],  # names/jargon to bias + post-correct
    "stats": {"words": 0, "utterances": 0, "audio_seconds": 0.0},
}


class Config:
    """Thread-safe config backed by config.json."""

    def __init__(self):
        self._lock = threading.Lock()
        os.makedirs(MODELS_DIR, exist_ok=True)
        self._data = dict(DEFAULTS)
        stored = {}
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                stored = json.load(f)
            for k, v in stored.items():
                if k in DEFAULTS:
                    self._data[k] = v
        except (OSError, ValueError):
            pass
        # one-time migration: switch older English-only installs to the new
        # multilingual default so Hindi/Hinglish works without any setup.
        if stored.get("config_version", 1) < CONFIG_VERSION:
            self._data["model"] = "small (multilingual)"
            self._data["language"] = "auto"
            self._data["config_version"] = CONFIG_VERSION
        self.save()

    def get(self, key):
        with self._lock:
            return self._data[key]

    def set(self, key, value):
        with self._lock:
            self._data[key] = value
        self.save()

    def add_stats(self, words, audio_seconds):
        with self._lock:
            s = self._data["stats"]
            s["words"] += words
            s["utterances"] += 1
            s["audio_seconds"] += audio_seconds
        self.save()

    def save(self):
        with self._lock:
            tmp = CONFIG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, CONFIG_PATH)
