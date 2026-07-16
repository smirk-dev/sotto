"""Synthesize the Hindi/Hinglish eval set used by eval_device_accuracy.py.

Needs Kokoro TTS, which is NOT a Sotto dependency — run it with a venv that has
it installed (`pip install kokoro soundfile`). The generated clips are committed,
so you only need this to extend or regenerate the set.

The repo has exactly one hinglish clip and no reference transcript, which is not
enough to judge whether moving the big model to the iGPU costs accuracy on the
use case that model was chosen for. These are code-switched the way the user
actually dictates (Devanagari + English nouns).
"""
import os
import numpy as np
import soundfile as sf
from kokoro import KPipeline

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wav", "hi")
os.makedirs(OUT, exist_ok=True)

SENTENCES = [
    ("h01", "मैंने कल का plan finalize कर दिया है।"),
    ("h02", "हम लोग meeting में इसको discuss करेंगे।"),
    ("h03", "बाकी details मैं email पे भेज दूंगा।"),
    ("h04", "ये project अगले हफ्ते तक complete हो जाएगा।"),
    ("h05", "मुझे इस report का review करना है।"),
    ("h06", "क्या आप मुझे वो file share कर सकते हैं?"),
    ("h07", "आज का weather बहुत अच्छा है।"),
    ("h08", "मैं office से निकल रहा हूँ, दस मिनट में पहुँचता हूँ।"),
    ("h09", "इस code में एक bug है जो fix करना पड़ेगा।"),
    ("h10", "कल सुबह नौ बजे call schedule कर लेते हैं।"),
]

pipe = KPipeline(lang_code="h")
with open(os.path.join(OUT, "truth.tsv"), "w", encoding="utf-8") as tf:
    for key, text in SENTENCES:
        audio = np.concatenate([a for _, _, a in pipe(text, voice="hf_alpha", speed=1.0)])
        audio = np.asarray(audio, dtype=np.float32)
        # kokoro is 24 kHz; sotto works at 16 kHz
        idx = np.arange(0, len(audio), 24000 / 16000)
        audio16 = np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)
        sf.write(os.path.join(OUT, f"{key}.wav"), audio16, 16000, subtype="PCM_16")
        tf.write(f"{key}\t{text}\n")
        print(f"{key}: {len(audio16)/16000:4.1f}s  {text}")
print(f"\nwrote {len(SENTENCES)} clips + truth.tsv to {OUT}")
