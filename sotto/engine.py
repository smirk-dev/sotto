"""OpenVINO Whisper engine: model load/download management + dictation sessions.

Chosen over faster-whisper and whisper.cpp after benchmarking on this machine
(i7-1360P, no CUDA): OpenVINO int8 CPU runs whisper base.en at <1s for a 4s
utterance vs ~6s for ctranslate2 int8 — see tests/bench_*.py and PROGRESS.md.

A DictationSession transcribes incrementally while recording (committing chunks
at silence boundaries) so that when the user releases the hotkey only the tail
remains — keeping end-of-utterance latency low even for long dictations.
"""

import logging
import os
import re
import threading
import time

import numpy as np

from . import vad
from .audio import SAMPLE_RATE
from .config import MODELS, MODELS_DIR

log = logging.getLogger("sotto")

# Xet fetches into a global chunk cache and only materialises files into the model
# dir near the end, so an 800 MB download reads as "10 MB" for minutes and looks
# hung — the progress UI polls the model dir. Plain HTTP streams into it instead,
# for ~13% more wall clock on a one-off download. huggingface_hub snapshots this
# into a module constant at import time, so it has to be set before it is imported
# (engine imports it lazily, inside the functions below). setdefault so anyone who
# sets HF_HUB_DISABLE_XET=0 deliberately still gets Xet.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

# mild repeat penalty as a backstop for repeat-loops (VAD is the primary noise gate);
# 1.2 suppresses loops without clipping real speech (1.3 dropped trailing words).
REPETITION_PENALTY = 1.2

# Languages that share Hindi's spoken form / should be rendered as Hindi (Devanagari,
# left-to-right) rather than their auto-detected script. Urdu is the big one — Whisper
# constantly tags Hindi speech as Urdu and writes it right-to-left in Arabic script.
_HINDI_FAMILY = {"hi", "ur", "ne", "mr", "sa", "bho", "mai", "pa", "gu", "bn"}

# Whisper (esp. multilingual) can fall into a repeat loop on silence/noise/odd
# audio, emitting the same character or short cluster hundreds of times. Collapse
# pathological runs so a glitch never floods the user's document.
_RUN_CHAR = re.compile(r"(.)\1{4,}")            # 5+ identical chars -> 2
_RUN_UNIT = re.compile(r"(.{1,5}?)\1{3,}")      # a 1-5 char unit repeated 4+ -> once


def _collapse_repeats(text: str) -> str:
    text = _RUN_CHAR.sub(r"\1\1", text)
    text = _RUN_UNIT.sub(r"\1", text)
    return text


def _dominant_script(text: str) -> str:
    """Which writing system dominates: latin | devanagari | arabic | other | none."""
    counts = {"latin": 0, "devanagari": 0, "arabic": 0, "other": 0}
    for ch in text:
        if not ch.isalpha():
            continue
        o = ord(ch)
        if o < 0x250 or 0x1E00 <= o <= 0x1EFF:
            counts["latin"] += 1
        elif 0x900 <= o <= 0x97F:
            counts["devanagari"] += 1
        elif 0x600 <= o <= 0x6FF or 0x750 <= o <= 0x77F or 0xFB50 <= o <= 0xFDFF:
            counts["arabic"] += 1
        else:
            counts["other"] += 1
    if not any(counts.values()):
        return "none"
    return max(counts, key=counts.get)

CHUNK_SECONDS = 14          # commit a chunk once this much uncommitted audio exists
SILENCE_RMS = 0.004
SILENCE_BLOCK = 1600        # 100 ms
CACHE_DIR = os.path.join(MODELS_DIR, "ov-cache")

# Whisper emits these on silent/noise-only audio; drop them when audio was quiet
_HALLUCINATIONS = {"thank you.", "thanks for watching!", "you", "you.", "bye.", "thank you very much."}


def model_dir(name):
    return os.path.join(MODELS_DIR, MODELS[name][0].split("/")[-1])


# Every OpenVINO whisper repo we list ships exactly these runtime artifacts, so
# requiring all of them tells a finished download apart from one that stopped
# half way. Checking only the encoder (as this used to) called a model with a
# missing decoder "downloaded", which surfaced later as a load error instead.
_REQUIRED_FILES = (
    "openvino_encoder_model.bin", "openvino_encoder_model.xml",
    "openvino_decoder_model.bin", "openvino_decoder_model.xml",
    "openvino_tokenizer.bin", "openvino_tokenizer.xml",
    "openvino_detokenizer.bin", "openvino_detokenizer.xml",
)

