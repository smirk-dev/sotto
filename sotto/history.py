"""Dictation history: JSONL log with search, re-copy, privacy clear."""

import json
import os
import time

from .config import HISTORY_PATH


def append(text: str, duration: float):
    entry = {"ts": time.time(), "text": text, "seconds": round(duration, 1)}
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load(limit=500):
    if not os.path.exists(HISTORY_PATH):
        return []
    entries = []
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
    return entries[-limit:][::-1]  # newest first


def clear():
    try:
        os.remove(HISTORY_PATH)
    except OSError:
        pass