DOWNLOAD_ATTEMPTS = 3

# Which models are worth handing to the iGPU. Measured, not assumed — on this class
# of machine (i7-1360P + Iris Xe, tests/bench_accel.py, 4.4 s clip):
#
#   large-v3-turbo   CPU 8.02 s   GPU 2.12 s   -> GPU wins decisively
#   small            CPU 1.49 s   GPU 1.31 s   -> a wash, and the GPU LOSES on
#                                                 longer clips (2.63 vs 2.27 s)
#
# End to end through the app (hotkey release -> text) the turbo win is 4.60 s -> 1.79 s
# warm, i.e. ~2.6x rather than the ~3.8x those raw generate() numbers imply — the
# engine caps max_new_tokens by clip length and the bench does not. Same text either
# way: tests/eval_device_accuracy.py scores CER 15.3% on both devices.
#
# The split is architectural rather than incidental. large-v3-turbo is ~79% encoder
# (32 encoder layers vs 4 decoder — that is the "turbo" design), and Whisper's
# encoder is one fixed-size, fully parallel pass over a 30 s mel regardless of how
# long you actually spoke: on CPU it costs a flat ~8 s for a 4 s clip and a 14 s one
# alike. That shape — big, dense, parallel, no autoregression — is what an iGPU is
# for. Small models spend their time in the memory-bound decoder loop instead, where
# the GPU has nothing to add and per-call overhead makes it a net loss. So this stays
# a per-model list, not a blanket "use the GPU if you have one".
_GPU_WORTH_IT = {"large-v3-turbo (multilingual)"}

# CPU is the floor: it needs no driver and is always present, so it is what we fall
# back to when a GPU is asked for but cannot actually run the model.
FALLBACK_DEVICE = "CPU"


def gpu_available():
    """True if OpenVINO can see a usable GPU. Cheap, but not free — call off the GUI thread."""
    try:
        import openvino
        return "GPU" in openvino.Core().available_devices
    except Exception:  # no openvino, no driver, enumeration blew up -> no GPU
        return False


def resolve_compute_device(device, model_name):
    """Turn the stored setting into a real OpenVINO device.

    "Auto" picks per model (see _GPU_WORTH_IT); an explicit "CPU"/"GPU" is obeyed.
    """
    if device and device != "Auto":
        return device
    if model_name in _GPU_WORTH_IT and gpu_available():
        return "GPU"
    return FALLBACK_DEVICE


def is_downloaded(name):
    """True only if every file the pipeline needs is present (see _REQUIRED_FILES)."""
    d = model_dir(name)
    return all(os.path.exists(os.path.join(d, f)) for f in _REQUIRED_FILES)


def missing_files(name):
    """Which required files are absent — for diagnosing a partial download."""
    d = model_dir(name)
    return [f for f in _REQUIRED_FILES if not os.path.exists(os.path.join(d, f))]


def expected_bytes(name):
    """Total download size per the Hub, or None if it can't be determined.

    Lets the UI show real progress instead of an indeterminate spinner.
    """
    from huggingface_hub import HfApi
    try:
        info = HfApi().model_info(MODELS[name][0], files_metadata=True)
        return sum(s.size or 0 for s in (info.siblings or [])) or None
    except Exception:
        return None


def download_model(name, attempts=DOWNLOAD_ATTEMPTS):
    """Blocking download from the official Hugging Face mirror (user-initiated).

    Transient network failures are retried with a backoff; snapshot_download
    resumes from whatever is already on disk, so a retry only re-fetches the
    bytes that are actually missing.
    """
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils import disable_progress_bars
    # huggingface_hub draws tqdm progress bars on sys.stderr, which is None in the
    # windowed (console=False) build — the AttributeError killed every download
    # before a single byte moved, so downloads never worked from the packaged app.
    # The Settings window renders its own progress, so the bars are pure liability.
    disable_progress_bars()
    delay = 2
    for attempt in range(1, attempts + 1):
        try:
            snapshot_download(MODELS[name][0], local_dir=model_dir(name))
            break
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(delay)
            delay *= 2
    missing = missing_files(name)
    if missing:  # Hub reported success but the model is unusable — say so now
        raise RuntimeError(f"download incomplete, missing: {', '.join(missing)}")


def downloaded_bytes(name):
    total = 0
    for root, _dirs, files in os.walk(model_dir(name)):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


class Engine:
    """Owns the WhisperPipeline. Loading happens on a background thread."""

    def __init__(self, on_state=None):
        self.pipe = None
        self.model_name = None
        self.device = None          # the device actually in use (post-resolve/fallback)
        self.state = "empty"        # empty | loading | ready | error
        self.error = ""
        self.on_state = on_state or (lambda s: None)
        self._lock = threading.Lock()

    def load(self, name, device="Auto"):
        def build(target):
            import openvino_genai
            os.makedirs(CACHE_DIR, exist_ok=True)
            # First GPU compile of large-v3-turbo takes ~15 s and leaves ~900 MB of
            # compiled kernels in CACHE_DIR; later loads reuse it and take ~5 s.
            t0 = time.perf_counter()
            pipe = openvino_genai.WhisperPipeline(model_dir(name), target,
                                                  CACHE_DIR=CACHE_DIR)
            log.info("loaded %s on %s in %.1fs", name, target, time.perf_counter() - t0)
            return pipe

        def work():
            self.state = "loading"
            self.on_state("loading")
            target = resolve_compute_device(device, name)
            try:
                try:
                    pipe = build(target)
                except Exception as e:
                    # A GPU can be enumerated and still fail to compile or fit the
                    # model (old driver, tiny shared pool, headless session). That is
                    # a reason to be slower, not to leave the user with a dead app.
                    if target == FALLBACK_DEVICE:
                        raise
                    log.warning("%s load failed on %s (%s) — falling back to %s",
                                name, target, str(e)[:120], FALLBACK_DEVICE)
                    target = FALLBACK_DEVICE
                    pipe = build(target)
                with self._lock:
                    self.pipe = pipe
                    self.model_name = name
                    self.device = target
                self.state = "ready"
                self.on_state("ready")
            except Exception as e:  # surfaced in tray/settings
                log.exception("model load failed: %s", name)
                self.state = "error"
                self.error = str(e)
                self.on_state("error")
        threading.Thread(target=work, name="model-load", daemon=True).start()

    def _generate(self, audio, prompt, language):
        """One generate() call. language=None auto-detects. Returns (text, detected_lang)."""
        with self._lock:
            pipe = self.pipe
            multilingual = not (self.model_name or "").endswith(".en")
        gc = pipe.get_generation_config()
        gc.repetition_penalty = REPETITION_PENALTY
        gc.initial_prompt = prompt or None
        # bound runaway output on odd audio without clipping real speech (~25 tok/s)
        gc.max_new_tokens = min(440, int(len(audio) / SAMPLE_RATE * 25) + 32)
        if multilingual:  # .en models reject task/language
            gc.task = "transcribe"
            gc.language = f"<|{language}|>" if language else None
        with self._lock:
            res = pipe.generate(audio, gc)
        return str(res).strip(), (getattr(res, "language", "") or "")

    def _sanitize(self, text):
        text = _collapse_repeats(text.strip())
        if text.lower() in _HALLUCINATIONS:
            return ""
        return text

    def transcribe(self, audio: np.ndarray, language="auto", prompt=None) -> str:
        """Transcribe one chunk. `language`: 'auto' (English+Hindi, the robust default),
        'auto-all' (unconstrained), 'en'/'hi'/<code> (forced), or ignored for .en models."""
        with self._lock:
            pipe = self.pipe
            name = self.model_name
        if pipe is None or len(audio) < SAMPLE_RATE // 4:
            return ""
        if not vad.has_speech(audio):     # silence or static noise -> no hallucination
            return ""

        # English-only models: language is fixed, just transcribe.
        if name.endswith(".en"):
            return self._sanitize(self._generate(audio, prompt, None)[0])

        # Forced single language (English, Hindi, or a specific code).
        if language not in ("auto", "auto-all"):
            code = "en" if language == "en" else language
            return self._sanitize(self._generate(audio, prompt, code)[0])

        # Auto-detect, then correct. First pass is unconstrained.
        text, lang = self._generate(audio, prompt, None)
        if language == "auto-all":
            return self._sanitize(text)

        # Default "auto" = English + Hindi only, everything else corrected or dropped.
        script = _dominant_script(text)
        if script == "devanagari":
            return self._sanitize(text)                       # clean Hindi
        if script == "arabic" or (lang in _HINDI_FAMILY and lang != "hi"):
            # Hindi mis-tagged as Urdu/other Indic -> redo forcing Hindi (Devanagari, LTR)
            return self._sanitize(self._generate(audio, prompt, "hi")[0])
        if lang == "en" or script == "latin":
            return self._sanitize(text)                       # English
        # exotic language AND exotic script => almost certainly noise; drop it
        return ""


def _last_silence_boundary(audio: np.ndarray) -> int | None:
    """Index just after the last ~200 ms of silence in `audio`, or None."""
    n = len(audio) // SILENCE_BLOCK
    quiet_run = 0
    best = None
    for b in range(n):
        block = audio[b * SILENCE_BLOCK:(b + 1) * SILENCE_BLOCK]
        if float(np.sqrt(np.mean(block**2))) < SILENCE_RMS:
            quiet_run += 1
            if quiet_run >= 2:
                best = (b + 1) * SILENCE_BLOCK
        else:
            quiet_run = 0
    return best


class DictationSession:
    """One press-to-release (or toggle on/off) recording.

    feed() is called periodically while recording and commits the next finished
    chunk at a silence boundary, returning its raw text — the app inserts that
    immediately in live-typing mode. finish() transcribes the remaining tail.

    min_commit_s: don't commit until this much uncommitted audio has piled up
      (lower = more responsive live typing, higher = fewer, more-accurate chunks).
    max_commit_s: if the speaker never pauses, force a cut past this length so a
      long monologue still streams out instead of waiting for the very end.
    """

    OVERLAP_S = 1.5   # re-transcribe this much across a forced (mid-speech) seam

    def __init__(self, engine: Engine, recorder, language, vocabulary,
                 min_commit_s=CHUNK_SECONDS, max_commit_s=CHUNK_SECONDS * 2):
        self.engine = engine
        self.recorder = recorder
        self.language = language
        self.vocab = vocabulary      # list of dictionary words
        self.min_commit = min_commit_s
        self.max_commit = max_commit_s
        self.committed = 0           # sample index transcribed so far
        self.parts = []              # committed text chunks (raw)
        self._dedup_next = False     # the next chunk re-covers a forced seam

    def _prompt(self):
        # Disabled: openvino Whisper's initial_prompt makes it truncate a chunk
        # badly (verified — a 6 s chunk collapsed to 5 words when the previous
        # sentence was passed as context). Dictionary names are fixed by textproc
        # post-correction instead, which costs nothing here.
        return None

    def _dedup(self, text):
        """Drop words at the start of `text` that repeat the tail of what's
        already committed — used after a forced seam left an overlap."""
        if not self.parts or not text:
            return text

        def norm(w):
            return w.lower().strip(".,!?;:\"'“”")

        prev = [norm(w) for w in " ".join(self.parts).split()[-14:]]
        new = text.split()
        new_norm = [norm(w) for w in new]
        for k in range(min(len(prev), len(new_norm), 12), 1, -1):  # need >=2 words to be safe
            if prev[-k:] == new_norm[:k]:
                return " ".join(new[k:])
        return text

    def feed(self):
        """Commit the next ready chunk; return its raw text (or '')."""
        total = self.recorder.sample_count
        uncommitted = total - self.committed
        if uncommitted < self.min_commit * SAMPLE_RATE:
            return ""
        audio = self.recorder.read_range(self.committed, total)
        cut = _last_silence_boundary(audio)
        forced = cut is None or cut < SAMPLE_RATE
        if forced:                                 # no pause found yet
            if uncommitted < self.max_commit * SAMPLE_RATE:
                return ""
            cut = len(audio) - SAMPLE_RATE // 2     # long monologue: force a cut near the end
            if cut < SAMPLE_RATE:
                return ""
        text = self.engine.transcribe(audio[:cut], self.language, self._prompt())
        if self._dedup_next:
            text = self._dedup(text)
        # After a forced cut, keep an overlap so the NEXT chunk re-covers the seam
        # (Whisper drops words at hard mid-speech boundaries); silence cuts are clean.
        overlap = int(self.OVERLAP_S * SAMPLE_RATE) if forced else 0
        self.committed += max(SAMPLE_RATE, cut - overlap)
        self._dedup_next = forced
        if text:
            self.parts.append(text)
        return text

    def finish(self, audio_total: np.ndarray) -> str:
        """Transcribe the remaining tail; return its raw text (or '')."""
        tail = audio_total[self.committed:]
        text = self.engine.transcribe(tail, self.language, self._prompt())
        if self._dedup_next:
            text = self._dedup(text)
        if text:
            self.parts.append(text)
        return text

    def full_text(self) -> str:
        """All committed + tail chunks joined (for history / non-live insert)."""
        return " ".join(self.parts).strip()
